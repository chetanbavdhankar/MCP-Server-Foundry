"""
MCP Server Foundry — Web UI Backend

Single-file Flask backend that orchestrates the existing CLI pipeline via subprocess.
Launch: python foundry_ui.py → browser opens at http://localhost:7777

No rewrites of existing tools — everything runs as subprocess calls to:
  - data/auto_spec_generator.py  (spec generation)
  - foundry/forge_recipe.py      (MCP server forging)
"""

from flask import Flask, request, jsonify, send_file
import os
import sys
import json
import uuid
import subprocess
import threading
import webbrowser
import asyncio
import time
from pathlib import Path

import pandas as pd
import yaml
import requests as http_req
import litellm

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ============================================================
# Constants
# ============================================================
ROOT = Path(__file__).parent.resolve()
DATA_DIR = ROOT / "data"
SPECS_DIR = ROOT / "foundry" / "specs"
OUTPUT_BASE = ROOT / "foundry" / "output"
PORT = 7777

# ============================================================
# Flask App
# ============================================================
app = Flask(__name__, static_folder=None)

# ============================================================
# Session State (single-user local tool)
# ============================================================
state = {
    "session_id": None,
    "uploaded_files": [],
    "combined_file": None,
    "columns": [],
    "row_count": 0,
    "file_size_kb": 0,
    "api_title": "My Dataset",
    "spec_path": None,
    "spec_content": None,
    "output_name": None,
    "server_main_path": None,
    "forge_status": "idle",
    "forge_logs": [],
    "forge_progress": 0,
    "forge_error": None,
    "mcp_process": None,
    "server_tools": [],
    "connection_config": {},
}

_forge_lock = threading.Lock()


def _kill_mcp():
    """Kill any running MCP server process."""
    proc = state.get("mcp_process")
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    state["mcp_process"] = None


def reset_state():
    """Kill processes and reset to initial state."""
    _kill_mcp()
    state.update({
        "session_id": None,
        "uploaded_files": [],
        "combined_file": None,
        "columns": [],
        "row_count": 0,
        "file_size_kb": 0,
        "api_title": "My Dataset",
        "spec_path": None,
        "spec_content": None,
        "output_name": None,
        "server_main_path": None,
        "forge_status": "idle",
        "forge_logs": [],
        "forge_progress": 0,
        "forge_error": None,
        "mcp_process": None,
        "server_tools": [],
        "connection_config": {},
    })


# ============================================================
# API Routes
# ============================================================

@app.route("/")
def index():
    return send_file(str(ROOT / "foundry_ui.html"))


@app.route("/ui/<path:filename>")
def serve_ui(filename):
    """Serve frontend static assets (CSS/JS)."""
    safe = Path(filename).name  # prevent traversal
    fpath = ROOT / "ui" / safe
    if fpath.exists():
        return send_file(str(fpath))
    return "Not found", 404


@app.route("/api/upload", methods=["POST"])
def upload():
    """Save uploaded files, validate columns, return schema info."""
    files = request.files.getlist("files")
    if not files or files[0].filename == "":
        return jsonify({"error": "No files provided"}), 400

    session_id = str(uuid.uuid4())[:8]
    session_dir = DATA_DIR / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    dfs, saved = [], []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in (".csv", ".xlsx", ".xls", ".json"):
            return jsonify({"error": f"Unsupported format: {ext}. Use CSV, XLSX, or JSON."}), 400
        path = session_dir / f.filename
        f.save(str(path))
        saved.append(str(path))
        try:
            if ext == ".csv":
                dfs.append(pd.read_csv(path))
            elif ext in (".xlsx", ".xls"):
                dfs.append(pd.read_excel(path))
            else:
                dfs.append(pd.read_json(path))
        except Exception as e:
            return jsonify({"error": f"Failed to read {f.filename}: {e}"}), 400

    # Validate columns match across files
    if len(dfs) > 1:
        base = set(dfs[0].columns)
        for i, df in enumerate(dfs[1:], 2):
            if set(df.columns) != base:
                return jsonify({"error": f"File {i} columns don't match file 1."}), 400

    combined = pd.concat(dfs, ignore_index=True)
    combined_path = session_dir / f"combined_{session_id}.xlsx"
    combined.to_excel(str(combined_path), index=False)

    columns = []
    for col in combined.columns:
        sample = ""
        non_null = combined[col].dropna()
        if len(non_null) > 0:
            sample = str(non_null.iloc[0])[:60]
        columns.append({"name": str(col), "type": str(combined[col].dtype), "sample": sample})

    state.update({
        "session_id": session_id,
        "uploaded_files": saved,
        "combined_file": str(combined_path),
        "columns": columns,
        "row_count": len(combined),
        "file_size_kb": round(os.path.getsize(combined_path) / 1024, 1),
    })

    return jsonify({
        "session_id": session_id,
        "file_count": len(files),
        "columns": columns,
        "row_count": len(combined),
        "file_size_kb": state["file_size_kb"],
    })


@app.route("/api/spec", methods=["POST"])
def generate_spec():
    """Run auto_spec_generator.py via subprocess."""
    data = request.get_json() or {}
    title = data.get("title", "My Dataset")
    state["api_title"] = title

    combined = state.get("combined_file")
    if not combined:
        return jsonify({"error": "No file uploaded yet."}), 400

    result = subprocess.run(
        [sys.executable, str(DATA_DIR / "auto_spec_generator.py"), combined, "--title", title],
        capture_output=True, text=True, cwd=str(ROOT),
    )

    if result.returncode != 0:
        return jsonify({"error": f"Spec generation failed: {result.stderr}"}), 500

    # Find the generated spec
    base = os.path.splitext(os.path.basename(combined))[0].lower().replace(" ", "_").replace("-", "_")
    spec_path = SPECS_DIR / f"{base}_api.yaml"

    if not spec_path.exists():
        return jsonify({"error": f"Spec file not found at {spec_path}"}), 500

    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()

    state["spec_path"] = str(spec_path)
    state["spec_content"] = content
    state["output_name"] = f"{base}-server"

    return jsonify({"spec_path": str(spec_path), "content": content})


@app.route("/api/spec-content")
def spec_content():
    if not state.get("spec_content"):
        return jsonify({"error": "No spec generated yet."}), 404
    return jsonify({"content": state["spec_content"], "path": state["spec_path"]})


@app.route("/api/forge", methods=["POST"])
def forge():
    """Start forge_recipe.py in a background thread."""
    if state["forge_status"] == "running":
        return jsonify({"error": "Forge already running."}), 409

    spec = state.get("spec_path")
    if not spec:
        return jsonify({"error": "No spec generated yet."}), 400

    output_name = state["output_name"]
    output_dir = str(OUTPUT_BASE / output_name)

    state.update({
        "forge_status": "running",
        "forge_logs": [],
        "forge_progress": 0,
        "forge_error": None,
        "server_main_path": None,
    })

    def _run():
        try:
            proc = subprocess.Popen(
                [sys.executable, str(ROOT / "foundry" / "forge_recipe.py"),
                 "-i", spec, "-o", output_dir, "--auto-approve"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=str(ROOT / "foundry"),
                bufsize=1,
            )
            for line in iter(proc.stdout.readline, ""):
                line = line.rstrip()
                if not line:
                    continue
                with _forge_lock:
                    state["forge_logs"].append(line)
                    # Estimate progress from agent names
                    ll = line.lower()
                    if "architect" in ll and "completed" in ll:
                        state["forge_progress"] = 25
                    elif "builder" in ll and "completed" in ll:
                        state["forge_progress"] = 50
                    elif "tester" in ll and "completed" in ll:
                        state["forge_progress"] = 75
                    elif "documenter" in ll and "completed" in ll:
                        state["forge_progress"] = 95

            proc.wait()
            with _forge_lock:
                if proc.returncode == 0:
                    state["forge_status"] = "complete"
                    state["forge_progress"] = 100
                    server_main = Path(output_dir) / "server" / "main.py"
                    if server_main.exists():
                        state["server_main_path"] = str(server_main)
                        _build_connection_config()
                        _auto_start_server()
                else:
                    state["forge_status"] = "error"
                    state["forge_error"] = "Pipeline exited with non-zero code."

        except Exception as e:
            with _forge_lock:
                state["forge_status"] = "error"
                state["forge_error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/forge-status")
def forge_status():
    with _forge_lock:
        return jsonify({
            "status": state["forge_status"],
            "progress": state["forge_progress"],
            "logs": state["forge_logs"][-50:],
            "error": state["forge_error"],
            "server_main_path": state["server_main_path"],
        })


def _build_connection_config():
    """Build MCP connection config JSON for external clients."""
    main_path = state.get("server_main_path")
    if not main_path:
        return
    title_slug = state["api_title"].lower().replace(" ", "-")
    config = {
        "mcpServers": {
            title_slug: {
                "command": "python",
                "args": [main_path.replace("\\", "/")],
                "env": {"API_BASE_URL": "http://localhost"}
            }
        }
    }
    state["connection_config"] = config


def _auto_start_server():
    """Auto-start the MCP server subprocess after forge completes."""
    main_path = state.get("server_main_path")
    if not main_path or not Path(main_path).exists():
        return
    try:
        proc = subprocess.Popen(
            [sys.executable, main_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**os.environ, "API_BASE_URL": "http://localhost"},
        )
        state["mcp_process"] = proc
    except Exception:
        pass


@app.route("/api/server/info")
def server_info():
    proc = state.get("mcp_process")
    running = proc is not None and proc.poll() is None
    return jsonify({
        "status": "running" if running else ("ready" if state.get("server_main_path") else "idle"),
        "pid": proc.pid if (proc and proc.poll() is None) else None,
        "server_path": state.get("server_main_path"),
        "connection_config": state.get("connection_config", {}),
        "tools": state.get("server_tools", []),
        "terminal_command": f"python {state['server_main_path']}" if state.get("server_main_path") else None,
    })


@app.route("/api/server/stop", methods=["POST"])
def server_stop():
    _kill_mcp()
    return jsonify({"status": "stopped"})


@app.route("/api/server/start", methods=["POST"])
def server_start():
    _auto_start_server()
    proc = state.get("mcp_process")
    if proc and proc.poll() is None:
        return jsonify({"status": "running", "pid": proc.pid})
    return jsonify({"error": "Failed to start server."}), 500


@app.route("/api/reset", methods=["POST"])
def reset():
    reset_state()
    return jsonify({"status": "reset"})


# ============================================================
# Ollama Model Discovery
# ============================================================

@app.route("/api/ollama/models")
def ollama_models():
    try:
        resp = http_req.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in resp.json().get("models", [])]
        return jsonify({"models": models, "available": True})
    except Exception:
        return jsonify({"models": [], "available": False})


# ============================================================
# Chat — MCP + LLM Integration
# ============================================================

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message."}), 400

    server_path = state.get("server_main_path")
    if not server_path or not Path(server_path).exists():
        return jsonify({"error": "MCP server not available. Complete the forge first."}), 400

    llm_config = {
        "provider": data.get("provider", "ollama"),
        "model": data.get("model", "qwen3.5:2b"),
        "api_key": data.get("api_key", ""),
    }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_chat(message, server_path, llm_config))
        loop.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "reply": f"Pipeline error: {e}", "tool_call": None}), 500


async def _run_chat(prompt, server_path, llm_config):
    """Connect to MCP server, query LLM, execute tools if needed."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path],
        env={**os.environ, "API_BASE_URL": "http://localhost"},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_resp = await session.list_tools()
            tools = tools_resp.tools

            # Store tool info for UI
            state["server_tools"] = [
                {"name": t.name, "description": t.description, "schema": t.inputSchema}
                for t in tools
            ]

            # Format for LLM
            tools_desc = "\n".join(
                f"- {t.name}: {t.description} (Schema: {json.dumps(t.inputSchema)})"
                for t in tools
            )

            sys_prompt = (
                f"You are a data analyst agent with these tools:\n{tools_desc}\n\n"
                f"User query: {prompt}\n\n"
                f"If you need a tool, reply ONLY with raw JSON: "
                f'{{"tool": "name", "args": {{...}}}}\n'
                f"Otherwise answer naturally."
            )

            # Step 1: Ask LLM
            llm_reply = _query_llm(sys_prompt, llm_config)

            # Step 2: Parse for tool call
            tool_call = None
            try:
                cleaned = llm_reply.strip().strip("```json").strip("```").strip()
                parsed = json.loads(cleaned)
                if "tool" in parsed:
                    tool_name = parsed["tool"]
                    tool_args = parsed.get("args", {})
                    tool_call = {"name": tool_name, "args": tool_args}

                    # Step 3: Execute tool via MCP
                    result = await session.call_tool(tool_name, arguments=tool_args)
                    result_text = "\n".join(c.text for c in result.content)

                    # Step 4: Synthesize
                    synth_prompt = (
                        f"User query: {prompt}\n\n"
                        f"Tool '{tool_name}' returned:\n{result_text}\n\n"
                        f"Give a helpful natural language response."
                    )
                    final = _query_llm(synth_prompt, llm_config)
                    return {"reply": final, "tool_call": tool_call, "tool_result": result_text[:2000]}

            except (json.JSONDecodeError, KeyError):
                pass

            return {"reply": llm_reply, "tool_call": None, "tool_result": None}


def _query_llm(prompt, config):
    """Route to Ollama or cloud LLM via LiteLLM."""
    provider = config.get("provider", "ollama")
    model = config.get("model", "")

    if provider == "ollama":
        try:
            resp = http_req.post(
                "http://localhost:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=120,
            )
            data = resp.json()
            if "error" in data:
                return f"Ollama error: {data['error']}"
            return data.get("response", "No response from Ollama.")
        except http_req.ConnectionError:
            return "Ollama is not running. Start the Ollama application first."
        except Exception as e:
            return f"Ollama query failed: {e}"
    else:
        try:
            messages = [{"role": "user", "content": prompt}]
            resp = litellm.completion(
                model=model,
                messages=messages,
                api_key=config.get("api_key", ""),
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"LLM API error: {e}"


# ============================================================
# Launch
# ============================================================

if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  MCP SERVER FOUNDRY — Web UI")
    print(f"  http://localhost:{PORT}")
    print(f"{'='*50}\n")

    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(host="127.0.0.1", port=PORT, debug=False)

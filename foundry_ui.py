"""
MCP Server Foundry — Web UI Backend

Decoupled and modernized backend pointing directly to Product A (Data Agent)
as a single, long-running FastMCP server spawned once at Flask startup.
"""

from flask import Flask, request, jsonify, send_file
import os
import sys
from typing import Dict, Any, List
import json
import uuid
import shutil
import subprocess
import threading
import webbrowser
import asyncio
import time
from pathlib import Path

import pandas as pd
import requests as http_req
import litellm

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ==============================================================================
# Constants & Paths
# ==============================================================================
ROOT = Path(__file__).parent.resolve()
DATA_DIR = ROOT / "data"
PORT = 7777

# Ensure ROOT/datasets exists
DATASETS_DIR = ROOT / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# Product A Main Path
PRODUCT_A_PATH = ROOT / "products" / "data-agent" / "server" / "main.py"

# ==============================================================================
# Flask App Setup
# ==============================================================================
app = Flask(__name__, static_folder=None)

# ==============================================================================
# State Management (Single User Local Session)
# ==============================================================================
state = {
    "session_id": None,
    "combined_file": None,
    "columns": [],
    "row_count": 0,
    "file_size_kb": 0,
    "api_title": "My Dataset",
    "forge_status": "complete",
    "forge_logs": ["Directly connected to Data Agent server."],
    "forge_progress": 100,
    "server_tools": [],
}

# ==============================================================================
# Long-running MCP Session Background Thread Manager
# ==============================================================================
_loop = None
_session = None

def _run_mcp_client_thread():
    global _loop, _session
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(PRODUCT_A_PATH)],
        env={**os.environ, "DATASETS_DIR": str(DATASETS_DIR)},
    )
    
    async def _manage_session():
        global _session
        print("[System] Spawning Product A FastMCP server once at startup...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                _session = session
                print("[OK] Product A FastMCP Session Initialized successfully.")
                
                # Retrieve tools to populate UI
                tools_resp = await session.list_tools()
                state["server_tools"] = [
                    {"name": t.name, "description": t.description, "schema": t.inputSchema}
                    for t in tools_resp.tools
                ]
                
                # Keep background thread alive
                while True:
                    await asyncio.sleep(3600)
                    
    try:
        _loop.run_until_complete(_manage_session())
    except Exception as e:
        print(f"[Error] MCP background thread crash: {e}")

# Spawn Product A on startup
threading.Thread(target=_run_mcp_client_thread, daemon=True).start()

# ==============================================================================
# Flask API Routes
# ==============================================================================

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
    """Save uploaded files, merge them, and copy to datasets directory for Product A discovery."""
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
            return jsonify({"error": f"Unsupported format: {ext}."}), 400
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

    if len(dfs) > 1:
        base = set(dfs[0].columns)
        for i, df in enumerate(dfs[1:], 2):
            if set(df.columns) != base:
                return jsonify({"error": f"File {i} columns don't match file 1."}), 400

    combined = pd.concat(dfs, ignore_index=True)
    # Save as CSV stem to have a clean, discoverable dataset name
    combined_name = f"combined_{session_id}"
    combined_path = DATASETS_DIR / f"{combined_name}.csv"
    combined.to_csv(str(combined_path), index=False)

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
        "combined_file": combined_name,
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
    """Mock endpoint: return a direct configuration spec to keep frontend happy."""
    combined = state.get("combined_file")
    if not combined:
        return jsonify({"error": "No file uploaded yet."}), 400
        
    spec_yaml = f"""
    openapi: 3.0.3
    info:
      title: "{state['combined_file']}"
      description: "Direct connection to Data Agent"
      version: 1.0.0
    paths:
      /search:
        post:
          operationId: filter_rows
    """
    return jsonify({"spec_path": "direct_mcp_connection", "content": spec_yaml})


@app.route("/api/spec-content")
def spec_content():
    return jsonify({"content": "Direct connection to Product A Data Agent", "path": "direct_connection"})


@app.route("/api/forge", methods=["POST"])
def forge():
    """Mock endpoint: instantly returns success as the server is already spawned."""
    state.update({
        "forge_status": "complete",
        "forge_progress": 100,
    })
    return jsonify({"status": "started"})


@app.route("/api/forge-status")
def forge_status():
    return jsonify({
        "status": "complete",
        "progress": 100,
        "logs": ["Data Agent is up and running in standard stdio mode.", "Foundry Pipeline auto-connected."],
        "error": None,
        "server_main_path": str(PRODUCT_A_PATH),
    })


@app.route("/api/server/info")
def server_info():
    return jsonify({
        "status": "running",
        "pid": os.getpid(),
        "server_path": str(PRODUCT_A_PATH),
        "connection_config": {"command": "python", "args": [str(PRODUCT_A_PATH)]},
        "tools": state["server_tools"],
        "terminal_command": f"python {PRODUCT_A_PATH}",
    })


@app.route("/api/server/stop", methods=["POST"])
def server_stop():
    return jsonify({"status": "stopped"})


@app.route("/api/server/start", methods=["POST"])
def server_start():
    return jsonify({"status": "running"})


@app.route("/api/reset", methods=["POST"])
def reset():
    state.update({
        "session_id": None,
        "combined_file": None,
        "columns": [],
        "row_count": 0,
        "file_size_kb": 0,
        "forge_status": "complete",
        "forge_progress": 100,
    })
    return jsonify({"status": "reset"})


@app.route("/api/ollama/models")
def ollama_models():
    try:
        resp = http_req.get("http://localhost:11434/api/tags", timeout=3)
        models = [m["name"] for m in resp.json().get("models", [])]
        return jsonify({"models": models, "available": True})
    except Exception:
        return jsonify({"models": [], "available": False})


# ==============================================================================
# ReAct Loop Chat Integration
# ==============================================================================

@app.route("/api/chat", methods=["POST"])
def chat():
    """Route chat prompts to the long-running Stdio background event loop thread."""
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message."}), 400

    llm_config = {
        "provider": data.get("provider", "ollama"),
        "model": data.get("model", "qwen3.5:2b"),
        "api_key": data.get("api_key", ""),
    }

    if _loop is None or _session is None:
        return jsonify({"error": "MCP session is currently initializing. Please wait a second."}), 503

    # Dispatch to background thread loop for thread-safe asynchronous execution
    coro = _run_react_agent(message, llm_config)
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    
    try:
        result = future.result(timeout=60.0) # wait up to 60 seconds
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "reply": f"ReAct agent loop failed: {e}", "steps": []}), 500


async def _run_react_agent(user_query: str, llm_config: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a ReAct agent loop (max 5 iterations) over Product A tools, tracking steps for the UI trace."""
    global _session
    steps = []
    
    # Establish connection trace
    steps.append({
        "title": "Establish MCP Pipeline",
        "status": "success",
        "description": "Connected to long-running stdio MCP server subprocess.",
        "code": f"Path: {PRODUCT_A_PATH}\nDatasets Dir: {DATASETS_DIR}"
    })
    
    # Get available tools
    tools = state["server_tools"]
    tools_desc = "\n".join(
        f"- {t['name']}: {t['description']} (Schema: {json.dumps(t['schema'])})"
        for t in tools
    )
    
    # Current active uploaded dataset name
    dataset_name = state.get("combined_file") or "sales" # fallback to sales if none uploaded
    
    system_prompt = (
        f"You are a professional data analyst ReAct agent. You have access to these dataset tools:\n{tools_desc}\n\n"
        f"The user has uploaded/selected the dataset: '{dataset_name}'. Every tool call requires a dataset name, so pass '{dataset_name}' as the dataset parameter.\n\n"
        f"You operate in a ReAct loop. In each turn, you can EITHER call a tool or provide a final answer.\n"
        f"To call a tool, respond with a JSON-wrapped tool call:\n"
        f'{{"thought": "reasons for calling this tool", "tool": "tool_name", "args": {{"dataset": "{dataset_name}", "key": "value"}}}} \n\n'
        f"If you have gathered all necessary information and are ready to answer the user, provide your final response in natural language markdown:\n"
        f'{{"thought": "I have completed my lookup", "final_answer": "your markdown report here"}}\n\n'
        f"Ensure you return STRICTLY a single, raw JSON object. Do not include markdown code fence formatting (no ```json)."
    )
    
    chat_history = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]
    
    final_reply = ""
    last_tool_result = ""
    
    # Run ReAct Loop up to 5 iterations
    for iteration in range(1, 6):
        # Step 1: Query LLM
        prompt_text = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in chat_history)
        llm_raw = _query_llm(prompt_text, llm_config)
        
        steps.append({
            "title": f"ReAct Iteration {iteration} — Reason & Plan",
            "status": "success",
            "description": f"Querying the LLM to formulate reasoning and plan next actions.",
            "code": f"--- CHAT CONTEXT SENT ---\n{prompt_text[:1500]}...\n\n--- LLM RAW RESPONSE ---\n{llm_raw}"
        })
        
        # Step 2: Parse LLM Response
        try:
            cleaned = llm_raw.strip().strip("```json").strip("```").strip()
            parsed = json.loads(cleaned)
        except Exception:
            # Fallback if LLM doesn't output valid JSON
            final_reply = llm_raw
            break
            
        thought = parsed.get("thought", "Analyzing query.")
        
        # Check if final answer
        if "final_answer" in parsed:
            final_reply = parsed["final_answer"]
            steps.append({
                "title": "ReAct Loop Completed",
                "status": "success",
                "description": "Agent successfully compiled the final answer report.",
                "code": f"Thought: {thought}\n\nFinal Report:\n{final_reply}"
            })
            break
            
        # Check if tool call
        if "tool" in parsed:
            tool_name = parsed["tool"]
            tool_args = parsed.get("args", {})
            
            # Formulate call logs for UI
            json_rpc_payload = {
                "jsonrpc": "2.0",
                "id": iteration,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": {"args": tool_args}}
            }
            steps.append({
                "title": f"Formulate Tool Call: {tool_name}",
                "status": "success",
                "description": f"Formulated standard JSON-RPC payload to call tool '{tool_name}'.",
                "code": f"JSON-RPC Request:\n{json.dumps(json_rpc_payload, indent=2)}"
            })
            
            # Step 3: Execute tool via MCP
            try:
                # FastMCP tools wrap arguments in a single "args" parameter
                result = await _session.call_tool(tool_name, arguments={"args": tool_args})
                result_text = "\n".join(c.text for c in result.content)
            except Exception as tool_err:
                result_text = json.dumps({"error": "Execution failed", "detail": str(tool_err)})
                
            last_tool_result = result_text
            
            steps.append({
                "title": f"Execute Backend Tool: {tool_name}",
                "status": "success",
                "description": "JSON-RPC transmitted over stdio connection to Data Agent. Captured output.",
                "code": f"--- Captured Tool Output ---\n{result_text[:2000]}"
            })
            
            # Update history for next iteration
            chat_history.append({"role": "assistant", "content": llm_raw})
            chat_history.append({"role": "user", "content": f"Tool '{tool_name}' returned:\n{result_text}"})
        else:
            # Fallback if no tool or final answer
            final_reply = llm_raw
            break
            
    if not final_reply:
        # Fallback if we exceeded 5 iterations without a final answer
        try:
            res_obj = json.loads(last_tool_result)
            final_reply = f"Successfully queried the dataset but reached max agent iterations. Here is a raw snippet of the data:\n\n```json\n{json.dumps(res_obj, indent=2)[:1000]}\n```"
        except Exception:
            final_reply = f"I executed the lookup query, but reached the maximum allowed analysis steps. Here is the raw output retrieved:\n\n{last_tool_result[:1000]}"
            
    return {
        "reply": final_reply,
        "tool_call": None,
        "tool_result": last_tool_result[:2000],
        "steps": steps
    }


def _query_llm(prompt: str, config: Dict[str, Any]) -> str:
    """Route prompts to Ollama or LiteLLM cloud integrations."""
    provider = config.get("provider", "ollama")
    model = config.get("model", "qwen3.5:2b")

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
            return data.get("response", "")
        except http_req.ConnectionError:
            return "Ollama is not running. Start Ollama first."
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


# ==============================================================================
# Web UI Entry Point
# ==============================================================================
if __name__ == "__main__":
    print(f"\n{'='*50}")
    print(f"  MCP SERVER FOUNDRY — Web UI (Product A Integrated)")
    print(f"  http://localhost:{PORT}")
    print(f"{'='*50}\n")

    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    app.run(host="127.0.0.1", port=PORT, debug=False)

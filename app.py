import streamlit as st
import subprocess
import os
import shutil
import json
import asyncio
import requests
from pathlib import Path

# Try to import MCP and LLM libraries, graceful degradation if not installed yet
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import litellm
except ImportError:
    st.error("Missing required dependencies: `pip install mcp litellm`")

async def run_mcp_agent(prompt, api_key, cloud_model, server_dir, ollama_model=None):
    server_script = os.path.join(server_dir, "server", "main.py")
    if not os.path.exists(server_script):
        return f"Error: MCP server main.py not found at {server_script}. Did the Forge complete successfully?"
        
    server_params = StdioServerParameters(
        command="python", 
        args=[server_script],
        env={**os.environ, "API_BASE_URL": "http://localhost:8080"}
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                
                # Format tools for the LLM prompt
                tools_desc = "\n".join([f"- {t.name}: {t.description} (Schema: {t.inputSchema})" for t in tools.tools])
                
                sys_prompt = f"""You are a data analyst agent. You have access to these tools:
{tools_desc}
User query: {prompt}
If you need to use a tool to answer the query, reply ONLY with a raw JSON object (no markdown blocks, no extra text) in this exact format: {{"tool": "name", "args": {{...}}}}
If you do not need a tool, just answer the query naturally."""
                
                llm_reply = ""
                # --- Step 1: Ask LLM what to do ---
                if cloud_model:
                    messages = [{"role": "system", "content": sys_prompt}]
                    resp = litellm.completion(
                        model=cloud_model,
                        messages=messages,
                        api_key=api_key
                    )
                    llm_reply = resp.choices[0].message.content
                else:
                    url = "http://localhost:11434/api/generate"
                    payload = {"model": ollama_model, "prompt": sys_prompt, "stream": False}
                    try:
                        resp = requests.post(url, json=payload).json()
                        if "error" in resp:
                            return f"Ollama Error: {resp['error']} (Try running `ollama pull {ollama_model}` in your terminal)"
                        llm_reply = resp['response']
                    except requests.exceptions.ConnectionError:
                        return "Ollama is not running. Please start the Ollama application."
                    except Exception as e:
                        return f"Ollama query failed: {e}"
                
                # --- Step 2: Parse LLM Intent ---
                try:
                    # Attempt to parse as tool call
                    llm_reply_clean = llm_reply.strip().strip('```json').strip('```').strip()
                    tool_req = json.loads(llm_reply_clean)
                    if "tool" in tool_req:
                        tool_name = tool_req["tool"]
                        tool_args = tool_req.get("args", {})
                        
                        # --- Step 3: Execute MCP Tool ---
                        tool_result = await session.call_tool(tool_name, arguments=tool_args)
                        result_text = "\n".join([c.text for c in tool_result.content])
                        
                        # --- Step 4: Final LLM Synthesis ---
                        final_prompt = f"User query: {prompt}\n\nThe tool '{tool_name}' returned this raw data:\n{result_text}\n\nPlease provide a helpful, natural language response based on this data."
                        
                        if cloud_model:
                            messages.append({"role": "assistant", "content": llm_reply})
                            messages.append({"role": "user", "content": final_prompt})
                            resp = litellm.completion(
                                model=cloud_model,
                                messages=messages,
                                api_key=api_key
                            )
                            return resp.choices[0].message.content
                        else:
                            payload["prompt"] = final_prompt
                            resp = requests.post(url, json=payload).json()
                            if "error" in resp:
                                return f"Ollama Error: {resp['error']}"
                            return resp['response']
                            
                except json.JSONDecodeError:
                    # LLM decided not to use a tool, return its natural answer
                    return llm_reply
                    
    except Exception as e:
        return f"MCP Agent Pipeline Error: {e}"

st.set_page_config(page_title="MCP SERVER FOUNDRY", layout="wide", initial_sidebar_state="expanded")

FUTURISTIC_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;700&display=swap');

/* Base Theme overrides */
.stApp {
    background-color: #050505;
    color: #a0aec0;
    font-family: 'Space Grotesk', sans-serif;
    background-image: 
        linear-gradient(rgba(0, 243, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0, 243, 255, 0.03) 1px, transparent 1px);
    background-size: 30px 30px;
}
/* Cyberpunk glowing accents */
h1, h2, h3 {
    color: #00f3ff !important;
    text-shadow: 0 0 15px rgba(0,243,255,0.4);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
}
/* Buttons */
.stButton>button {
    background: rgba(0, 243, 255, 0.05);
    color: #00f3ff;
    border: 1px solid #00f3ff;
    box-shadow: 0 0 10px rgba(0,243,255,0.1), inset 0 0 10px rgba(0,243,255,0.05);
    transition: all 0.3s ease;
    border-radius: 2px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.stButton>button:hover {
    background: #00f3ff;
    color: #000;
    box-shadow: 0 0 20px rgba(0,243,255,0.8);
    border-color: #00f3ff;
}
/* Inputs */
.stTextInput>div>div>input {
    background-color: rgba(0,0,0,0.8);
    color: #00f3ff;
    border: 1px solid #1a202c;
    border-radius: 2px;
}
.stTextInput>div>div>input:focus {
    border-color: #00f3ff;
    box-shadow: 0 0 10px rgba(0,243,255,0.3);
}
.stSelectbox>div>div>div {
    background-color: rgba(0,0,0,0.8);
    color: #00f3ff;
    border-color: #1a202c;
}
/* Chat Interface */
.stChatMessage {
    background-color: rgba(5, 5, 5, 0.7);
    border: 1px solid #1a202c;
    border-left: 3px solid #00f3ff;
    border-radius: 4px;
    padding: 1rem;
    backdrop-filter: blur(10px);
    margin-bottom: 10px;
}
.stChatInputContainer {
    border: 1px solid rgba(0,243,255,0.5);
    box-shadow: 0 0 15px rgba(0,243,255,0.1);
    border-radius: 4px;
    background: rgba(0,0,0,0.9);
}
hr {
    border-color: #00f3ff;
    opacity: 0.2;
}
[data-testid="stSidebar"] {
    background-color: rgba(5,5,5,0.95);
    border-right: 1px solid rgba(0,243,255,0.2);
}
</style>
"""
st.markdown(FUTURISTIC_CSS, unsafe_allow_html=True)

# --- UI HIERARCHY ---
st.title("MCP SERVER FOUNDRY // DATA AGENT")
st.markdown("> SYNTHESIZE CSV/EXCEL ARTIFACTS INTO SENTIENT DATA NODES.")

# --- SIDEBAR FOR CONFIG ---
with st.sidebar:
    st.header("SYS_CONFIG_MATRIX")
    llm_backend = st.selectbox(
        "Select LLM Backend",
        ["Cloud API (LiteLLM)", "Ollama (Local)"],
        index=0
    )
    
    api_key = ""
    cloud_model = None
    ollama_model = None
    
    if llm_backend == "Cloud API (LiteLLM)":
        cloud_model = st.text_input("LiteLLM Model String", value="gemini/gemini-3.1-pro-preview", help="e.g., anthropic/claude-3-opus, openai/gpt-4o, gemini/gemini-1.5-pro")
        api_key = st.text_input("Provider API Key", type="password", help="Your API key is never stored.")
        
        # Diagnostic button for Google API specifically
        if api_key and "gemini" in cloud_model.lower() and st.button("Check Available Gemini Models"):
            try:
                import requests
                models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                models_resp = requests.get(models_url).json()
                if "models" in models_resp:
                    available = [m["name"] for m in models_resp["models"] if "generateContent" in m.get("supportedGenerationMethods", [])]
                    st.info(f"Your API key has access to:\n" + "\n".join(f"- `{m}`" for m in available))
                else:
                    st.error(f"API Error: {models_resp}")
            except Exception as e:
                st.error(f"Failed to fetch models: {e}")
                
    else:
        ollama_model = st.text_input("Ollama Model Name", value="qwen3.5:2b", help="Ensure you have run `ollama pull <model>` beforehand.")
    
    if st.button("Reset Session"):
        st.session_state.clear()
        st.rerun()

# --- STEP 1: FILE UPLOAD ---
st.subheader("PHASE 1: UPLOAD DATA CHUNK")
uploaded_file = st.file_uploader("INITIALIZE UPLINK (CSV/XLSX)", type=["csv", "xlsx", "xls"])

if uploaded_file:
    # Ensure directories exist
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    if "upload_id" not in st.session_state or st.session_state.get("last_upload_name") != uploaded_file.name:
        import uuid
        st.session_state.upload_id = uuid.uuid4().hex[:6]
        st.session_state.last_upload_name = uploaded_file.name
        # Reset data_ready when a new file is uploaded
        st.session_state.data_ready = False
        st.session_state.server_dir = ""
        
    short_id = st.session_state.upload_id
    raw_name = uploaded_file.name.split('.')[0]
    ext = Path(uploaded_file.name).suffix
    unique_filename = f"{raw_name}_{short_id}{ext}"
    
    file_path = data_dir / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    st.success(f"File '{uploaded_file.name}' initialized as Node: {short_id}.")

    # --- STEP 2: BACKEND PIPELINE ---
    if not st.session_state.data_ready:
        if st.button("INITIATE FORGE SEQUENCE"):
            with st.status("ESTABLISHING BACKEND NEURAL NET...", expanded=True) as status:
                try:
                    # A. Generate YAML
                    st.write("1/3 COMPILING OPENAPI SCHEMATIC...")
                    subprocess.run(["python", "data/auto_spec_generator.py", str(file_path)], check=True)
                    
                    base_name = unique_filename.split('.')[0].lower().replace(" ", "_").replace("-", "_")
                    spec_path = Path(f"foundry/specs/{base_name}_api.yaml")
                    server_dir = Path(f"foundry/output/{base_name}-server")
                    
                    # B. Forge Server
                    st.write("2/3 FORGING MCP NODE VIA IBM BOB PROTOCOL...")
                    subprocess.run([
                        "python", "foundry/forge_recipe.py", 
                        "--input", str(spec_path), 
                        "--output", str(server_dir), 
                        "--auto-approve"
                    ], check=True)
                    
                    st.write("3/3 BACKEND SYSTEMS ONLINE!")
                    st.session_state.server_dir = str(server_dir)
                    st.session_state.data_ready = True
                    status.update(label="FORGE SEQUENCE OPTIMAL.", state="complete", expanded=False)
                    st.rerun()
                except Exception as e:
                    status.update(label="Pipeline Failed", state="error", expanded=True)
                    st.error(f"Error during execution: {e}")

    # --- STEP 3: CHAT INTERFACE ---
    if st.session_state.data_ready:
        st.divider()
        st.subheader("PHASE 2: NEURAL LINK INTERFACE")
        
        if cloud_model and not api_key:
            st.warning("⚠️ CRITICAL: PROVIDER API KEY MISSING IN SYS_CONFIG.")
        else:
            if "messages" not in st.session_state:
                st.session_state.messages = [{"role": "assistant", "content": "SYSTEM ONLINE. MCP server uplink established. Awaiting query execution..."}]

            # Display chat history
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # Input field
            if prompt := st.chat_input("TRANSMIT QUERY..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    with st.spinner("EXECUTING MCP PROTOCOL..."):
                        # Execute the true async agent pipeline
                        response = asyncio.run(
                            run_mcp_agent(prompt, api_key, cloud_model, st.session_state.server_dir, ollama_model)
                        )
                        st.markdown(response)
                
                st.session_state.messages.append({"role": "assistant", "content": response})

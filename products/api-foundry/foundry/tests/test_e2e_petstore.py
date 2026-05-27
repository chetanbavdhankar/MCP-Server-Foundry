import os
import sys
import shutil
import pytest
import asyncio
from pathlib import Path

# Add api-foundry root and foundry package to path
foundry_root = Path(__file__).resolve().parents[2]
if str(foundry_root) not in sys.path:
    sys.path.insert(0, str(foundry_root))
if str(foundry_root / "foundry") not in sys.path:
    sys.path.insert(0, str(foundry_root / "foundry"))

from forge_recipe import run_pipeline

@pytest.mark.asyncio
async def test_petstore_e2e_generation(tmp_path):
    """End-to-end test for Product B: OpenAPI spec to FastMCP server generation and validation."""
    spec_path = foundry_root / "foundry" / "specs" / "petstore.yaml"
    output_dir = tmp_path / "petstore-server"
    
    # Run the generator pipeline end-to-end
    context = await run_pipeline(
        spec_path=str(spec_path),
        output_dir=str(output_dir),
        verbose=True,
        auto_approve=True
    )
    
    assert not context.errors, f"Pipeline errors: {context.errors}"
    
    # Assert generated files exist
    server_dir = output_dir / "server"
    assert (server_dir / "main.py").exists(), "main.py not generated"
    assert (server_dir / "validation_models.py").exists(), "validation_models.py not generated"
    assert (server_dir / "test_server.py").exists(), "test_server.py not generated"
    
    # Temporarily append generated server directory to path for dynamic import
    sys.path.insert(0, str(server_dir))
    try:
        # Import the dynamically generated server
        from main import mcp
        
        # 1. Verify registered tools list
        tools = await mcp.list_tools()
        tool_names = [t.name for t in tools]
        assert "getPetById" in tool_names
        assert "createPet" in tool_names
        
        # 2. Call a tool with bad input (passing a dict to a required string argument petId)
        # Pydantic will fail validation and throw a ValidationError
        from mcp.server.fastmcp.exceptions import ToolError
        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool("getPetById", arguments={"petId": {"invalid_struct": 123}})
            
        assert exc_info is not None
        assert "validation error" in str(exc_info.value)
        
        # 3. Spawn the server process, list tools, and call one tool with bad input, asserting JSON-RPC error code -32602
        import json
        
        env = os.environ.copy()
        env["API_KEY"] = "test-api-key"
        
        server_main_path = server_dir / "main.py"
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(server_main_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        try:
            async def send_request(req):
                proc.stdin.write((json.dumps(req) + "\n").encode())
                await proc.stdin.drain()
                try:
                    line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=3.0)
                    if not line_bytes:
                        raise ValueError("Server returned EOF")
                    return json.loads(line_bytes.decode().strip())
                except asyncio.TimeoutError:
                    # Non-blocking read of stderr if available to help diagnose
                    try:
                        err_bytes = await asyncio.wait_for(proc.stderr.readline(), timeout=0.5)
                        err_msg = err_bytes.decode().strip() if err_bytes else ""
                    except Exception:
                        err_msg = "Unknown error"
                    raise TimeoutError(f"Timeout waiting for server response. Stderr: {err_msg}")
                
            # A. Handshake (initialize)
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            init_res = await send_request(init_req)
            assert "result" in init_res, f"Initialization failed: {init_res}"
            
            # B. List tools
            list_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            list_res = await send_request(list_req)
            assert "result" in list_res, f"List tools failed: {list_res}"
            tool_names = [t["name"] for t in list_res["result"]["tools"]]
            assert "getPetById" in tool_names
            
            # C. Call tool with bad input (passing non-dict arguments to trigger -32602)
            call_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "getPetById",
                    "arguments": "not-a-dict"
                }
            }
            call_res = await send_request(call_req)
            assert "error" in call_res, f"Expected error response, got: {call_res}"
            error_code = call_res["error"]["code"]
            assert error_code == -32602, f"Expected error code -32602 for invalid params, got {error_code}"
        finally:
            try:
                proc.terminate()
                await proc.wait()
            except Exception:
                pass
            
    finally:
        sys.path.remove(str(server_dir))
        # Clear imported main and validation_models from sys.modules to prevent caching collisions
        sys.modules.pop("main", None)
        sys.modules.pop("validation_models", None)



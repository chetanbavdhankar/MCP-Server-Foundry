#!/usr/bin/env python3
"""
Test script to verify MCP server handshake and tool listing.

This script sends MCP protocol messages to the generated server
and validates the responses.
"""

import json
import subprocess
import sys


def send_mcp_request(process, request):
    """Send an MCP request and get the response."""
    request_json = json.dumps(request) + "\n"
    process.stdin.write(request_json.encode())
    process.stdin.flush()
    
    response_line = process.stdout.readline().decode().strip()
    return json.loads(response_line)


def test_initialize(process):
    """Test the initialize handshake."""
    print("Testing initialize handshake...")
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    response = send_mcp_request(process, request)
    
    assert response.get("jsonrpc") == "2.0", "Invalid JSON-RPC version"
    assert response.get("id") == 1, "Invalid response ID"
    assert "result" in response, "No result in response"
    assert "serverInfo" in response["result"], "No serverInfo in result"
    
    print(f"  [OK] Server: {response['result']['serverInfo']['name']}")
    return True


def test_list_tools(process):
    """Test the tools/list method."""
    print("Testing tools/list...")
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list"
    }
    
    response = send_mcp_request(process, request)
    
    assert response.get("jsonrpc") == "2.0", "Invalid JSON-RPC version"
    assert response.get("id") == 2, "Invalid response ID"
    assert "result" in response, "No result in response"
    assert "tools" in response["result"], "No tools in result"
    
    tools = response["result"]["tools"]
    print(f"  [OK] Found {len(tools)} tools")
    
    for tool in tools:
        print(f"    - {tool['name']}: {tool['description']}")
    
    return len(tools) > 0


def main():
    """Run all tests."""
    server_path = "output/test-api/server/main.py"
    
    print("="*60)
    print("MCP SERVER TEST SUITE")
    print("="*60)
    print(f"Testing server: {server_path}\n")
    
    # Start the server process
    try:
        process = subprocess.Popen(
            [sys.executable, server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Run tests
        tests_passed = 0
        tests_total = 2
        
        try:
            if test_initialize(process):
                tests_passed += 1
            
            if test_list_tools(process):
                tests_passed += 1
        
        finally:
            process.terminate()
            process.wait(timeout=2)
        
        print("\n" + "="*60)
        print(f"RESULTS: {tests_passed}/{tests_total} tests passed")
        print("="*60)
        
        return 0 if tests_passed == tests_total else 1
        
    except Exception as e:
        print(f"\n[FAIL] Test execution failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob

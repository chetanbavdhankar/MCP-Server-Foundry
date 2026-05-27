"""Tests for M5 Documentation Generation."""
import pytest
from pathlib import Path

from agents.documenter import DocumenterAgent
from core.agent_interface import AgentContext, AgentExecutionError


class TestDocumenterAgent:
    @pytest.mark.asyncio
    async def test_requires_plan(self, tmp_path):
        agent = DocumenterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = None
        ctx.generated_code = {"main.py": "code"}
        with pytest.raises(AgentExecutionError, match="plan"):
            await agent.execute(ctx)

    @pytest.mark.asyncio
    async def test_requires_generated_code(self, tmp_path):
        agent = DocumenterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = {"api_info": {"title": "T"}, "endpoints_by_tag": {}}
        ctx.generated_code = None
        with pytest.raises(AgentExecutionError, match="code"):
            await agent.execute(ctx)

    @pytest.mark.asyncio
    async def test_generates_all_documentation_files(self, tmp_path):
        agent = DocumenterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = {
            "api_info": {"title": "Test API Service", "version": "1.0.0"},
            "authentication": {
                "env_vars": [
                    {"key": "API_KEY", "description": "Bearer token for API auth"}
                ]
            },
            "endpoints_by_tag": {
                "items": [{
                    "path": "/items",
                    "method": "POST",
                    "operation_id": "createItem",
                    "summary": "Create list item",
                    "parameters": [
                        {"name": "category", "in": "query", "required": False,
                         "schema": {"type": "string"}},
                    ],
                    "request_body": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["title"],
                                    "properties": {
                                        "title": {"type": "string"},
                                        "quantity": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    },
                }]
            },
        }
        ctx.generated_code = {
            "main.py": "code",
            "test_server.py": "async def test_1(): pass\nasync def test_2(): pass"
        }
        ctx.test_results = {"test_count": 2}

        result = await agent.execute(ctx)

        # Verify README.md exists and contains API Details, Env Vars, and Integration Guides
        readme_file = tmp_path / "server" / "README.md"
        assert readme_file.exists()
        readme_content = readme_file.read_text(encoding="utf-8")
        assert "Test API Service" in readme_content
        assert "API_KEY" in readme_content
        assert "createItem" in readme_content
        assert "claude_desktop_config.json" in readme_content
        assert "2" in readme_content

        # Verify docs/tool_reference.md exists and has schema description
        ref_file = tmp_path / "server" / "docs" / "tool_reference.md"
        assert ref_file.exists()
        ref_content = ref_file.read_text(encoding="utf-8")
        assert "createItem" in ref_content
        assert "category" in ref_content
        assert "title" in ref_content

        # Verify run_server.sh exists and is Unix line-ended
        sh_file = tmp_path / "server" / "run_server.sh"
        assert sh_file.exists()
        sh_content = sh_file.read_text(encoding="utf-8")
        assert "python3 main.py" in sh_content
        assert "\r\n" not in sh_content

        # Verify run_server.bat exists and is Windows line-ended
        bat_file = tmp_path / "server" / "run_server.bat"
        assert bat_file.exists()
        bat_content = bat_file.read_text(encoding="utf-8")
        assert "python main.py" in bat_content
        assert b"\r\n" in bat_file.read_bytes()

        # Check that files were registered in generated_code context
        assert "README.md" in result.generated_code
        assert "docs/tool_reference.md" in result.generated_code
        assert "run_server.sh" in result.generated_code
        assert "run_server.bat" in result.generated_code

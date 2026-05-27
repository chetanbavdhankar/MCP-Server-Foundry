"""Tests for M4 Adversarial Test Suite Generation."""
import pytest
from pathlib import Path

from agents.tester import (
    TesterAgent,
    _to_class_name,
    _to_safe_name,
    _build_valid_args,
    _find_first_string_param,
    _get_required_params,
)
from core.agent_interface import AgentContext, AgentExecutionError


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestToClassName:
    def test_kebab(self):
        assert _to_class_name("get-user") == "GetUser"

    def test_snake(self):
        assert _to_class_name("list_tasks") == "ListTasks"

    def test_mixed(self):
        assert _to_class_name("create-new_item") == "CreateNewItem"

    def test_single(self):
        assert _to_class_name("initialize") == "Initialize"


class TestToSafeName:
    def test_kebab_to_snake(self):
        assert _to_safe_name("get-user") == "get_user"


class TestBuildValidArgs:
    def test_string_param(self):
        tool = {"input_schema": {"properties": {"name": {"type": "string"}}, "required": ["name"]}}
        args = _build_valid_args(tool)
        assert isinstance(args["name"], str)

    def test_integer_param(self):
        tool = {"input_schema": {"properties": {"count": {"type": "integer"}}, "required": []}}
        args = _build_valid_args(tool)
        assert isinstance(args["count"], int)

    def test_enum_param(self):
        tool = {"input_schema": {"properties": {"status": {"type": "string", "enum": ["a", "b"]}}, "required": []}}
        args = _build_valid_args(tool)
        assert args["status"] == "a"

    def test_email_format(self):
        tool = {"input_schema": {"properties": {"email": {"type": "string", "format": "email"}}, "required": []}}
        args = _build_valid_args(tool)
        assert "@" in args["email"]

    def test_respects_minimum(self):
        tool = {"input_schema": {"properties": {"n": {"type": "integer", "minimum": 5}}, "required": []}}
        args = _build_valid_args(tool)
        assert args["n"] >= 5


class TestFindFirstStringParam:
    def test_finds_string(self):
        tool = {"input_schema": {"properties": {"id": {"type": "integer"}, "name": {"type": "string"}}, "required": []}}
        assert _find_first_string_param(tool) == "name"

    def test_skips_enum(self):
        tool = {"input_schema": {"properties": {"status": {"type": "string", "enum": ["a"]}}, "required": []}}
        assert _find_first_string_param(tool) is None

    def test_no_string(self):
        tool = {"input_schema": {"properties": {"id": {"type": "integer"}}, "required": []}}
        assert _find_first_string_param(tool) is None


class TestGetRequiredParams:
    def test_extracts_required(self):
        tool = {"input_schema": {
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }}
        params = _get_required_params(tool)
        assert len(params) == 1
        assert params[0]["name"] == "a"
        assert params[0]["wrong_type_value"] is not None


# ---------------------------------------------------------------------------
# TesterAgent execution
# ---------------------------------------------------------------------------

class TestTesterAgent:
    @pytest.mark.asyncio
    async def test_requires_plan(self, tmp_path):
        agent = TesterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = None
        ctx.generated_code = {"main.py": "code"}
        with pytest.raises(AgentExecutionError, match="plan"):
            await agent.execute(ctx)

    @pytest.mark.asyncio
    async def test_requires_generated_code(self, tmp_path):
        agent = TesterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = {"api_info": {"title": "T"}, "endpoints_by_tag": {}}
        ctx.generated_code = None
        with pytest.raises(AgentExecutionError, match="code"):
            await agent.execute(ctx)

    @pytest.mark.asyncio
    async def test_generates_test_file(self, tmp_path):
        agent = TesterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = {
            "api_info": {"title": "Test", "version": "1.0"},
            "authentication": {"env_vars": ["API_KEY"]},
            "endpoints_by_tag": {
                "items": [{
                    "path": "/items",
                    "method": "GET",
                    "operation_id": "listItems",
                    "summary": "List items",
                    "parameters": [
                        {"name": "limit", "in": "query", "required": False,
                         "schema": {"type": "integer", "minimum": 1}},
                    ],
                    "request_body": None,
                }]
            },
        }
        ctx.generated_code = {"main.py": "code"}

        result = await agent.execute(ctx)

        test_file = tmp_path / "server" / "test_server.py"
        assert test_file.exists()
        content = test_file.read_text(encoding="utf-8")
        assert "TestProtocol" in content
        assert "TestToolListitemsHappyPath" in content
        assert "TestInjectionPrevention" in content
        assert "test_valid_call_returns_success" in content
        assert "test_server.py" in result.generated_code

    @pytest.mark.asyncio
    async def test_populates_test_results(self, tmp_path):
        agent = TesterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = {
            "api_info": {"title": "T", "version": "1"},
            "authentication": {"env_vars": []},
            "endpoints_by_tag": {
                "a": [{
                    "path": "/a",
                    "method": "POST",
                    "operation_id": "createA",
                    "summary": "Create",
                    "parameters": [],
                    "request_body": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    },
                }]
            },
        }
        ctx.generated_code = {"main.py": "code"}

        result = await agent.execute(ctx)

        assert result.test_results is not None
        assert result.test_results["test_count"] > 0
        assert "protocol" in result.test_results["categories"]
        assert "happy_path" in result.test_results["categories"]
        assert "injection" in result.test_results["categories"]

    @pytest.mark.asyncio
    async def test_generates_injection_tests_for_string_params(self, tmp_path):
        agent = TesterAgent()
        ctx = AgentContext(spec_path="x", output_dir=str(tmp_path))
        ctx.plan = {
            "api_info": {"title": "T", "version": "1"},
            "authentication": {"env_vars": []},
            "endpoints_by_tag": {
                "x": [{
                    "path": "/x",
                    "method": "GET",
                    "operation_id": "getX",
                    "summary": "Get",
                    "parameters": [
                        {"name": "query", "in": "query", "required": False,
                         "schema": {"type": "string"}},
                    ],
                    "request_body": None,
                }]
            },
        }
        ctx.generated_code = {"main.py": "code"}

        result = await agent.execute(ctx)
        content = (tmp_path / "server" / "test_server.py").read_text(encoding="utf-8")
        assert "SQL_PAYLOADS" in content
        assert "SHELL_PAYLOADS" in content
        assert "test_injection_in_getX" in content
        assert result.test_results["injectable_tools"] == ["getX"]

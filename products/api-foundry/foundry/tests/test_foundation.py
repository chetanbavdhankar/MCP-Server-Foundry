"""Tests for M1 Foundation: spec parser, agent interface, and orchestrator."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.spec_parser import (
    load_spec,
    validate_spec,
    normalize_spec,
    parse_endpoint,
    extract_auth_requirements,
    SpecParserError,
)
from core.agent_interface import AgentContext, Agent, StandaloneAgent, AgentExecutionError
from core.orchestrator import Orchestrator, PipelineBuilder


# ---------------------------------------------------------------------------
# Spec Parser
# ---------------------------------------------------------------------------

MINIMAL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "list_items",
                "summary": "List items",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}


class TestLoadSpec:
    def test_load_yaml(self, tmp_path):
        f = tmp_path / "spec.yaml"
        f.write_text("openapi: '3.0.0'\ninfo:\n  title: T\n  version: '1'\npaths: {}\n")
        data = load_spec(str(f))
        assert data["openapi"] == "3.0.0"

    def test_load_json(self, tmp_path):
        f = tmp_path / "spec.json"
        f.write_text(json.dumps(MINIMAL_SPEC))
        data = load_spec(str(f))
        assert data["info"]["title"] == "Test"

    def test_file_not_found(self):
        with pytest.raises(SpecParserError, match="not found"):
            load_spec("/nonexistent/path.yaml")

    def test_unsupported_format(self, tmp_path):
        f = tmp_path / "spec.txt"
        f.write_text("hello")
        with pytest.raises(SpecParserError, match="Unsupported"):
            load_spec(str(f))

    def test_invalid_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(":\n  : :\n    [invalid")
        with pytest.raises(SpecParserError, match="YAML"):
            load_spec(str(f))


class TestValidateSpec:
    def test_valid_spec(self):
        validate_spec(MINIMAL_SPEC)  # should not raise

    def test_missing_openapi(self):
        with pytest.raises(SpecParserError, match="openapi"):
            validate_spec({"info": {"title": "T"}, "paths": {}})

    def test_missing_paths(self):
        with pytest.raises(SpecParserError, match="paths"):
            validate_spec({"openapi": "3.0.0", "info": {"title": "T"}})

    def test_wrong_version(self):
        with pytest.raises(SpecParserError, match="Unsupported"):
            validate_spec({"openapi": "2.0", "info": {"title": "T"}, "paths": {}})

    def test_missing_title(self):
        with pytest.raises(SpecParserError, match="title"):
            validate_spec({"openapi": "3.0.0", "info": {"version": "1"}, "paths": {}})


class TestNormalizeSpec:
    def test_parses_endpoints(self):
        parsed = normalize_spec(MINIMAL_SPEC)
        assert parsed.title == "Test"
        assert len(parsed.endpoints) == 1
        assert parsed.endpoints[0].method == "GET"
        assert parsed.endpoints[0].path == "/items"

    def test_default_server(self):
        parsed = normalize_spec(MINIMAL_SPEC)
        assert parsed.servers[0]["url"] == "http://localhost"

    def test_extracts_schemas(self):
        spec = {**MINIMAL_SPEC, "components": {"schemas": {"Item": {"type": "object"}}}}
        parsed = normalize_spec(spec)
        assert "Item" in parsed.schemas

    def test_skips_non_method_keys(self):
        spec = {
            **MINIMAL_SPEC,
            "paths": {
                "/x": {
                    "summary": "ignored",
                    "get": {"operationId": "get_x", "responses": {}},
                }
            },
        }
        parsed = normalize_spec(spec)
        assert len(parsed.endpoints) == 1


class TestParseEndpoint:
    def test_basic_endpoint(self):
        ep = parse_endpoint("/foo", "post", {"summary": "Create"}, MINIMAL_SPEC)
        assert ep.path == "/foo"
        assert ep.method == "POST"
        assert ep.summary == "Create"

    def test_auto_operation_id(self):
        ep = parse_endpoint("/bar", "get", {}, MINIMAL_SPEC)
        assert "get" in ep.operation_id
        assert "bar" in ep.operation_id


class TestExtractAuth:
    def test_api_key(self):
        spec = normalize_spec({
            **MINIMAL_SPEC,
            "components": {
                "securitySchemes": {"key": {"type": "apiKey", "name": "X-Key", "in": "header"}}
            },
        })
        auth = extract_auth_requirements(spec)
        assert auth["required"] is True
        assert "API_KEY" in auth["env_vars"]

    def test_no_auth(self):
        spec = normalize_spec(MINIMAL_SPEC)
        auth = extract_auth_requirements(spec)
        assert auth["required"] is False
        assert auth["env_vars"] == []


# ---------------------------------------------------------------------------
# Agent Interface
# ---------------------------------------------------------------------------

class TestAgentContext:
    def test_defaults(self):
        ctx = AgentContext(spec_path="spec.yaml")
        assert ctx.spec_path == "spec.yaml"
        assert ctx.plan is None
        assert len(ctx.execution_id) > 0
        assert len(ctx.timestamp) > 0
        assert ctx.errors == []

    def test_add_trace(self):
        ctx = AgentContext(spec_path="x")
        ctx.add_trace("TestAgent", "started")
        assert len(ctx.agent_trace) == 1
        assert ctx.agent_trace[0]["agent"] == "TestAgent"
        assert "timestamp" in ctx.agent_trace[0]

    def test_add_error(self):
        ctx = AgentContext(spec_path="x")
        ctx.add_error("TestAgent", "something broke")
        assert len(ctx.errors) == 1
        assert ctx.errors[0]["error"] == "something broke"

    def test_to_dict(self):
        ctx = AgentContext(spec_path="x")
        d = ctx.to_dict()
        assert d["spec_path"] == "x"
        assert d["has_plan"] is False
        assert d["error_count"] == 0


class TestAgentExecutionError:
    def test_message(self):
        err = AgentExecutionError("Builder", "failed hard")
        assert "Builder" in str(err)
        assert "failed hard" in str(err)

    def test_details(self):
        err = AgentExecutionError("A", "msg", details={"key": "val"})
        assert err.details == {"key": "val"}


# ---------------------------------------------------------------------------
# Orchestrator + PipelineBuilder
# ---------------------------------------------------------------------------

class DummyAgent(StandaloneAgent):
    """Test agent that marks context."""

    def __init__(self, name: str = "Dummy", fail: bool = False):
        super().__init__(name)
        self._fail = fail

    async def execute(self, context: AgentContext) -> AgentContext:
        self.log_start(context)
        if self._fail:
            raise AgentExecutionError(self.name, "intentional failure")
        context.plan = {"dummy": True}
        self.log_complete(context)
        return context


class TestPipelineBuilder:
    def test_build_single_agent(self):
        pipeline = PipelineBuilder().add_agent(DummyAgent()).set_output_dir("./out").build()
        assert len(pipeline.agents) == 1

    def test_build_empty_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            PipelineBuilder().build()

    def test_auto_approve_flag(self):
        pipeline = PipelineBuilder().add_agent(DummyAgent()).auto_approve(True).build()
        assert pipeline.auto_approve is True


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_successful_pipeline(self, tmp_path):
        orch = Orchestrator([DummyAgent()], str(tmp_path), auto_approve=True)
        ctx = AgentContext(spec_path="spec.yaml", output_dir=str(tmp_path))
        result = await orch.execute_pipeline(ctx)
        assert result.plan == {"dummy": True}
        assert len(result.agent_trace) >= 2  # started + completed
        # Provenance should be saved
        assert (tmp_path / "provenance.json").exists()
        assert (tmp_path / "audit.jsonl").exists()

    @pytest.mark.asyncio
    async def test_failing_agent(self, tmp_path):
        orch = Orchestrator([DummyAgent(fail=True)], str(tmp_path), auto_approve=True)
        ctx = AgentContext(spec_path="spec.yaml", output_dir=str(tmp_path))
        with pytest.raises(AgentExecutionError, match="intentional"):
            await orch.execute_pipeline(ctx)

    @pytest.mark.asyncio
    async def test_audit_log_written(self, tmp_path):
        orch = Orchestrator([DummyAgent()], str(tmp_path), auto_approve=True)
        ctx = AgentContext(spec_path="spec.yaml", output_dir=str(tmp_path))
        await orch.execute_pipeline(ctx)
        audit_file = tmp_path / "audit.jsonl"
        lines = audit_file.read_text().strip().split("\n")
        events = [json.loads(l)["event"] for l in lines]
        assert "pipeline.start" in events
        assert "agent.start" in events
        assert "agent.complete" in events
        assert "pipeline.complete" in events

    @pytest.mark.asyncio
    async def test_provenance_contains_hashes(self, tmp_path):
        # Create a fake server file to hash
        server_dir = tmp_path / "server"
        server_dir.mkdir()
        (server_dir / "main.py").write_text("print('hi')")

        orch = Orchestrator([DummyAgent()], str(tmp_path), auto_approve=True)
        ctx = AgentContext(spec_path="spec.yaml", output_dir=str(tmp_path))
        await orch.execute_pipeline(ctx)

        prov = json.loads((tmp_path / "provenance.json").read_text())
        assert "main.py" in prov["generated_files"]
        assert len(prov["generated_files"]["main.py"]) == 64  # SHA-256

"""End-to-end integration test: runs the full Foundry pipeline against the test spec."""
import json
import pytest
from pathlib import Path

from core.agent_interface import AgentContext
from core.orchestrator import PipelineBuilder
from agents.architect import ArchitectAgent
from agents.builder import BuilderAgent


class TestFullPipeline:
    """Run the complete Architect → Builder pipeline and verify all artifacts."""

    @pytest.mark.asyncio
    async def test_pipeline_produces_all_artifacts(self, tmp_path):
        spec_path = Path(__file__).parent.parent / "specs" / "test_api.yaml"
        if not spec_path.exists():
            pytest.skip("test_api.yaml not found")

        output_dir = str(tmp_path / "output")
        ctx = AgentContext(spec_path=str(spec_path), output_dir=output_dir)

        pipeline = (
            PipelineBuilder()
            .add_agent(ArchitectAgent())
            .add_agent(BuilderAgent())
            .set_output_dir(output_dir)
            .auto_approve(True)
            .build()
        )

        result = await pipeline.execute_pipeline(ctx)

        # --- Plan assertions (Architect output) ---
        assert result.plan is not None
        assert "api_info" in result.plan
        assert "endpoints_by_tag" in result.plan
        plan_file = tmp_path / "output" / "plan.json"
        assert plan_file.exists()

        # --- Code assertions (Builder output) ---
        server_dir = tmp_path / "output" / "server"
        assert (server_dir / "main.py").exists()
        assert (server_dir / "error_schemas.py").exists()
        assert (server_dir / "audit_logger.py").exists()
        assert (server_dir / ".env.example").exists()

        # main.py should contain the API title
        main_code = (server_dir / "main.py").read_text()
        assert "Test API" in main_code

        # --- Governance assertions (M3 output) ---
        audit_file = tmp_path / "output" / "audit.jsonl"
        assert audit_file.exists()
        audit_lines = audit_file.read_text().strip().split("\n")
        events = [json.loads(l)["event"] for l in audit_lines]
        assert "pipeline.start" in events
        assert "pipeline.complete" in events
        assert "gate.approved" in events  # auto-approved

        provenance_file = tmp_path / "output" / "provenance.json"
        assert provenance_file.exists()
        prov = json.loads(provenance_file.read_text())
        assert prov["schema_version"] == "1.0.0"
        assert "main.py" in prov["generated_files"]
        assert prov["spec"]["sha256"] is not None
        assert len(prov["agents_executed"]) >= 2

        # --- Context assertions ---
        assert result.generated_code is not None
        assert len(result.generated_code) >= 4
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_pipeline_with_missing_spec_raises(self, tmp_path):
        """Pipeline should raise FileNotFoundError before any agent runs."""
        ctx = AgentContext(spec_path="/nonexistent.yaml", output_dir=str(tmp_path))
        pipeline = (
            PipelineBuilder()
            .add_agent(ArchitectAgent())
            .set_output_dir(str(tmp_path))
            .auto_approve(True)
            .build()
        )
        with pytest.raises(Exception):
            await pipeline.execute_pipeline(ctx)

"""Tests for M3 Governance Layer: audit logging, approval gates, provenance."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from core.audit import AuditLogger, AuditEvent, AuditSeverity, AuditEntry, compute_file_hash
from core.approval_gates import (
    gate_plan_review,
    gate_code_review,
    run_approval_gate,
    ApprovalDecision,
    GateRejectedError,
    _format_plan_summary,
    _format_code_summary,
)


# --- AuditLogger ---


class TestAuditLogger:
    """Tests for the structured audit logger."""

    def test_creates_log_file(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.PIPELINE_START, message="test")
        assert log_path.exists()

    def test_log_entry_is_valid_json(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.PIPELINE_START, message="test")

        line = log_path.read_text().strip()
        data = json.loads(line)
        assert data["event"] == "pipeline.start"
        assert data["execution_id"] == "exec-1"
        assert data["message"] == "test"

    def test_multiple_entries_are_separate_lines(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.AGENT_START, agent="Architect")
        logger.log(AuditEvent.AGENT_COMPLETE, agent="Architect")

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_severity_levels(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")

        logger.log(AuditEvent.SEMGREP_PASS, severity=AuditSeverity.INFO)
        logger.log(AuditEvent.SEMGREP_FAIL, severity=AuditSeverity.ERROR)

        lines = log_path.read_text().strip().split("\n")
        assert json.loads(lines[0])["severity"] == "INFO"
        assert json.loads(lines[1])["severity"] == "ERROR"

    def test_none_fields_omitted(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.PIPELINE_START)

        data = json.loads(log_path.read_text().strip())
        assert "agent" not in data
        assert "request_id" not in data
        assert "duration_ms" not in data

    def test_duration_ms_recorded(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.AGENT_COMPLETE, duration_ms=123.45)

        data = json.loads(log_path.read_text().strip())
        assert data["duration_ms"] == 123.45

    def test_in_memory_entries(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.PIPELINE_START)
        logger.log(AuditEvent.PIPELINE_COMPLETE)
        assert len(logger.entries) == 2

    def test_get_entries_by_event(self, tmp_path):
        log_path = tmp_path / "audit.jsonl"
        logger = AuditLogger(log_path, "exec-1")
        logger.log(AuditEvent.AGENT_START, agent="A")
        logger.log(AuditEvent.AGENT_COMPLETE, agent="A")
        logger.log(AuditEvent.AGENT_START, agent="B")

        starts = logger.get_entries_by_event(AuditEvent.AGENT_START)
        assert len(starts) == 2


# --- Approval Gates ---


class TestApprovalDecision:
    def test_bool_true(self):
        assert bool(ApprovalDecision(approved=True))

    def test_bool_false(self):
        assert not bool(ApprovalDecision(approved=False))


class TestAutoApprove:
    """Auto-approve mode skips interactive prompts."""

    def test_gate_plan_review_auto(self, tmp_path):
        audit = AuditLogger(tmp_path / "a.jsonl", "exec-1")
        plan = {
            "api_info": {"title": "Test", "version": "1.0", "base_url": "http://x"},
            "endpoints_by_tag": {},
            "authentication": {"required": False},
            "schemas": {},
        }
        decision = gate_plan_review(plan, audit, auto_approve=True)
        assert decision.approved
        # Should have logged GATE_PROMPT and GATE_APPROVED
        events = [e.event for e in audit.entries]
        assert "gate.prompt" in events
        assert "gate.approved" in events

    def test_gate_code_review_auto(self, tmp_path):
        audit = AuditLogger(tmp_path / "a.jsonl", "exec-1")
        code = {"main.py": "print('hello')\n"}
        decision = gate_code_review(code, True, audit, auto_approve=True)
        assert decision.approved


class TestInteractiveGate:
    """Interactive gate prompts — using mocked stdin."""

    @patch("core.approval_gates._prompt_user", return_value="y")
    def test_approve(self, mock_prompt, tmp_path):
        audit = AuditLogger(tmp_path / "a.jsonl", "exec-1")
        decision = run_approval_gate("Test Gate", "summary", audit)
        assert decision.approved

    @patch("core.approval_gates._prompt_user", side_effect=["n", ""])
    def test_reject(self, mock_prompt, tmp_path):
        audit = AuditLogger(tmp_path / "a.jsonl", "exec-1")
        with pytest.raises(GateRejectedError, match="Test Gate"):
            run_approval_gate("Test Gate", "summary", audit)

    @patch("core.approval_gates._prompt_user", side_effect=["d", "y"])
    def test_details_then_approve(self, mock_prompt, tmp_path):
        audit = AuditLogger(tmp_path / "a.jsonl", "exec-1")
        decision = run_approval_gate("Test Gate", "summary", audit)
        assert decision.approved
        assert mock_prompt.call_count == 2


# --- Formatting ---


class TestFormatting:
    def test_format_plan_summary(self):
        plan = {
            "api_info": {"title": "Stripe", "version": "2024-01", "base_url": "https://api.stripe.com"},
            "endpoints_by_tag": {
                "charges": [
                    {"method": "post", "path": "/v1/charges"},
                    {"method": "get", "path": "/v1/charges/{id}"},
                ]
            },
            "authentication": {"required": True, "env_vars": ["API_KEY"]},
            "schemas": {"Charge": {}, "Customer": {}},
        }
        output = _format_plan_summary(plan)
        assert "Stripe" in output
        assert "/v1/charges" in output
        assert "2 validation models" in output

    def test_format_code_summary(self):
        code = {"main.py": "a\nb\nc\n", "models.py": "x\n"}
        output = _format_code_summary(code)
        assert "main.py" in output
        assert "TOTAL" in output


# --- File Hashing ---


class TestFileHash:
    def test_compute_file_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = compute_file_hash(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_hash_changes_with_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h1 = compute_file_hash(f)
        f.write_text("world")
        h2 = compute_file_hash(f)
        assert h1 != h2

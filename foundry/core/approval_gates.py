"""
Human approval gates for the Foundry pipeline.

Provides interactive checkpoints where a human operator can review
and approve/reject pipeline artifacts before proceeding. Two gates:

  Gate 1 (post-Architect): Review the generated plan before building.
  Gate 2 (post-Builder):   Review generated code before deployment.

Gates can be bypassed with --auto-approve for CI/CD pipelines.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from core.audit import AuditLogger, AuditEvent, AuditSeverity


class ApprovalDecision:
    """Result of a human approval gate."""

    def __init__(self, approved: bool, reason: Optional[str] = None, reviewer: str = "operator"):
        self.approved = approved
        self.reason = reason
        self.reviewer = reviewer

    def __bool__(self) -> bool:
        return self.approved


class GateRejectedError(Exception):
    """Raised when a human operator rejects an approval gate."""

    def __init__(self, gate_name: str, reason: Optional[str] = None):
        self.gate_name = gate_name
        self.reason = reason
        msg = f"Gate '{gate_name}' rejected by operator"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


def _format_plan_summary(plan: Dict[str, Any]) -> str:
    """Render a human-readable summary of the Architect's plan."""
    lines = []
    api = plan.get("api_info", {})
    lines.append(f"  API:     {api.get('title', '?')} v{api.get('version', '?')}")
    lines.append(f"  Base:    {api.get('base_url', '?')}")

    endpoints = plan.get("endpoints_by_tag", {})
    total = sum(len(eps) for eps in endpoints.values())
    lines.append(f"  Tools:   {total} endpoints across {len(endpoints)} tags")

    for tag, eps in endpoints.items():
        lines.append(f"    [{tag}]")
        for ep in eps:
            lines.append(f"      {ep.get('method', '?').upper():6s} {ep.get('path', '?')}")

    auth = plan.get("authentication", {})
    if auth.get("required"):
        lines.append(f"  Auth:    required ({len(auth.get('env_vars', []))} env vars)")
    else:
        lines.append("  Auth:    none")

    schemas = plan.get("schemas", {})
    lines.append(f"  Schemas: {len(schemas)} validation models")

    return "\n".join(lines)


def _format_code_summary(generated_code: Dict[str, str]) -> str:
    """Render a human-readable summary of the Builder's output."""
    lines = []
    for filename, code in generated_code.items():
        loc = code.count("\n") + 1
        lines.append(f"  {filename:30s} {loc:>5} lines")
    total = sum(c.count("\n") + 1 for c in generated_code.values())
    lines.append(f"  {'TOTAL':30s} {total:>5} lines")
    return "\n".join(lines)


def _prompt_user(prompt: str) -> str:
    """Read a line from stdin with a prompt. Testable seam."""
    print(prompt, end="", file=sys.stderr, flush=True)
    return input()


def run_approval_gate(
    gate_name: str,
    summary: str,
    audit: AuditLogger,
    auto_approve: bool = False,
) -> ApprovalDecision:
    """
    Run an interactive approval gate.

    Args:
        gate_name: Human-readable gate identifier (e.g. "Plan Review")
        summary: Multi-line summary of the artifact to review
        audit: AuditLogger instance for recording the decision
        auto_approve: If True, skip prompt and approve automatically

    Returns:
        ApprovalDecision

    Raises:
        GateRejectedError: If the operator rejects
    """
    audit.log(
        AuditEvent.GATE_PROMPT,
        agent=gate_name,
        message=f"Approval gate '{gate_name}' activated",
    )

    if auto_approve:
        decision = ApprovalDecision(approved=True, reason="auto-approved")
        audit.log(
            AuditEvent.GATE_APPROVED,
            agent=gate_name,
            message="Auto-approved (--auto-approve flag)",
        )
        print(f"\n  [GATE] {gate_name}: auto-approved\n", file=sys.stderr)
        return decision

    # Print gate UI
    print(f"\n{'─' * 60}", file=sys.stderr)
    print(f"  APPROVAL GATE: {gate_name}", file=sys.stderr)
    print(f"{'─' * 60}", file=sys.stderr)
    print(summary, file=sys.stderr)
    print(f"{'─' * 60}", file=sys.stderr)

    while True:
        response = _prompt_user("  Approve? [y/n/d(etails)]: ").strip().lower()

        if response in ("y", "yes"):
            decision = ApprovalDecision(approved=True)
            audit.log(
                AuditEvent.GATE_APPROVED,
                agent=gate_name,
                message="Approved by operator",
            )
            print(f"  [GATE] {gate_name}: APPROVED ✓\n", file=sys.stderr)
            return decision

        elif response in ("n", "no"):
            reason = _prompt_user("  Reason (optional): ").strip() or None
            audit.log(
                AuditEvent.GATE_REJECTED,
                severity=AuditSeverity.WARN,
                agent=gate_name,
                message=f"Rejected by operator: {reason or 'no reason given'}",
            )
            raise GateRejectedError(gate_name, reason)

        elif response in ("d", "details"):
            print("\n  [Full artifact details will be shown here in future milestones]\n", file=sys.stderr)

        else:
            print("  Please enter y, n, or d.", file=sys.stderr)


def gate_plan_review(
    plan: Dict[str, Any],
    audit: AuditLogger,
    auto_approve: bool = False,
) -> ApprovalDecision:
    """Gate 1: Review the Architect's plan before building."""
    summary = _format_plan_summary(plan)
    return run_approval_gate("Plan Review", summary, audit, auto_approve)


def gate_code_review(
    generated_code: Dict[str, str],
    semgrep_passed: Optional[bool],
    audit: AuditLogger,
    auto_approve: bool = False,
) -> ApprovalDecision:
    """Gate 2: Review the Builder's output before deployment."""
    summary = _format_code_summary(generated_code)
    if semgrep_passed is not None:
        status = "PASSED ✓" if semgrep_passed else "FAILED ✗"
        summary += f"\n  Semgrep:  {status}"
    return run_approval_gate("Code Review", summary, audit, auto_approve)


# Made with Bob

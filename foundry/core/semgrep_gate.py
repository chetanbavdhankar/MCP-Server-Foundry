"""
Semgrep static analysis integration.

This module runs Semgrep scans on generated code as a build gate,
failing the build if security violations are detected.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class ViolationSeverity(Enum):
    """Severity levels for Semgrep violations."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class SemgrepViolation:
    """Represents a single Semgrep violation."""
    rule_id: str
    severity: ViolationSeverity
    message: str
    file_path: str
    line_number: int
    code_snippet: str
    fix: Optional[str] = None


@dataclass
class ScanResult:
    """Results from a Semgrep scan."""
    passed: bool
    violations: List[SemgrepViolation]
    errors: List[str]
    scan_time_seconds: float
    files_scanned: int


class SemgrepGate:
    """
    Runs Semgrep static analysis as a build gate.
    
    Scans generated code for security vulnerabilities and fails
    the build if ERROR-level violations are found.
    """
    
    def __init__(self, rules_path: Optional[Path] = None):
        """
        Initialize the Semgrep gate.
        
        Args:
            rules_path: Path to custom Semgrep rules (optional)
        """
        self.rules_path = rules_path
        self.scan_result: Optional[ScanResult] = None
    
    def run_semgrep_scan(self, code_dir: Path) -> ScanResult:
        """
        Run Semgrep scan on a directory.
        
        Args:
            code_dir: Directory containing code to scan
            
        Returns:
            ScanResult with violations and metadata
        """
        if not code_dir.exists():
            return ScanResult(
                passed=False,
                violations=[],
                errors=[f"Code directory not found: {code_dir}"],
                scan_time_seconds=0.0,
                files_scanned=0
            )
        
        # Build Semgrep command
        cmd = ["semgrep", "--json", "--quiet"]
        
        # Add rules
        if self.rules_path and self.rules_path.exists():
            cmd.extend(["--config", str(self.rules_path)])
        else:
            # Use default security rules
            cmd.extend(["--config", "auto"])
        
        # Add target directory
        cmd.append(str(code_dir))
        
        try:
            # Run Semgrep
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            # Parse output
            if result.stdout:
                scan_data = json.loads(result.stdout)
                violations = self._parse_violations(scan_data)
                
                # Check if scan passed (no ERROR-level violations)
                error_violations = [
                    v for v in violations 
                    if v.severity == ViolationSeverity.ERROR
                ]
                
                scan_result = ScanResult(
                    passed=len(error_violations) == 0,
                    violations=violations,
                    errors=[],
                    scan_time_seconds=scan_data.get("time", 0.0),
                    files_scanned=len(scan_data.get("results", []))
                )
            else:
                scan_result = ScanResult(
                    passed=True,
                    violations=[],
                    errors=[],
                    scan_time_seconds=0.0,
                    files_scanned=0
                )
            
            self.scan_result = scan_result
            return scan_result
            
        except subprocess.TimeoutExpired:
            return ScanResult(
                passed=False,
                violations=[],
                errors=["Semgrep scan timed out after 60 seconds"],
                scan_time_seconds=60.0,
                files_scanned=0
            )
        except FileNotFoundError:
            return ScanResult(
                passed=False,
                violations=[],
                errors=["Semgrep not found. Install with: pip install semgrep"],
                scan_time_seconds=0.0,
                files_scanned=0
            )
        except json.JSONDecodeError as e:
            return ScanResult(
                passed=False,
                violations=[],
                errors=[f"Failed to parse Semgrep output: {str(e)}"],
                scan_time_seconds=0.0,
                files_scanned=0
            )
        except Exception as e:
            return ScanResult(
                passed=False,
                violations=[],
                errors=[f"Semgrep scan failed: {str(e)}"],
                scan_time_seconds=0.0,
                files_scanned=0
            )
    
    def _parse_violations(self, scan_data: Dict[str, Any]) -> List[SemgrepViolation]:
        """
        Parse Semgrep JSON output into violation objects.
        
        Args:
            scan_data: Parsed JSON from Semgrep
            
        Returns:
            List of violations
        """
        violations = []
        
        for result in scan_data.get("results", []):
            # Map Semgrep severity to our enum
            severity_str = result.get("extra", {}).get("severity", "WARNING").upper()
            try:
                severity = ViolationSeverity[severity_str]
            except KeyError:
                severity = ViolationSeverity.WARNING
            
            violation = SemgrepViolation(
                rule_id=result.get("check_id", "unknown"),
                severity=severity,
                message=result.get("extra", {}).get("message", "No message"),
                file_path=result.get("path", "unknown"),
                line_number=result.get("start", {}).get("line", 0),
                code_snippet=result.get("extra", {}).get("lines", ""),
                fix=result.get("extra", {}).get("fix")
            )
            violations.append(violation)
        
        return violations
    
    def check_for_violations(self, scan_result: ScanResult) -> bool:
        """
        Check if there are any ERROR-level violations.
        
        Args:
            scan_result: Result from Semgrep scan
            
        Returns:
            True if no ERROR violations, False otherwise
        """
        return scan_result.passed
    
    def format_violations_report(self, violations: List[SemgrepViolation]) -> str:
        """
        Format violations into a human-readable report.
        
        Args:
            violations: List of violations
            
        Returns:
            Formatted report string
        """
        if not violations:
            return "✓ No violations found"
        
        lines = [
            "=" * 60,
            "SEMGREP VIOLATIONS DETECTED",
            "=" * 60,
            ""
        ]
        
        # Group by severity
        errors = [v for v in violations if v.severity == ViolationSeverity.ERROR]
        warnings = [v for v in violations if v.severity == ViolationSeverity.WARNING]
        infos = [v for v in violations if v.severity == ViolationSeverity.INFO]
        
        if errors:
            lines.append(f"ERRORS ({len(errors)}):")
            lines.append("-" * 60)
            for v in errors:
                lines.extend(self._format_violation(v))
            lines.append("")
        
        if warnings:
            lines.append(f"WARNINGS ({len(warnings)}):")
            lines.append("-" * 60)
            for v in warnings:
                lines.extend(self._format_violation(v))
            lines.append("")
        
        if infos:
            lines.append(f"INFO ({len(infos)}):")
            lines.append("-" * 60)
            for v in infos:
                lines.extend(self._format_violation(v))
            lines.append("")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _format_violation(self, violation: SemgrepViolation) -> List[str]:
        """Format a single violation."""
        lines = [
            f"[{violation.severity.value}] {violation.rule_id}",
            f"  File: {violation.file_path}:{violation.line_number}",
            f"  Message: {violation.message}",
        ]
        
        if violation.code_snippet:
            lines.append(f"  Code: {violation.code_snippet.strip()}")
        
        if violation.fix:
            lines.append(f"  Fix: {violation.fix}")
        
        lines.append("")
        return lines


def run_security_scan(code_dir: Path, rules_path: Optional[Path] = None) -> ScanResult:
    """
    Convenience function to run a security scan.
    
    Args:
        code_dir: Directory to scan
        rules_path: Optional custom rules
        
    Returns:
        Scan result
    """
    gate = SemgrepGate(rules_path)
    return gate.run_semgrep_scan(code_dir)


def check_build_gate(scan_result: ScanResult) -> bool:
    """
    Check if the build should pass based on scan results.
    
    Args:
        scan_result: Result from Semgrep scan
        
    Returns:
        True if build should pass, False if it should fail
    """
    return scan_result.passed and not scan_result.errors


# Made with Bob
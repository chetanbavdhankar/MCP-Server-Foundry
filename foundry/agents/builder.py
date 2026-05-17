"""
Builder Agent (Security-Enhanced) - MCP server code generation with security features.

This agent takes the plan from the Architect and generates a complete,
production-grade MCP server with:
- Strict input validation using Pydantic models
- Secret detection and environment variable externalization
- Structured error handling
- Static analysis with Semgrep
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.agent_interface import StandaloneAgent, AgentContext, AgentExecutionError
from core.validation import generate_validation_models
from core.security import SecretDetector, EnvironmentVariableGenerator
from core.semgrep_gate import run_security_scan


class BuilderAgent(StandaloneAgent):
    """
    Unified Builder agent responsible for secure code generation.
    
    This agent:
    1. Reads the plan from the Architect agent
    2. Detects secrets and externalizes them to environment variables
    3. Generates Pydantic validation models from OpenAPI schemas
    4. Generates MCP server code using security-enhanced templates
    5. Generates error response schemas
    6. Runs Semgrep static analysis as a build gate
    7. Outputs a complete, secure, runnable server structure
    """
    
    def __init__(self, enable_semgrep: bool = True):
        super().__init__("Builder")
        
        self.enable_semgrep = enable_semgrep
        
        # Set up Jinja2 environment
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    async def execute(self, context: AgentContext) -> AgentContext:
        """
        Execute the security-enhanced builder agent logic.
        
        Args:
            context: Current execution context with plan
            
        Returns:
            Updated context with generated code
        """
        self.log_start(context)
        
        if not context.plan:
            raise AgentExecutionError(
                self.name,
                "No plan found in context. Architect agent must run first."
            )
        
        try:
            plan = context.plan
            
            print(f"  Generating secure MCP server for: {plan['api_info']['title']}")
            
            # Step 1: Detect secrets in the spec
            print(f"  [Security] Detecting secrets in specification...")
            secret_detector = SecretDetector()
            spec_data = context.spec_data if context.spec_data else {}
            secrets = secret_detector.detect_secrets_in_spec(spec_data)
            print(f"  [Security] Found {len(secrets)} secrets to externalize")
            
            # Step 2: Generate environment variable template
            print(f"  [Security] Generating .env.example...")
            env_generator = EnvironmentVariableGenerator()
            env_vars = env_generator.extract_auth_env_vars(plan["authentication"], secrets)
            env_template = env_generator.generate_env_template(env_vars)
            
            # Step 3: Generate validation models from schemas
            print(f"  [Security] Generating Pydantic validation models...")
            validation_models_code = generate_validation_models(plan.get("schemas", {}))
            
            # Step 4: Prepare tool definitions from plan
            tools = self._prepare_tools(plan)
            print(f"  Prepared {len(tools)} tool definitions")
            
            # Step 5: Generate error schemas
            print(f"  Generating error response schemas...")
            error_schemas_code = self._generate_error_schemas()
            
            # Step 6: Generate main server file
            print(f"  Generating main server code...")
            server_code = self._generate_server(plan, tools)

            # Step 6b: Generate runtime audit logger (M3)
            print(f"  [Governance] Generating runtime audit logger...")
            audit_logger_code = self._generate_audit_logger(plan.get("sensitive_fields", []))
            
            # Step 7: Create output directory structure
            output_dir = Path(context.output_dir)
            server_dir = output_dir / "server"
            server_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 8: Write all files
            files_written = self._write_files(
                server_dir,
                server_code,
                validation_models_code,
                error_schemas_code,
                env_template,
                audit_logger_code,
            )
            
            print(f"  Generated {files_written} files")
            
            # Step 9: Run Semgrep scan
            scan_result = None
            if self.enable_semgrep:
                print(f"  [Security] Running Semgrep static analysis...")
                scan_result = self._run_semgrep_scan(server_dir)
                
                if not scan_result.passed:
                    self._handle_semgrep_violations(scan_result)
                else:
                    print(f"  [Security] [OK] Semgrep scan passed - no violations found")
            
            # Store generated code in context
            context.generated_code = {
                "main.py": server_code,
                "validation_models.py": validation_models_code,
                "error_schemas.py": error_schemas_code,
                "audit_logger.py": audit_logger_code,
                ".env.example": env_template,
            }
            
            self.log_complete(context, {
                "tools_generated": len(tools),
                "files_created": files_written,
                "secrets_externalized": len(secrets),
                "validation_models": len(plan.get("schemas", {})),
                "semgrep_passed": scan_result.passed if (self.enable_semgrep and scan_result) else None,
                "output_dir": str(server_dir)
            })
            
            return context
            
        except Exception as e:
            error_msg = f"Failed to generate code: {str(e)}"
            self.log_error(context, error_msg)
            raise AgentExecutionError(self.name, error_msg)
    
    def _prepare_tools(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare tool definitions from the plan.
        
        Args:
            plan: The plan from Architect agent
            
        Returns:
            List of tool definitions
        """
        tools = []
        
        for tag, endpoints in plan["endpoints_by_tag"].items():
            for endpoint in endpoints:
                tool = self._endpoint_to_tool(endpoint, tag, plan.get("schemas", {}))
                tools.append(tool)
        
        return tools
    
    def _endpoint_to_tool(self, endpoint: Dict[str, Any], tag: str, schemas: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert an endpoint definition to an MCP tool definition.
        
        Args:
            endpoint: Endpoint from the plan
            tag: Tag/category for the endpoint
            schemas: Available schemas for validation model lookup
            
        Returns:
            Tool definition dictionary
        """
        # Create tool name from operation ID
        tool_name = endpoint["operation_id"].replace("_", "-")
        
        # Build input schema from parameters and request body
        input_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # Track if we have a validation model for this tool
        validation_model = None
        
        # Add path and query parameters
        for param in endpoint.get("parameters", []):
            param_name = param.get("name", "unknown")
            param_schema = param.get("schema", {"type": "string"})
            
            input_schema["properties"][param_name] = {
                "type": param_schema.get("type", "string"),
                "description": param.get("description", "")
            }
            
            if param.get("required", False):
                input_schema["required"].append(param_name)
        
        # Add request body properties if present
        if endpoint.get("request_body"):
            req_body = endpoint["request_body"]
            if "content" in req_body:
                json_content = req_body["content"].get("application/json", {})
                if "schema" in json_content:
                    schema = json_content["schema"]
                    
                    # Check if this references a named schema
                    if "$ref" in schema:
                        ref_name = schema["$ref"].split("/")[-1]
                        if ref_name in schemas:
                            validation_model = ref_name
                    
                    if "properties" in schema:
                        input_schema["properties"].update(schema["properties"])
                    if "required" in schema:
                        input_schema["required"].extend(schema["required"])
        
        return {
            "name": tool_name,
            "description": endpoint.get("summary", f"{endpoint['method']} {endpoint['path']}"),
            "input_schema": input_schema,
            "endpoint": endpoint,
            "validation_model": validation_model
        }
    
    def _generate_error_schemas(self) -> str:
        """
        Generate error response schemas.
        
        Returns:
            Error schemas code as string
        """
        template = self.jinja_env.get_template("error_schemas.py.j2")
        return template.render()
    
    def _generate_audit_logger(self, sensitive_fields: List[str] = None) -> str:
        """
        Generate runtime audit logger for the MCP server.
        
        Returns:
            Audit logger code as string
        """
        template = self.jinja_env.get_template("audit_logger.py.j2")
        return template.render(sensitive_fields=sensitive_fields or [])
    
    def _generate_server(self, plan: Dict[str, Any], tools: List[Dict[str, Any]]) -> str:
        """
        Generate the main server code using security-enhanced templates.
        
        Args:
            plan: The plan from Architect agent
            tools: List of tool definitions
            
        Returns:
            Generated server code as string
        """
        # Use the secure template
        template = self.jinja_env.get_template("server_main_secure.py.j2")
        
        return template.render(
            api_title=plan["api_info"]["title"],
            api_version=plan["api_info"]["version"],
            api_description=plan["api_info"]["description"],
            base_url=plan["api_info"]["base_url"],
            tools=tools,
            auth_required=plan["authentication"]["required"],
            env_vars=plan["authentication"]["env_vars"],
            validation_models_import=len(plan.get("schemas", {})) > 0
        )
    
    def _write_files(
        self,
        server_dir: Path,
        server_code: str,
        validation_models_code: str,
        error_schemas_code: str,
        env_template: str,
        audit_logger_code: str,
    ) -> int:
        """
        Write all generated files to the output directory.
        
        Args:
            server_dir: Output directory
            server_code: Main server code
            validation_models_code: Validation models code
            error_schemas_code: Error schemas code
            env_template: Environment variable template
            
        Returns:
            Number of files written
        """
        files_written = 0
        
        # Write main server file
        main_file = server_dir / "main.py"
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(server_code)
        files_written += 1
        print(f"    [OK] {main_file}")
        
        # Write validation models if any schemas exist
        if validation_models_code and "class" in validation_models_code:
            validation_file = server_dir / "validation_models.py"
            with open(validation_file, 'w', encoding='utf-8') as f:
                f.write(validation_models_code)
            files_written += 1
            print(f"    [OK] {validation_file}")
        
        # Write error schemas
        error_file = server_dir / "error_schemas.py"
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(error_schemas_code)
        files_written += 1
        print(f"    [OK] {error_file}")
        
        # Write .env.example
        env_file = server_dir / ".env.example"
        with open(env_file, 'w', encoding='utf-8') as f:
            f.write(env_template)
        files_written += 1
        print(f"    [OK] {env_file}")

        # Write runtime audit logger (M3)
        audit_file = server_dir / "audit_logger.py"
        with open(audit_file, 'w', encoding='utf-8') as f:
            f.write(audit_logger_code)
        files_written += 1
        print(f"    [OK] {audit_file}")
        
        return files_written
    
    def _run_semgrep_scan(self, server_dir: Path) -> Any:
        """
        Run Semgrep static analysis on generated code.
        
        Args:
            server_dir: Directory containing generated code
            
        Returns:
            ScanResult object
        """
        rules_path = Path(__file__).parent.parent / ".semgrep" / "rules" / "mcp-security.yaml"
        
        try:
            scan_result = run_security_scan(server_dir, rules_path)
            return scan_result
        except Exception as e:
            print(f"    [Warning] Semgrep scan failed: {str(e)}")
            print(f"    [Warning] Continuing without static analysis")
            # Return a failing result if Semgrep fails to ensure safety
            from core.semgrep_gate import ScanResult
            return ScanResult(
                passed=False,
                violations=[],
                errors=[str(e)],
                scan_time_seconds=0.0,
                files_scanned=0
            )
    
    def _handle_semgrep_violations(self, scan_result: Any):
        """
        Handle Semgrep violations - fail the build if errors found.
        
        Args:
            scan_result: ScanResult from Semgrep scan
            
        Raises:
            AgentExecutionError: If ERROR-level violations found
        """
        from core.semgrep_gate import SemgrepGate, ViolationSeverity
        
        gate = SemgrepGate()
        report = gate.format_violations_report(scan_result.violations)
        
        # Count ERROR-level violations
        error_count = sum(
            1 for v in scan_result.violations 
            if v.severity == ViolationSeverity.ERROR
        )
        
        if error_count > 0:
            print(f"\n{report}\n")
            raise AgentExecutionError(
                self.name,
                f"Build failed: {error_count} ERROR-level security violations detected. "
                f"Fix the violations above and regenerate.",
                details={"violations": error_count, "report": report}
            )
        else:
            # Only warnings/info - log but don't fail
            print(f"    [Warning] {len(scan_result.violations)} non-critical violations found")
            if scan_result.violations:
                print(f"\n{report}\n")


# Made with Bob
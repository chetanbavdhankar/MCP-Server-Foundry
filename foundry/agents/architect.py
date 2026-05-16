"""
Architect Agent - OpenAPI spec analysis and planning.

This agent parses the OpenAPI specification, builds a dependency graph,
and creates a structured plan for code generation.
"""

import json
from pathlib import Path
from typing import Dict, Any

from core.agent_interface import StandaloneAgent, AgentContext, AgentExecutionError
from core.spec_parser import load_spec, normalize_spec, extract_auth_requirements


class ArchitectAgent(StandaloneAgent):
    """
    Architect agent responsible for spec parsing and planning.
    
    This agent:
    1. Loads and validates the OpenAPI specification
    2. Normalizes the spec into a structured format
    3. Analyzes endpoints, parameters, and dependencies
    4. Extracts authentication requirements
    5. Creates a structured plan for the Builder agent
    """
    
    def __init__(self):
        super().__init__("Architect")
    
    async def execute(self, context: AgentContext) -> AgentContext:
        """
        Execute the architect agent logic.
        
        Args:
            context: Current execution context
            
        Returns:
            Updated context with spec data and plan
        """
        self.log_start(context)
        
        try:
            # Load the OpenAPI specification
            print(f"  Loading spec from: {context.spec_path}")
            spec_data = load_spec(context.spec_path)
            context.spec_data = spec_data
            
            # Normalize the specification
            print(f"  Normalizing spec structure...")
            parsed_spec = normalize_spec(spec_data)
            
            print(f"  Found {len(parsed_spec.endpoints)} endpoints")
            print(f"  API: {parsed_spec.title} v{parsed_spec.version}")
            
            # Extract authentication requirements
            auth_info = extract_auth_requirements(parsed_spec)
            
            # Build the plan
            plan = self._build_plan(parsed_spec, auth_info)
            context.plan = plan
            
            # Save plan to output directory
            self._save_plan(plan, context.output_dir)
            
            self.log_complete(context, {
                "endpoints_found": len(parsed_spec.endpoints),
                "schemas_found": len(parsed_spec.schemas),
                "auth_required": auth_info["required"]
            })
            
            return context
            
        except Exception as e:
            error_msg = f"Failed to parse spec: {str(e)}"
            self.log_error(context, error_msg)
            raise AgentExecutionError(self.name, error_msg, {"spec_path": context.spec_path})
    
    def _build_plan(self, parsed_spec, auth_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a structured plan from the parsed spec.
        
        Args:
            parsed_spec: Normalized specification
            auth_info: Authentication requirements
            
        Returns:
            Plan dictionary for the Builder agent
        """
        # Group endpoints by tag
        endpoints_by_tag = {}
        for endpoint in parsed_spec.endpoints:
            tag = endpoint.tags[0] if endpoint.tags else "default"
            if tag not in endpoints_by_tag:
                endpoints_by_tag[tag] = []
            endpoints_by_tag[tag].append({
                "path": endpoint.path,
                "method": endpoint.method,
                "operation_id": endpoint.operation_id,
                "summary": endpoint.summary,
                "parameters": endpoint.parameters,
                "request_body": endpoint.request_body,
                "responses": endpoint.responses
            })
        
        plan = {
            "api_info": {
                "title": parsed_spec.title,
                "version": parsed_spec.version,
                "description": parsed_spec.description,
                "base_url": parsed_spec.servers[0]["url"] if parsed_spec.servers else "http://localhost"
            },
            "authentication": auth_info,
            "endpoints_by_tag": endpoints_by_tag,
            "schemas": parsed_spec.schemas,
            "generation_strategy": {
                "server_type": "mcp",
                "language": "python",
                "framework": "custom",
                "validation": "pydantic",
                "transport": "stdio"
            },
            "file_structure": {
                "server_dir": "server",
                "tools_dir": "server/tools",
                "schemas_dir": "server/schemas",
                "main_file": "server/main.py"
            }
        }
        
        return plan
    
    def _save_plan(self, plan: Dict[str, Any], output_dir: str):
        """Save the plan to a JSON file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        plan_file = output_path / "plan.json"
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan, f, indent=2)
        
        print(f"  Plan saved to: {plan_file}")

# Made with Bob

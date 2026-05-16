"""
Builder Agent - MCP server code generation.

This agent takes the plan from the Architect and generates a complete,
syntactically valid MCP server implementation.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.agent_interface import StandaloneAgent, AgentContext, AgentExecutionError


class BuilderAgent(StandaloneAgent):
    """
    Builder agent responsible for code generation.
    
    This agent:
    1. Reads the plan from the Architect agent
    2. Generates MCP server code using templates
    3. Creates tool handlers for each endpoint
    4. Outputs a complete, runnable server structure
    """
    
    def __init__(self):
        super().__init__("Builder")
        
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
        Execute the builder agent logic.
        
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
            
            print(f"  Generating MCP server for: {plan['api_info']['title']}")
            
            # Prepare tool definitions from plan
            tools = self._prepare_tools(plan)
            print(f"  Prepared {len(tools)} tool definitions")
            
            # Generate main server file
            server_code = self._generate_server(plan, tools)
            
            # Create output directory structure
            output_dir = Path(context.output_dir)
            server_dir = output_dir / "server"
            server_dir.mkdir(parents=True, exist_ok=True)
            
            # Write server file
            main_file = server_dir / "main.py"
            with open(main_file, 'w', encoding='utf-8') as f:
                f.write(server_code)
            
            print(f"  Generated server file: {main_file}")
            
            # Store generated code in context
            context.generated_code = {
                "main.py": server_code
            }
            
            self.log_complete(context, {
                "tools_generated": len(tools),
                "files_created": 1,
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
                tool = self._endpoint_to_tool(endpoint, tag)
                tools.append(tool)
        
        return tools
    
    def _endpoint_to_tool(self, endpoint: Dict[str, Any], tag: str) -> Dict[str, Any]:
        """
        Convert an endpoint definition to an MCP tool definition.
        
        Args:
            endpoint: Endpoint from the plan
            tag: Tag/category for the endpoint
            
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
                    if "properties" in schema:
                        input_schema["properties"].update(schema["properties"])
                    if "required" in schema:
                        input_schema["required"].extend(schema["required"])
        
        return {
            "name": tool_name,
            "description": endpoint.get("summary", f"{endpoint['method']} {endpoint['path']}"),
            "input_schema": input_schema,
            "endpoint": endpoint
        }
    
    def _generate_server(self, plan: Dict[str, Any], tools: List[Dict[str, Any]]) -> str:
        """
        Generate the main server code using templates.
        
        Args:
            plan: The plan from Architect agent
            tools: List of tool definitions
            
        Returns:
            Generated server code as string
        """
        template = self.jinja_env.get_template("server_main.py.j2")
        
        return template.render(
            api_title=plan["api_info"]["title"],
            api_version=plan["api_info"]["version"],
            api_description=plan["api_info"]["description"],
            base_url=plan["api_info"]["base_url"],
            tools=tools,
            auth_required=plan["authentication"]["required"],
            env_vars=plan["authentication"]["env_vars"]
        )

# Made with Bob

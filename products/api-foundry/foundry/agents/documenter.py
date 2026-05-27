"""
Documenter Agent — Milestone 5: Documentation Generation.

Generates a complete, beautiful documentation suite for the generated MCP server.
Features:
  1. Complete, premium README.md with environment variables, integration guides, and run scripts.
  2. Dedicated tool_reference.md manual detailing parameter schemas, constraints, and JSON request payloads.
  3. Linux/macOS run_server.sh launch script with auto-setup and env check.
  4. Windows run_server.bat launch script with auto-setup and env check.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import jinja2

from core.agent_interface import AgentContext, StandaloneAgent, AgentExecutionError


class DocumenterAgent(StandaloneAgent):
    """
    Generates developer documentation and launch recipes for the generated MCP server.

    Reads the plan, generated code, and test metadata from the context, and produces:
    - server/README.md
    - server/docs/tool_reference.md
    - server/run_server.sh
    - server/run_server.bat
    """

    def __init__(self):
        super().__init__("Documenter")
        template_dir = Path(__file__).parent.parent.parent / "templates"
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        """Generate and write the documentation and recipes."""
        self.log_start(context)

        plan = context.plan
        if not plan:
            raise AgentExecutionError(self.name, "No plan available — Architect must run first")

        generated_code = context.generated_code
        if not generated_code:
            raise AgentExecutionError(self.name, "No generated code — Builder must run first")

        # Reconstruct tool definitions from plan
        tools = self._prepare_tools(plan)
        print(f"  Generating documentation and launch recipes for {len(tools)} tools")

        # Extract environment variables and format details
        auth = plan.get("authentication", {})
        raw_env_vars = auth.get("env_vars", [])
        env_vars = []
        for var in raw_env_vars:
            if isinstance(var, str):
                env_vars.append({
                    "key": var,
                    "description": f"Target API authentication key mapping for {var}."
                })
            elif isinstance(var, dict):
                env_vars.append({
                    "key": var.get("key", ""),
                    "description": var.get("description", "Target API authentication key.")
                })

        # Get test count from context metadata or by parsing generated test file
        test_count = 0
        if context.test_results and "test_count" in context.test_results:
            test_count = context.test_results["test_count"]
        elif "test_server.py" in generated_code:
            test_code = generated_code["test_server.py"]
            test_count = len(re.findall(r"async def test_", test_code))

        # Absolute paths for integration guides
        output_dir = Path(context.output_dir)
        server_dir = output_dir / "server"
        server_dir.mkdir(parents=True, exist_ok=True)
        docs_dir = server_dir / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        main_py_abs = server_dir / "main.py"
        # Format slash for JSON config escaping
        server_path_slash = str(main_py_abs.resolve()).replace("\\", "/")

        # 1. Render and write README.md
        readme_template = self.jinja_env.get_template("server_readme.md.j2")
        readme_code = readme_template.render(
            api_title=plan["api_info"]["title"],
            tools=tools,
            env_vars=env_vars,
            test_count=test_count,
            server_path_slash=server_path_slash,
        )
        readme_file = server_dir / "README.md"
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(readme_code)
        context.generated_code["README.md"] = readme_code
        print(f"    [OK] {readme_file}")

        # 2. Render and write tool_reference.md
        ref_template = self.jinja_env.get_template("tool_reference.md.j2")
        ref_code = ref_template.render(
            api_title=plan["api_info"]["title"],
            tools=tools,
        )
        ref_file = docs_dir / "tool_reference.md"
        with open(ref_file, "w", encoding="utf-8") as f:
            f.write(ref_code)
        context.generated_code["docs/tool_reference.md"] = ref_code
        print(f"    [OK] {ref_file}")

        # 3. Render and write run_server.sh
        sh_template = self.jinja_env.get_template("run_server.sh.j2")
        sh_code = sh_template.render(
            api_title=plan["api_info"]["title"],
            env_vars=env_vars,
        )
        sh_file = server_dir / "run_server.sh"
        with open(sh_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(sh_code)
        context.generated_code["run_server.sh"] = sh_code
        print(f"    [OK] {sh_file}")

        # 4. Render and write run_server.bat
        bat_template = self.jinja_env.get_template("run_server.bat.j2")
        bat_code = bat_template.render(
            api_title=plan["api_info"]["title"],
            env_vars=env_vars,
        )
        bat_file = server_dir / "run_server.bat"
        with open(bat_file, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(bat_code)
        context.generated_code["run_server.bat"] = bat_code
        print(f"    [OK] {bat_file}")

        self.log_complete(context, {
            "readme_generated": True,
            "tool_reference_generated": True,
            "run_scripts_generated": True,
            "tools_documented": len(tools),
        })

        return context

    def _prepare_tools(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reconstruct tool list from plan (mirrors Builder/Tester _prepare_tools)."""
        tools = []
        for tag, endpoints in plan["endpoints_by_tag"].items():
            for endpoint in endpoints:
                tool_name = endpoint["operation_id"].replace("_", "-")

                input_schema = {"type": "object", "properties": {}, "required": []}

                for param in endpoint.get("parameters", []):
                    param_name = param.get("name", "unknown")
                    param_schema = param.get("schema", {"type": "string"})
                    input_schema["properties"][param_name] = {
                        "type": param_schema.get("type", "string"),
                        "description": param.get("description", ""),
                    }
                    if "enum" in param_schema:
                        input_schema["properties"][param_name]["enum"] = param_schema["enum"]
                    if "minimum" in param_schema:
                        input_schema["properties"][param_name]["minimum"] = param_schema["minimum"]
                    if "maximum" in param_schema:
                        input_schema["properties"][param_name]["maximum"] = param_schema["maximum"]
                    if "format" in param_schema:
                        input_schema["properties"][param_name]["format"] = param_schema["format"]
                    if param.get("required", False):
                        input_schema["required"].append(param_name)

                if endpoint.get("request_body"):
                    req_body = endpoint["request_body"]
                    if "content" in req_body:
                        json_content = req_body["content"].get("application/json", {})
                        if "schema" in json_content:
                            schema = json_content["schema"]
                            if "properties" in schema:
                                for pname, pdef in schema["properties"].items():
                                    input_schema["properties"][pname] = pdef
                            if "required" in schema:
                                input_schema["required"].extend(schema["required"])

                tools.append({
                    "name": tool_name,
                    "description": endpoint.get("summary", ""),
                    "input_schema": input_schema,
                    "endpoint": endpoint,
                })
        return tools


# Made with Bob

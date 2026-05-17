"""
Tester Agent — Milestone 4: Adversarial Test Suite Generation.

Generates a comprehensive pytest test suite for the generated MCP server.
Test categories:
  1. Protocol compliance (initialize, tools/list, error codes)
  2. Happy-path tool calls (valid inputs → success)
  3. Malformed input (missing/wrong-type required fields)
  4. Injection prevention (SQL, shell, prompt payloads)
"""

import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import jinja2

from core.agent_interface import AgentContext, StandaloneAgent, AgentExecutionError


# Type → example value mapping for generating valid test fixtures
_EXAMPLE_VALUES = {
    "string": '"test-value"',
    "integer": "42",
    "number": "3.14",
    "boolean": "True",
    "array": "[]",
    "object": "{}",
}

# Type → deliberately wrong-type value for malformed tests
_WRONG_TYPE_VALUES = {
    "string": "99999",           # int instead of string
    "integer": '"not-a-number"', # string instead of int
    "number": '"not-a-number"',
    "boolean": '"not-a-bool"',
}


def _to_class_name(tool_name: str) -> str:
    """Convert tool-name to PascalCase class name."""
    return "".join(word.capitalize() for word in re.split(r"[-_]", tool_name))


def _to_safe_name(tool_name: str) -> str:
    """Convert tool-name to snake_case for pytest function names."""
    return tool_name.replace("-", "_")


def _build_valid_args(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Build a dict of valid example arguments for a tool."""
    args = {}
    schema = tool.get("input_schema", {})
    for name, prop in schema.get("properties", {}).items():
        ptype = prop.get("type", "string")
        if "enum" in prop:
            args[name] = prop["enum"][0]
        elif ptype == "string":
            fmt = prop.get("format", "")
            if fmt == "email":
                args[name] = "test@example.com"
            elif fmt == "date":
                args[name] = "2026-01-01"
            elif fmt == "date-time":
                args[name] = "2026-01-01T00:00:00Z"
            else:
                args[name] = "test-value"
        elif ptype == "integer":
            # Respect min/max if present
            mn = prop.get("minimum", 1)
            args[name] = mn
        elif ptype == "number":
            args[name] = 1.0
        elif ptype == "boolean":
            args[name] = True
        elif ptype == "array":
            args[name] = []
        elif ptype == "object":
            args[name] = {}
    return args


def _find_first_string_param(tool: Dict[str, Any]) -> Optional[str]:
    """Find the first string-typed param for injection testing."""
    schema = tool.get("input_schema", {})
    for name, prop in schema.get("properties", {}).items():
        if prop.get("type") == "string" and "enum" not in prop:
            return name
    return None


def _get_required_params(tool: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get required params with their types and wrong-type test values."""
    schema = tool.get("input_schema", {})
    required = set(schema.get("required", []))
    params = []
    for name, prop in schema.get("properties", {}).items():
        if name in required:
            ptype = prop.get("type", "string")
            params.append({
                "name": name,
                "type": ptype,
                "wrong_type_value": _WRONG_TYPE_VALUES.get(ptype, "None"),
            })
    return params


class TesterAgent(StandaloneAgent):
    """
    Generates an adversarial pytest test suite for the MCP server.

    Reads the plan and generated_code from context, produces
    test_server.py in the server output directory.
    """
    __test__ = False

    def __init__(self):
        super().__init__("Tester")
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        """Generate and write the test suite."""
        self.log_start(context)

        plan = context.plan
        if not plan:
            raise AgentExecutionError(self.name, "No plan available — Architect must run first")

        generated_code = context.generated_code
        if not generated_code:
            raise AgentExecutionError(self.name, "No generated code — Builder must run first")

        # Reconstruct tool definitions from plan (same logic as Builder)
        tools = self._prepare_tools(plan)
        print(f"  Generating adversarial test suite for {len(tools)} tools")

        # Enrich tools with test metadata
        enriched_tools = []
        for tool in tools:
            enriched_tools.append({
                **tool,
                "class_name": _to_class_name(tool["name"]),
                "safe_name": _to_safe_name(tool["name"]),
                "valid_args": _build_valid_args(tool),
                "first_string_param": _find_first_string_param(tool),
                "required_params": _get_required_params(tool),
            })

        # Extract env vars for test fixture
        auth = plan.get("authentication", {})
        env_vars = auth.get("env_vars", [])

        # Count injection-testable tools (those with a string param)
        injectable = [t for t in enriched_tools if t["first_string_param"]]

        # Render test template
        template = self.jinja_env.get_template("test_server.py.j2")
        test_code = template.render(
            api_title=plan["api_info"]["title"],
            server_dir_name="server",
            tool_count=len(enriched_tools),
            tools=enriched_tools,
            env_vars=env_vars,
        )

        # Write to server directory
        output_dir = Path(context.output_dir)
        server_dir = output_dir / "server"
        server_dir.mkdir(parents=True, exist_ok=True)

        test_file = server_dir / "test_server.py"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_code)
        print(f"    [OK] {test_file}")

        # Count generated tests
        test_count = self._count_tests(test_code)
        print(f"  Generated {test_count} test cases across 4 categories")

        # Add to generated code context
        context.generated_code["test_server.py"] = test_code

        # Store test generation metadata
        context.test_results = {
            "test_file": str(test_file),
            "test_count": test_count,
            "categories": {
                "protocol": 5,
                "happy_path": len(enriched_tools),
                "malformed": sum(len(t["required_params"]) + 1 for t in enriched_tools if t["required_params"]),
                "injection": len(injectable),
            },
            "injectable_tools": [t["name"] for t in injectable],
        }

        self.log_complete(context, {
            "test_count": test_count,
            "tools_tested": len(enriched_tools),
            "injectable_tools": len(injectable),
        })

        return context

    def _prepare_tools(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Reconstruct tool list from plan (mirrors Builder._prepare_tools)."""
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

    @staticmethod
    def _count_tests(test_code: str) -> int:
        """Count test methods in generated code."""
        return len(re.findall(r"async def test_", test_code))


# Made with Bob

#!/usr/bin/env python3
"""
MCP Server Foundry - Main Recipe Entry Point

This is the primary entry point for the Foundry pipeline.
It orchestrates the four-agent workflow to convert OpenAPI specs
into production-grade MCP servers.

Usage:
    python forge_recipe.py --input <spec_file> --output <output_dir>
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Ensure foundry package root is importable when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from core.agent_interface import AgentContext
from core.orchestrator import PipelineBuilder
from agents.architect import ArchitectAgent
from agents.builder import BuilderAgent
from agents.tester import TesterAgent
from core.approval_gates import GateRejectedError


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MCP Server Foundry - Convert OpenAPI specs to MCP servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate from test spec
  python forge_recipe.py --input specs/test_api.yaml --output output/test-api

  # Specify custom output directory
  python forge_recipe.py -i specs/stripe.yaml -o output/stripe-mcp
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Path to OpenAPI specification file (YAML or JSON)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='./output',
        help='Output directory for generated server (default: ./output)'
    )
    
    parser.add_argument(
        '--name',
        help='Optional name for the generated server'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--auto-approve',
        action='store_true',
        help='Skip interactive approval gates (for CI/CD)'
    )
    
    return parser.parse_args()


async def run_pipeline(
    spec_path: str,
    output_dir: str,
    verbose: bool = False,
    auto_approve: bool = False,
):
    """
    Run the complete Foundry pipeline.
    
    Args:
        spec_path: Path to the OpenAPI specification
        output_dir: Directory for output artifacts
        verbose: Enable verbose logging
        auto_approve: Skip interactive approval gates
        
    Returns:
        Final execution context
        
    Raises:
        FileNotFoundError: If spec file doesn't exist
        GateRejectedError: If an approval gate is rejected
    """
    if not Path(spec_path).exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    
    context = AgentContext(
        spec_path=spec_path,
        output_dir=output_dir
    )
    
    pipeline = (
        PipelineBuilder()
        .add_agent(ArchitectAgent())
        .add_agent(BuilderAgent())
        .add_agent(TesterAgent())
        .set_output_dir(output_dir)
        .auto_approve(auto_approve)
        .build()
    )
    
    return await pipeline.execute_pipeline(context)


def print_summary(context: AgentContext):
    """Print execution summary."""
    print("\n" + "="*60)
    print("EXECUTION SUMMARY")
    print("="*60)
    print(f"Spec file: {context.spec_path}")
    print(f"Output directory: {context.output_dir}")
    print(f"Execution ID: {context.execution_id}")
    print(f"Agents executed: {len(context.agent_trace)}")
    
    if context.errors:
        print(f"\nErrors encountered: {len(context.errors)}")
        for error in context.errors:
            print(f"  - {error['agent']}: {error['error']}")
    else:
        print("\n[OK] Pipeline completed successfully")
    
    if context.plan:
        print(f"\n[OK] Plan generated with {len(context.plan.get('endpoints_by_tag', {}))} endpoint groups")
    
    if context.generated_code:
        print(f"[OK] Generated {len(context.generated_code)} code files")
    
    if context.test_results:
        tr = context.test_results
        print(f"[OK] Generated {tr['test_count']} adversarial test cases")
        cats = tr.get("categories", {})
        for cat, count in cats.items():
            print(f"     {cat}: {count}")

    print("\nNext steps:")
    print(f"  1. Review the generated server in: {context.output_dir}/server/")
    print(f"  2. Install dependencies: pip install pytest pytest-asyncio pydantic httpx")
    print(f"  3. Run the test suite: cd {context.output_dir}/server && python -m pytest test_server.py -v")
    print(f"  4. Run the server: python {context.output_dir}/server/main.py")
    print("="*60 + "\n")


def main():
    """Main entry point."""
    args = parse_arguments()
    
    print("\n" + "="*60)
    print("MCP SERVER FOUNDRY")
    print("="*60)
    print(f"Input spec: {args.input}")
    print(f"Output directory: {args.output}")
    print("="*60 + "\n")
    
    try:
        context = asyncio.run(run_pipeline(
            spec_path=args.input,
            output_dir=args.output,
            verbose=args.verbose,
            auto_approve=args.auto_approve,
        ))
        print_summary(context)
        return 0
    except FileNotFoundError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except GateRejectedError as e:
        print(f"\nPipeline aborted: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"\nPipeline execution failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob

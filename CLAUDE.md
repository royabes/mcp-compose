# MCP Compose — Project Instructions

Local workflow orchestrator for MCP servers. Define TOML workflows as DAGs, execute via CLI or MCP server.

## Tech Stack
- Python 3.11+, Typer (CLI), FastMCP 3.x (MCP server)
- Pydantic (validation), asyncio (parallel execution)

## Commands
```bash
pip install -e ".[dev]"          # Install
mc list                          # List workflows
mc validate <name>               # Validate workflow
mc run <name>                    # Show execution plan
mc new <name>                    # Scaffold workflow
pytest tests/ -v                 # Run tests
python -m mcp_compose.mcp_server # Start MCP server
```

## Architecture
```
src/mcp_compose/
├── cli.py          # Typer app — mc subcommands
├── mcp_server.py   # FastMCP — 4 tools
├── engine.py       # DAG resolver, async executor
├── models.py       # Pydantic workflow/step models
├── templates.py    # {{}} interpolation engine
└── config.py       # Workflow discovery (global + project)
```

## Workflow Locations
- Global: `~/.claude/workflows/*.toml`
- Project: `.claude/workflows/*.toml` (overrides global)

## Code Style
- Type hints everywhere (Python 3.11+ syntax)
- Pydantic BaseModel for structured data
- No classes for modules — use functions
- asyncio for parallel step execution

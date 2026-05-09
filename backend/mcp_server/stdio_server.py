"""
Servidor MCP (stdio) usando FastMCP — ferramentas equivalentes ao RAG Supabase.

Cursor / cliente MCP exemplo:
  command: python
  args: ["mcp_server/stdio_server.py"]
  cwd: <repo>/backend
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from fastmcp import FastMCP  # noqa: E402

from app.supabase_store import format_retrieval_for_agents, match_chunks  # noqa: E402

mcp = FastMCP("electrical-compliance-mcp")


@mcp.tool()
def match_technical_norms(query: str, norm_code: str = "", match_count: int = 8) -> str:
    """Busca semântica em normas técnicas indexadas (Supabase + pgvector)."""
    norm = norm_code.strip() or None
    rows = match_chunks(query=query, match_count=int(match_count), norm_code=norm)
    return format_retrieval_for_agents(rows)


@mcp.tool()
def evidence_format_help() -> str:
    """Descreve como interpretar blocos de evidência retornados pela busca."""
    return json.dumps(
        {
            "fields": ["norm_code", "metadata", "content", "similarity"],
            "policy": "Não citar cláusulas que não apareçam literalmente no content.",
        },
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    mcp.run()

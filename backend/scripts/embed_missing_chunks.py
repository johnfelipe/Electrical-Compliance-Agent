"""Gera embeddings para linhas doc_chunks com embedding ausente."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from openai import OpenAI  # noqa: E402

from app.config import settings  # noqa: E402
from app.supabase_store import get_client  # noqa: E402


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


def main(batch_size: int = 32) -> None:
    if not settings.openai_api_key:
        raise SystemExit("Defina OPENAI_API_KEY")

    sb = get_client()
    client = OpenAI(api_key=settings.openai_api_key)

    rows = (
        sb.table("doc_chunks").select("id,content,embedding").limit(10_000).execute().data
        or []
    )
    pending = [r for r in rows if r.get("embedding") in (None, "null")]
    if not pending:
        print("Nada a processar.")
        return

    ids = [r["id"] for r in pending]
    texts = [r["content"] for r in pending]

    updated = 0
    for i in range(0, len(texts), batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_text = texts[i : i + batch_size]
        emb = client.embeddings.create(model=settings.embedding_model, input=batch_text)
        vectors = [d.embedding for d in emb.data]
        for cid, vec in zip(batch_ids, vectors, strict=True):
            sb.table("doc_chunks").update({"embedding": to_pgvector(vec)}).eq("id", cid).execute()
            updated += 1

    print(f"Atualizados {updated} chunks.")


if __name__ == "__main__":
    main()

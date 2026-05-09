"""
Pipeline Fase 2: PDF norma técnica -> Gemini extrai texto/tabelas (Markdown) ->
chunk -> OpenAI embeddings -> Supabase technical_docs/doc_chunks.

Uso:
  python scripts/ingest_gemini_pdf.py --pdf path.pdf --norm "NBR 5410" --title "..."
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import google.generativeai as genai  # noqa: E402
from openai import OpenAI  # noqa: E402

from app.config import settings  # noqa: E402
from app.supabase_store import get_client  # noqa: E402

CHUNK_SPLIT = re.compile(r"(?=\n(?:##)\s+)")


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in values) + "]"


def split_markdown(section_text: str, max_chars: int = 3800, overlap: int = 320) -> list[str]:
    if len(section_text) <= max_chars:
        return [section_text.strip()]
    pieces: list[str] = []
    start = 0
    while start < len(section_text):
        chunk = section_text[start : start + max_chars].strip()
        if chunk:
            pieces.append(chunk)
        start += max_chars - overlap
    return pieces


def gemini_pdf_to_markdown(pdf_path: Path) -> str:
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv(
        "GOOGLE_API_KEY"
    )
    if not api_key:
        raise SystemExit("Defina GEMINI_API_KEY ou GOOGLE_API_KEY no .env")

    genai.configure(api_key=api_key)
    uploaded = genai.upload_file(path=str(pdf_path))
    model = genai.GenerativeModel("gemini-1.5-pro")

    prompt = (
        "Você é um assistente de engenharia. Converta o PDF normativo inteiro para Markdown. "
        "Preserve títulos com '## nível adequado'. "
        "Tabelas devem vir como tabelas Markdown. "
        "Preserve notas e referências quando forem tecnicamente relevantes."
    )

    resp = model.generate_content([prompt, uploaded], request_options={"timeout": 900})
    return str(resp.text or "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--norm", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--edition", default="")
    args = ap.parse_args()

    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY necessário para embeddings")

    markdown = gemini_pdf_to_markdown(args.pdf.expanduser())

    md_path = args.pdf.with_suffix(".extracted.md")
    md_path.write_text(markdown, encoding="utf-8")
    print("Markdown salvo em", md_path)

    raw_sections = [s.strip() for s in CHUNK_SPLIT.split("\n" + markdown) if s.strip()]
    sections = raw_sections if raw_sections else [markdown]

    chunks: list[tuple[int, dict[str, object], str]] = []
    for sec in sections:
        heading_match = re.search(r"^(#{1,4})\s+(.+)", sec, flags=re.MULTILINE)
        meta: dict[str, object] = {}
        if heading_match:
            meta["heading"] = heading_match.group(2).strip()[:280]
        for piece in split_markdown(sec):
            idx = len(chunks)
            chunks.append((idx, meta, piece))

    sb = get_client()
    oai = OpenAI(api_key=settings.openai_api_key)

    doc = (
        sb.table("technical_docs")
        .insert(
            {
                "title": args.title,
                "norm_code": args.norm,
                "edition": args.edition or None,
                "source_uri": str(args.pdf.resolve()),
                "meta": {"ingestion": "gemini-1.5-pro"},
            }
        )
        .execute()
    )
    doc_id = doc.data[0]["id"]

    batch_size = 16
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [b[2] for b in batch]
        embeddings = [
            e.embedding for e in oai.embeddings.create(model=settings.embedding_model, input=texts).data
        ]
        rows = []
        for (idx, meta, text), vec in zip(batch, embeddings, strict=True):
            rows.append(
                {
                    "doc_id": doc_id,
                    "chunk_index": idx,
                    "content": text,
                    "embedding": to_pgvector(vec),
                    "metadata": meta,
                }
            )
        sb.table("doc_chunks").insert(rows).execute()

    print(f"Inseridos {len(chunks)} chunks no documento", doc_id)


if __name__ == "__main__":
    main()

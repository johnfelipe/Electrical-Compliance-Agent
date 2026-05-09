from openai import OpenAI

from app.config import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings")
    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    return [d.embedding for d in resp.data]

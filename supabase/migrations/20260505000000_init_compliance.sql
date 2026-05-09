-- The Electrical Compliance Agent — schema inicial
create extension if not exists pgcrypto;
create extension if not exists vector;

create table if not exists public.technical_docs (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  norm_code text not null,
  edition text,
  source_uri text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.doc_chunks (
  id uuid primary key default gen_random_uuid(),
  doc_id uuid not null references public.technical_docs (id) on delete cascade,
  content text not null,
  embedding vector(1536),
  chunk_index int not null default 0,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create index if not exists doc_chunks_doc_id_idx on public.doc_chunks (doc_id);

create index if not exists doc_chunks_embedding_hnsw on public.doc_chunks
  using hnsw (embedding vector_cosine_ops);

create table if not exists public.project_audits (
  id uuid primary key default gen_random_uuid(),
  user_input text not null,
  normalized_summary jsonb,
  norms_touched text[] default '{}',
  findings jsonb,
  full_report text,
  agent_trace jsonb,
  created_at timestamptz default now()
);

create or replace function public.match_doc_chunks (
  query_embedding vector(1536),
  match_count int default 8,
  filter_norm_code text default null
)
returns table (
  chunk_id uuid,
  doc_id uuid,
  norm_code text,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    c.id as chunk_id,
    c.doc_id,
    d.norm_code,
    c.content,
    c.metadata,
    1 - (c.embedding <=> query_embedding) as similarity
  from public.doc_chunks c
  join public.technical_docs d on d.id = c.doc_id
  where c.embedding is not null
    and (filter_norm_code is null or d.norm_code ilike ('%' || filter_norm_code || '%'))
  order by c.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

-- Exemplo mínimo para demo (Fase 1) — executar após migrations
insert into public.technical_docs (id, title, norm_code, edition, meta)
values
  ('11111111-1111-1111-1111-111111111101', 'NBR 5410 — Instalações elétricas de baixa tensão', 'NBR 5410', '2004', '{"topic":"LV"}'::jsonb),
  ('11111111-1111-1111-1111-111111111102', 'NBR 14039 — Instalações elétricas em AT', 'NBR 14039', '2019', '{"topic":"HV"}'::jsonb)
on conflict do nothing;

-- Dois trechos fictícios para smoke test (embeddings nulos = busca vetorial não retorna; use scripts/ingest para popular)
insert into public.doc_chunks (doc_id, content, chunk_index, metadata)
values
  ('11111111-1111-1111-1111-111111111101',
   'NBR 5410 (exemplo didático): condutores devem ser dimensionados para suportar a corrente de projeto e as condições de instalação. Referência de item/cláusula deve vir do documento oficial.',
   0,
   '{"section":"6.x","clause":" exemplo didático "}'),
  ('11111111-1111-1111-1111-111111111102',
   'NBR 14039 (exemplo didático): equipamentos e barramentos devem atender aos requisitos de curto-circuito e coordenação de proteções conforme o projeto.',
   0,
   '{"section":" segurança "}');

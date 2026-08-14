# Feasibility Assessment

## Verdict: FEASÍVEL ✅

Todos os 6 bugfixes têm causa-raiz conhecida, solução documentada e sem bloqueadores externos. A iniciativa pode ser concluída em 3-4 dias de desenvolvimento.

---

## Análise por Bug

### BUG3 — Python plots (BAIXO RISCO)
- **Técnico:** `code_executor.py` já executa e salva. Só precisa retornar URL correta. 2-3h de trabalho.
- **Infra:** Nenhuma mudança. GCS bucket já existe.
- **Risco:** Mínimo. Mudança localizada em 2 arquivos.

### BUG4 — Tavily API (BAIXO RISCO)
- **Técnico:** Substituição de scraping por API REST. Tavily tem plano gratuito (1.000 req/mês) adequado para uso pessoal.
- **Infra:** Adicionar `TAVILY_API_KEY` no Secret Manager do GCP e no `cmo-agent` Cloud Run env vars.
- **Risco:** Baixo. Fallback: se Tavily falhar, retornar string vazia (comportamento atual já trata isso).
- **Dependência externa:** Criar conta em tavily.com antes do deploy.

### BUG5 — Pydantic warnings (MÍNIMO RISCO)
- **Técnico:** Renomear campo em 4 classes Pydantic. Pydantic v2 suporta `Field(alias="copy")` para manter compatibilidade no JSON de saída.
- **Infra:** Nenhuma.
- **Risco:** Mínimo. Afeta apenas serialização interna do distribution_agent.

### BUG6 — Validator contextual (BAIXO RISCO)
- **Técnico:** Adicionar campo `tipo_artigo` na interface `PautaConcebida` (TypeScript + Pydantic). Validator lê o campo e aplica critérios diferentes.
- **Infra:** Nenhuma. Alteração de prompt no sistema.
- **Risco:** Baixo. O campo é opcional com fallback para "tecnico" (comportamento atual).

### BUG1 — Slide designer agent (MÉDIO RISCO)
- **Técnico:** Novo agente Python que recebe um segmento do manifesto e retorna HTML completo (1920×1080 ou 1080×1920). Usa Gemini via Vertex AI (mesma infra existente). 8 tipos de beat mapeados.
- **Infra:** Nenhuma infra nova. O HTML gerado substitui os placeholders no manifest_builder.py.
- **Risco:** Médio. A qualidade do HTML gerado pelo LLM pode variar. Mitigação: template-driven prompting (cada beat tem um template base que o LLM preenche).
- **Latência:** +10-15s no endpoint `/package`. Aceitável.

### BUG2 — Avatar job por segmento (MÉDIO-ALTO RISCO)
- **Técnico:** Refatorar `_concatenate_audio()` → processar segmentos individualmente. Mudar `AvatarCompletedMsg` de `str` para `list[str]`.
- **Infra:** Sem infra nova. Mas exige **deploy coordenado** de 3 serviços: `cmo-agent` (não afetado), `heygen-callback`, `video-editor-job`. O `avatar-job` é Cloud Run Job.
- **Risco:** A mudança de contrato Pub/Sub é um breaking change. Se `heygen-callback` (producer) for atualizado antes de `video-editor-job` (consumer), mensagens com `list[str]` chegarão a um consumer que espera `str` → crash. **Mitigação:** Deploy simultâneo via um único `gcloud builds submit`.
- **Custo HeyGen:** N chamadas individuais vs 1 concatenada. O custo é cobrado por segundo de vídeo gerado, não por chamada. O custo total é idêntico. Número de chamadas API aumenta (1 por segmento × ~8 segmentos × 2 targets = ~16 chamadas HeyGen por vídeo).

---

## Resumo de Risco

| Bug | Risco | Mitigação |
|---|---|---|
| BUG3 | Baixo | Teste local antes do deploy |
| BUG4 | Baixo | Criar conta Tavily + testar TAVILY_API_KEY |
| BUG5 | Mínimo | — |
| BUG6 | Baixo | Campo opcional com fallback |
| BUG1 | Médio | Template-driven prompting por beat type |
| BUG2 | Médio-Alto | Deploy coordenado dos 3 serviços simultâneo |

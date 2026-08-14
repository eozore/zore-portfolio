# Initiative Brief — éozoré Content Studio Bugfixes

## Resumo executivo
Corrigir 6 bugs que impedem o funcionamento correto da pipeline de criação de conteúdo do éozoré. Os mais críticos (BUG1 e BUG2) tornam os vídeos YouTube inutilizáveis (telas pretas, áudio dessincronizado). Os demais degradam a qualidade do conteúdo gerado.

## O que será entregue
1. **BUG3** — Gráficos Python renderizam como imagens reais no artigo (não mais telas brancas)
2. **BUG4** — Pesquisa web do CMO Agent funciona com alta confiabilidade via Tavily API
3. **BUG5** — Logs do cmo-agent sem warnings de Pydantic
4. **BUG6** — Artigos conceituais/estratégicos não são mais reprovados injustamente
5. **BUG1** — Vídeos YouTube têm slides visuais reais por segmento (hook, teoria, código, demo...)
6. **BUG2** — Áudio e vídeo estão sincronizados por segmento (sem mais concatenação indevida)

## Arquivos modificados

### cmo-agent (Python)
- `agents/cmo_agent/code_executor.py`
- `agents/cmo_agent/tools.py`
- `agents/cmo_agent/distribution_agent.py`
- `agents/cmo_agent/validator_agent.py`
- `agents/cmo_agent/prompts.py`
- `agents/cmo_agent/slide_designer_agent.py` *(novo)*
- `agents/cmo_agent/agent.py`
- `agents/cmo_agent/manifest_builder.py`

### pipeline (Python)
- `agents/pipeline/shared/models.py`
- `agents/pipeline/avatar_job/job.py`
- `agents/pipeline/heygen_callback/app.py`
- `agents/pipeline/video_editor_job/job.py`

### frontend (TypeScript)
- `apps/web/src/components/csm/RichArticleRenderer.tsx`
- `apps/web/src/components/csm/CsmDashboard.tsx`

## Aprovação
**Aprovado por:** Victor Zore (fundador / PO)
**Data:** 2026-07-29
**Evidência:** NEXT_SESSION.md — documento de handoff gerado pelo próprio Victor com especificação detalhada dos 6 bugs

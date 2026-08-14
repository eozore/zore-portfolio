# Risk and Sequencing Rationale
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [stories.md](../user-stories/stories.md) | [mockups.md](../refined-mockups/mockups.md) | [components.md](../application-design/components.md) | [unit-of-work.md](../units-generation/unit-of-work.md) | [unit-of-work-dependency.md](../units-generation/unit-of-work-dependency.md) | [unit-of-work-story-map.md](../units-generation/unit-of-work-story-map.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Heurística Aplicada

**Bolt 0:** Foundational-first — pré-requisitos duros sem valor incremental direto, mas desbloqueadores críticos.

**Bolt 1 (Walking Skeleton):** Risk-first — as duas integrações externas de maior risco (ElevenLabs TTS + HeyGen Lipsync v3) são validadas antes de qualquer construção adicional. Segue o princípio de Cockburn: "a walking skeleton is the thinnest possible slice of real functionality that connects all the major system parts."

**Bolts 2-4:** Value-first — cada Bolt entrega uma capacidade diretamente utilizável por Victor. Sequenciados por dependência técnica (VideoEditor antes de Publisher, pois Publisher consome vídeos prontos) com consideração de risco (VideoEditor tem risco técnico maior que a UI, então vem antes).

**Bolt 5:** Value-completion — o sistema já funciona após o Bolt 4; o Bolt 5 adiciona os formatos derivados para completar a promessa omnicanal.

---

## Análise de Risco por Bolt (Risk-Reduction Value)

### Bolt 1 — Riscos resolvidos

| Risco | RAID Ref | Mitigação via Bolt 1 |
|---|---|---|
| Custo real HeyGen Lipsync PAYG pode exceder R$80 | A-03, OQ-01 | Spike: medir custo real antes de continuar |
| ElevenLabs Instant Clone inadequado para pt-BR | A-02, OQ-02 | Teste de voz clonada antes de usar em produção |
| HeyGen callback_url não funciona como arquitetado | ADR-03 | Validado end-to-end no Bolt 1 |
| Firestore `collection_group` indexing falha silenciosamente | Architecture Reviewer F4 | Smoke test no Bolt 0 (índice aplicado) + validado no Bolt 1 |

### Bolt 2 — Riscos resolvidos

| Risco | RAID Ref | Mitigação via Bolt 2 |
|---|---|---|
| Playwright + FFmpeg causam OOM no Cloud Run (4GB) | Architecture Reviewer F2 | Execução real de vídeo de 15 min; medir RAM |
| Playwright em Alpine Linux falha com animações CSS | A-04 | Spike incluído no Bolt 2 |

### Bolt 3 — Riscos resolvidos

| Risco | RAID Ref | Mitigação via Bolt 3 |
|---|---|---|
| YouTube service account não funciona para upload | A-05, FR-12 | Confirmado na prática com YouTube OAuth |
| Meta Graph API bloqueia conta por comportamento anômalo | R04, CC-02 | Rate limits implementados e testados |

---

## Justificativa de Desvios do DAG Topológico

O DAG topológico de U-01 a U-13 sugere que U-03 (projects-api) pode ser construído antes de U-12 (publisher-service), já que U-03 não depende de U-12. Porém, no plano de Bolts, **U-03 e U-12 estão no mesmo Bolt 3**.

**Razão:** U-03 sozinho (sem U-12) entrega apenas endpoints de aprovação sem capacidade de publicação — uma funcionalidade incompleta do ponto de vista do usuário. A hipótese de confiança do Bolt 3 ("pipeline completa funciona") exige que U-12 e U-03 sejam validados juntos. Agrupá-los no mesmo Bolt maximiza o valor entregue por Bolt.

Similarmente, **U-04, U-05, U-06** (Bolt 4) são topologicamente independentes entre si após U-01, mas agrupados porque a UI é uma capacidade coesa (Victor não consegue usar meia-UI). O Bolt 4 entrega "operabilidade pelo CSM Studio" como capacidade completa.

---

## WSJF Simplificado (Reinertsen / SAFe)

| Bolt | User-Business Value | Time Criticality | Risk-Reduction | Job Size | WSJF Score |
|---|---|---|---|---|---|
| 0: `foundations` | 2 (infra pura) | 10 (bloqueia tudo) | 3 | 1 | **(2+10+3)/1 = 15** |
| 1: `walking-skeleton` | 8 (valida arquitetura) | 9 (risco alto) | 10 (resolve 4 riscos) | 5 | **(8+9+10)/5 = 5.4** |
| 2: `video-editor` | 7 (vídeo é o produto) | 7 | 8 (OOM/Playwright) | 6 | **(7+7+8)/6 = 3.7** |
| 3: `publisher-core` | 10 (entrega valor direto) | 8 | 6 | 7 | **(10+8+6)/7 = 3.4** |
| 4: `studio-ui` | 9 (operabilidade de Victor) | 5 | 2 | 8 | **(9+5+2)/8 = 2.0** |
| 5: `distribution` | 8 (completa omnicanal) | 3 | 1 | 5 | **(8+3+1)/5 = 2.4** |

O WSJF confirma a sequência Bolt 0 → 1 → 2 → 3 → 4 → 5 com ajuste: Bolt 5 tem WSJF ligeiramente maior que Bolt 4, mas a dependência técnica (Victor precisa da UI para operar o sistema) justifica manter a UI no Bolt 4 antes da distribuição completa no Bolt 5.

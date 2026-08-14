# Team Assessment
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md) | [feasibility-assessment.md](../feasibility/feasibility-assessment.md)

---

## Modelo de Time

Este projeto opera sob o modelo **Solo Tech Lead + AI Agents**. Não há equipe humana além de Victor Zore.

```
+---------------------------+
|   Victor Zore             |
|   Tech Lead + PO          |
|   ~5h/semana (review/gate)|
+---------------------------+
            |
     delega execução para
            |
+---------------------------+
|   AIDLC Agent Ensemble    |
|   (conductor + agents)    |
|   execução autônoma       |
+---------------------------+
```

O modelo implica algumas adaptações em relação ao processo AIDLC padrão:

- **Gates de aprovação** são checkpoints reais onde Victor revisa e aprova antes de prosseguir — não cerimônias de time.
- **Velocidade** é determinada pelo ritmo de aprovação de Victor, não por sprints de equipe.
- **Comunicação** é toda assíncrona (Victor lê os artefatos gerados e responde quando disponível).
- **Handoffs** são entre Bolts AIDLC, não entre pessoas.

---

## Perfil Técnico: Victor Zore

| Domínio | Nível | Relevância para o Projeto |
|---|---|---|
| Python (FastAPI, async, dataclasses) | Sênior | TTS Job, Avatar Job, Video Editor Job, Publisher Service — todos em Python |
| TypeScript / Next.js App Router | Sênior | Kanban, Painel de Configuração, rotas API no CSM Studio |
| GCP (Cloud Run, Firestore, GCS, Secret Manager) | Sênior | Toda a infraestrutura do projeto |
| Firebase Admin SDK | Sênior | Autenticação, Firestore, credenciais |
| FFmpeg (composição de vídeo) | Intermediário | Video Editor Job — já tem experiência com `editor_pipeline.py` |
| Playwright / Chromium headless | Intermediário | Renderização de slides HTML — já usa em `tool-videoyoutube` |
| GCP Pub/Sub | Básico → Intermediário | Novo componente; curva de aprendizado baixa (SDK simples) |
| HeyGen API v3 | Novo | Lipsync API v3 — documentação lida, implementação a fazer |
| ElevenLabs API | Novo | Clone de voz e TTS — documentação lida, implementação a fazer |
| YouTube Data API v3 | Básico | Upload de vídeo — dentro do ecossistema GCP já conhecido |
| Meta Graph API | Básico | Já tem integrações funcionando (Instagram/Threads/Facebook) |
| LinkedIn API v2 | Básico | Já tem integração funcionando |

**Lacunas identificadas (não bloqueantes):**

| Lacuna | Mitigação |
|---|---|
| HeyGen Lipsync API v3 (novo) | Leitura de documentação + spike no Bolt 1 antes de commitar à arquitetura completa |
| ElevenLabs Voice Clone (novo) | Setup inicial de conta e teste de clone antes do Bolt 1 (pre-condition B1-08) |
| GCP Pub/Sub (básico) | SDK Python/Node bem documentado; curva ≤ 1 dia |

---

## Capacidade e Cadência

| Fase | Capacidade de Victor | Modo de Operação |
|---|---|---|
| Ideation (atual) | ~2h/sessão de Q&A | Responde perguntas, aprova gates |
| Inception | ~3h/semana para revisão de artefatos | Aprova requirements, stories, design |
| Construction | ~5h/semana para revisão de código e gates | Revisa diffs, aprova Bolts, testa manualmente |
| Operation | ~1h/semana para monitoramento | Opera o sistema, responde alertas |

**Ritmo de Bolt:** dado ~5h/semana disponíveis para review, cada Bolt deve ter gates de aprovação que caibam em 1-2h de revisão. Bolts muito grandes precisam ser divididos.

---

## Estrutura de Decisão (Solo)

```
Victor é simultaneamente:
  - Product Owner: define prioridades e aprova o que vai para produção
  - Tech Lead: toma decisões arquiteturais e de implementação
  - Operador: executa o sistema após a construção

Não há:
  - Comitê de aprovação
  - Code review por pares
  - Sprint planning com time
  - Reuniões de status

O que substitui:
  - Gates AIDLC: substituem sprint reviews e retrospectivas
  - Artefatos escritos: substituem discussões de time
  - Testes automatizados: substituem code review por pares (parcialmente)
```

---

## Riscos de Capacidade

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Victor indisponível por semana(s) | Média | Alto para gates | Workflow pode ser pausado e retomado (`/aidlc --resume`); Pub/Sub mantém estado |
| Scope creep solo — sem time para questionar | Média | Médio | Gates AIDLC servem como freio; scope-document define o OUT claramente |
| Debt técnico acumulado sem code review | Baixa | Médio | Agente AIDLC faz quality review em cada Bolt; testes automatizados como rede de segurança |

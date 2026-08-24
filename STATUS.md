# éozoré Content Studio — estado da entrega

**Última revisão:** 23/08/2026.

Este documento substitui `NEXT_SESSION.md`, `ROADMAP.md`, `cmofinal.md` e
`build_csm_tool.md`. Os quatro eram de julho e descreviam como "faltando"
coisas que já existem — `slide_designer_agent`, avatar por segmento, corte
vertical. Manter quatro versões da verdade era o que tornava impossível saber
o que faltava de fato.

Para a arquitetura da pipeline de vídeo, ver `PIPELINE_E2E_REVIEW.md`.

---

## O produto

Um fluxo contínuo, com dois pontos de aprovação humana:

```
tema → pauta → ARTIGO → [você aprova] → ROTEIRO+SLIDES → [você aprova]
                                                              ↓
                        produção do vídeo (TTS → HeyGen → edição → YouTube privado)
                                                              ↓
                        PLANO SOCIAL → [você agenda] → social_queue → publicação
                                                              ↓
                        corte vertical (Reel + Short recortados do mesmo vídeo)
```

---

## As duas interfaces

O repositório tem **duas gerações** da ferramenta. Isto é temporário e
deliberado.

### `/admin/studio` — a atual

Orquestrada por um grafo LangGraph (`agents/cmo_agent/graph/`), com checkpoint
durável em Firestore: o gate pausa de verdade, sem segurar instância de Cloud
Run, e a retomada acontece em outro processo dias depois.

- saída estruturada via `responseSchema` (`structured.py`) — nenhum agente
  parseia JSON com regex
- multi-tenancy verificada por HMAC nos três serviços
- observabilidade OTel → Cloud Trace, degradando para no-op

### `/admin/csm` — a anterior, ainda no ar

Quatro abas (Ideia → Artigo → Revisão → Acompanhamento) sobre os endpoints
imperativos do `agent.py`. **Mantida como rede de segurança até o Studio
completar um ciclo real em produção.** Quando isso acontecer, sai — junto com
os endpoints legados do `agent.py` que só ela usa.

Os componentes das abas que já não eram importados por ninguém
(`GenerateTab`, `PublishTab`, `PackageTab`, `RepurposeTab`, `YoutubeTab`,
`CalendarTab` e dependentes) foram removidos em 23/08.

---

## O que está pronto e verificado

| | |
|---|---|
| Grafo com dois gates e checkpoint em Firestore | ✅ |
| Artigo publicado no blog como rascunho ao aprovar o gate | ✅ |
| Plano social gravado na `social_queue` com imagens renderizadas | ✅ |
| Corte vertical acionável pela interface | ✅ |
| Pipeline de vídeo sob a regra 80/20 (avatar/ilustração) | ✅ |
| HeyGen na API v3, com motor configurável | ✅ |
| Gate de custo em dólares, com tarifa por motor | ✅ |
| Ambiente local com emuladores e stubs pagos | ✅ |

**183 testes** — 122 em `agents/pipeline`, 61 em `agents/cmo_agent`.

---

## O que falta

- **Nenhum ciclo completo rodou no Studio.** Nem local, nem em produção. É a
  próxima coisa a fazer, e é o que separa "implementado" de "entregue".
- **Sincronia labial não medida.** O diagnóstico está fechado (era o motor de
  renderização, não o modo de entrada de áudio — ver `PIPELINE_E2E_REVIEW.md`),
  mas falta o teste A/B de um segmento curto para confirmar o ganho e o custo
  real do `avatar_v`.
- **Stories saem tipográficos.** O schema descreve uma `ilustracao` por frame
  e nada a gera: não há modelo de imagem em nenhum ponto da pipeline.
- **Studio não tem biblioteca de sessões.** "Novo tema" descarta a anterior
  sem lista para voltar.
- **Carrossel e stories derivam do artigo**, não das ilustrações do vídeo.
- **Nenhum artigo saiu com gráfico.** Só há suporte a ` ```python-plot ` →
  matplotlib → PNG estático, e o modelo não tem emitido nem isso.

---

## Custo por vídeo

O gasto é dominado pelo HeyGen, e o motor decide:

| Motor | US$/min | ~60s de avatar |
|---|---|---|
| `avatar_iii` | 1,00 | ~US$1 |
| `avatar_iv` | 4,00 | ~US$4 |
| `avatar_v` | não publicado | medido em execução |

Configurável em `HEYGEN_ENGINE` sem rebuild. O crédito de API é um pool
**separado** do da assinatura da plataforma web — crédito de plano não paga
chamada de API.

---

## Deploy

Não existe GitHub Actions. O deploy é Cloud Build, e há **trigger ativo**:
push na `main` dispara build automático.

| Config | O que deploya |
|---|---|
| `cloudbuild.yaml` | `cmo-agent` + `frontend` |
| `cloudbuild-pipeline.yaml` | Cloud Run Jobs: tts, avatar, video-editor, vertical-cut, publisher, callbacks |
| `cloudbuild-web.yaml` | só o frontend |

Disparo manual:

```bash
gcloud builds submit --config=cloudbuild-pipeline.yaml --project=vazfy-417019
```

**Mudança em `agents/pipeline/` não sai pelo `cloudbuild.yaml`** — precisa do
`cloudbuild-pipeline.yaml`.

---

## Ambiente local

```bash
docker compose -f docker-compose.local.yml up --build
```

`http://localhost:3000/admin/studio`, senha `local`. Firestore e Pub/Sub
emulados, HeyGen e ElevenLabs em stub, Vertex AI real. Detalhes em
`infra/local/README.md`.

---

## Segurança

`NEXT_SESSION.md` trazia a senha de produção do CSM em texto puro e foi
removido — mas **ela continua no histórico do git**. Rotacione
`CSM_PASSWORD_HASH` no Secret Manager e faça deploy antes de considerar o
repositório limpo.

Ver `CSM_SECURITY_SETUP.md` para o segredo interno Next.js ↔ cmo-agent.

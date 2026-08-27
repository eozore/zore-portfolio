# éozoré Content Studio — estado da entrega

**Última revisão:** 26/08/2026.

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
| **Ciclo completo executado ponta a ponta no ambiente local** | ✅ |
| **`terraform plan` limpo — o .tf descreve o que está no ar** | ✅ |

**183 testes** — 122 em `agents/pipeline`, 61 em `agents/cmo_agent`.

### O ciclo local de 26/08

Primeira execução completa do Studio, pela rota real do frontend
(`/api/csm/studio`), não pelos endpoints do grafo — a distinção importa: é o
Next.js que grava o artigo e dispara a produção, e um ciclo que fale direto
com o `cmo-agent` pula as duas coisas sem acusar nada.

```
artigo 8843 chars → rascunho gravado, 404 na URL direta
pacote 11 segmentos, 37% avatar, 8 slides
produção disparada, projectId devolvido
21 peças sociais → 50 documentos na social_queue
```

Zero erros. Três defeitos do ambiente local foram corrigidos para chegar lá —
os três silenciosos, e os três desarmando a validação que o ambiente promete:

1. o emulador recusava toda escrita no banco `(default)`;
2. depois de corrigido (1), o Node passou a gravar num banco e o Python em
   outro — o artigo de um lado, o grafo e a fila do outro, sem erro nenhum;
3. o Pub/Sub emulado subia sem topic, então o gate do vídeo — o mais caro do
   fluxo — abortava sempre e nunca podia ser exercitado.

## O que falta

- **Nenhum ciclo completo rodou em PRODUÇÃO.** O ciclo local fecha ponta a
  ponta, mas o ambiente local não cobre IAM, Secret Manager, rede entre
  serviços do Cloud Run, nem a produção do vídeo em si (HeyGen e ElevenLabs
  são stub, e nenhum Cloud Run Job roda localmente).

  **Bloqueado hoje**: o refresh token do YouTube está inválido
  (`./scripts/check-credentials.sh` acusa). Renove com
  `./scripts/renew_token.py youtube` — exige o seu consentimento OAuth no
  navegador — antes de aprovar o gate do vídeo. Sem isso o vídeo é gerado,
  gasta os créditos, e falha só na publicação.

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

Não existe GitHub Actions. É Cloud Build, com **dois triggers** na `main`:

| Trigger | Config | Cobre |
|---|---|---|
| `eozore` | `cloudbuild.yaml` | cmo-agent + frontend + cromex |
| `eozore-pipeline` | `cloudbuild-pipeline.yaml` | Cloud Run Jobs, filtrado em `agents/pipeline/**` |

`cloudbuild-web.yaml` existe e deploya só o frontend, mas nenhum trigger o usa.

Até 23/08 havia **um** trigger. O cabeçalho do `cloudbuild-pipeline.yaml`
afirmava ter o seu, mas ele nunca tinha sido criado — então toda correção da
pipeline só chegava em produção se alguém lembrasse do comando manual. É a
explicação mais provável para produção ter divergido da main.

```bash
./scripts/deploy.sh            # pipeline e depois web, com testes antes
./scripts/deploy.sh --check    # o que está no ar agora
```

**A ordem importa**: a pipeline primeiro. Se o frontend novo subir antes dos
jobs, aprovar um vídeo dispara a produção pelo caminho antigo.

---

## Ambiente local

```bash
docker compose -f docker-compose.local.yml up --build
docker compose -f docker-compose.local.yml exec cmo-agent python /app/seed.py
```

`http://localhost:3000/admin/studio`, senha `local`. Firestore e Pub/Sub
emulados, HeyGen e ElevenLabs em stub, Vertex AI real. Detalhes em
`infra/local/README.md`.

**Rode o `seed.py`.** Ele não é só conveniência: além dos agentes e das
skills, cria os sete topics do Pub/Sub. O emulador sobe sem topic nenhum, e
sem eles o gate do vídeo aborta em `Topic not found`.

---

## Infraestrutura

`infra/pipeline/` descreve os recursos da pipeline: service account e IAM,
bucket de mídia, os sete topics, as seis subscriptions push, os seis Cloud Run
Jobs, os três services e o Cloud Scheduler.

```bash
cd infra/pipeline && terraform plan
```

**Deve dizer `No changes`.** Se acusar diferença, a pergunta certa é qual dos
dois lados está errado — não aplicar por reflexo. Até 26/08 o plan pedia 6
recursos a criar e 7 a alterar, e nenhum era intenção: `apply` teria revertido
a imagem dos jobs para `:latest` e trocado os `secret_key_ref` de YouTube e
ElevenLabs por env vazia.

A imagem dos jobs está sob `ignore_changes` de propósito: quem manda nela é o
Cloud Build. Terraform cuida da forma dos recursos, o Cloud Build cuida do que
roda dentro deles.

---

## Antes de aprovar um pacote

```bash
./scripts/check-credentials.sh
```

Tokens de publicação expiram sozinhos — o do YouTube em ~7 dias enquanto a
tela de consentimento estiver em "Testing". A pipeline só descobriria na hora
de publicar, depois de já ter gasto ElevenLabs e HeyGen no vídeo inteiro.

Para renovar: `./scripts/renew_token.py youtube` (ou `threads`). O login
acontece no seu navegador; o script não vê a senha.

## Segurança

**Pendência aberta: `csm-password-hash` nunca foi rotacionado.** O
`NEXT_SESSION.md` trazia a senha de produção do CSM em texto puro. O arquivo
foi removido em `388fed1`, mas **a senha continua no histórico do git**, e o
segredo segue na versão 1, de 27/07 — anterior ao vazamento ter sido notado.

A chave de sessão já foi separada da senha (`csm-auth-secret`, criado em
25/08 por `fb4227d`), então uma sessão não é mais forjável a partir dela. Mas
quem tiver o histórico do repositório ainda consegue **entrar** em
`/admin/csm` e `/admin/studio`.

Rotacionar exige escolher uma senha nova — é ação sua:

```bash
printf '%s' 'NOVA_SENHA' | shasum -a 256 | cut -d" " -f1 \
  | gcloud secrets versions add csm-password-hash --data-file=-
./scripts/deploy.sh web
```

Ver `CSM_SECURITY_SETUP.md` para o segredo interno Next.js ↔ cmo-agent.

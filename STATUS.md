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

## O primeiro ciclo em produção — 27/08

Rodou ponta a ponta: artigo publicado, semana de 51 peças agendada (28/08 a
03/09), vídeo montado e enviado ao YouTube como privado (`c24oqVj_CRQ`).

E revelou cinco defeitos que só aparecem no produto final. Nenhum deu erro em
lugar nenhum — cada etapa reportou sucesso:

| O que quebrou | Como se manifestou |
|---|---|
| URL do callback com path depois da query | 4 callbacks em 404; projeto travado em `pending_callback` com crédito gasto |
| MP3 embrulhado em cabeçalho WAV | ilustrações cortadas em 18% da fala; vídeo de 94s em vez de 208s |
| `:root` apagado no escopamento do CSS | 173 `var(--…)` sem definição; slides sem design nenhum |
| Narração renderizada no slide | espectador lia e ouvia a mesma frase |
| Endpoint de thumbnail sem `/set` | vídeo publicado sem capa, com a imagem pronta no GCS |

Mais três na interface: agendamento sem confirmação, etapa de edição
invisível (e polling congelando junto) e login ilegível.

Todos corrigidos, cada um com teste de regressão que falha sem a correção.

---

## O Studio

`/admin/studio` abre na **biblioteca**: um item por ciclo, com o estado de
cada um dos quatro entregáveis. Não é barra de progresso — é matriz, porque
as combinações reais incluem "artigo publicado, vídeo travado, social
agendada", que nenhuma barra representa.

Cada célula é acionável quando faz sentido: publicar o artigo em rascunho,
agendar a semana, derivar o Reel, remontar o vídeo.

**Retomar reusa o mesmo `projectId`.** É a diferença entre custar zero e
custar US$5: aprovar o gate de novo cria um projeto novo e refaz o avatar,
enquanto retomar da edição reaproveita os clipes que já estão no GCS. `tts` e
`avatar` gastam dinheiro e exigem confirmação explícita.

Antes disto o checkpoint do LangGraph era **inlistável**: ele grava em
`graph_threads/{thread}/checkpoints/{id}` e o documento pai nunca é criado —
no Firestore, um documento que só tem subcoleção não aparece em listagem nem
responde a `get()`. O id da sessão vivia no `localStorage` e "Novo tema" o
sobrescrevia; o ciclo anterior ficava inalcançável. `studio_sessions` resolve
isso, e `scripts/backfill_sessoes.py` reconstrói o índice para ciclos
anteriores a ele.

---

## O que falta

- **Refazer o vídeo de 27/08** com o áudio e os slides corrigidos. Os clipes
  de avatar já estão no GCS e são reaproveitáveis: custa zero de HeyGen.
- **Nenhum ciclo completo rodou em PRODUÇÃO.** O ciclo local fecha ponta a
  ponta, mas o ambiente local não cobre IAM, Secret Manager, rede entre
  serviços do Cloud Run, nem a produção do vídeo em si (HeyGen e ElevenLabs
  são stub, e nenhum Cloud Run Job roda localmente).

  Um ciclo rodou (ver acima), mas com os cinco defeitos. O próximo é que
  vale como entrega.

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

## Tokens de publicação

Expiram sozinhos, e a pipeline só descobria na hora de publicar — depois de
ter gasto ElevenLabs e HeyGen no vídeo inteiro.

`token-refresh-job` roda toda segunda 09:00 UTC e renova o que é renovável:

| Token | Vence em | Automatizável |
|---|---|---|
| YouTube `refresh_token` | 7 dias em "Testing"; indefinido em produção | ❌ exige consentimento no navegador |
| LinkedIn `access_token` | 60 dias | ✅ via `refresh_token` |
| LinkedIn `refresh_token` | 365 dias | ❌ exige consentimento |
| Threads | 60 dias | ✅ `th_refresh_token` |
| Instagram | não expira (token de página) | — só se verifica |

O que não é renovável vira log de ERROR com o comando da correção, dias antes
de vencer. **Alerta não marca o job como falho**: ele funcionou e encontrou
algo que só um humano resolve — marcar vermelho ensinaria a ignorar.

**O YouTube expirar em 7 dias tem causa e tem cura, e a cura não é código.**
Autorização de test user vale 7 dias; publicar a tela de consentimento em
"In production" remove o limite. Enquanto estiver em "Testing", nenhum job
resolve — só avisa.

Verificação manual, a qualquer momento:

```bash
./scripts/check-credentials.sh
gcloud run jobs execute token-refresh-job --region us-central1   # renova de verdade
```

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

**`csm-password-hash` rotacionado em 27/08.** O `NEXT_SESSION.md` trazia a
senha de produção em texto puro; o arquivo saiu em `388fed1`, mas a senha
continua no histórico do git — o que importa é que ela deixou de valer.

A versão 2 do segredo está ativa e a **versão 1 foi desativada**, então o
valor que está no histórico não abre mais nada. A chave de sessão já era
separada da senha desde `fb4227d`, então uma sessão também não é forjável a
partir dela.

A ordem importa em qualquer rotação futura: publique a versão nova, force uma
revisão do frontend (o segredo é resolvido no start da instância, não no
deploy), CONFIRME que a senha nova autentica, e só então desative a antiga.
Desativar antes de confirmar tranca o dono do canal para fora.

```bash
gcloud run services update frontend --region us-central1 \
  --update-secrets=CSM_PASSWORD_HASH=csm-password-hash:latest
```

Ver `CSM_SECURITY_SETUP.md` para o segredo interno Next.js ↔ cmo-agent.

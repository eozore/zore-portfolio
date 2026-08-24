# éozoré — contexto para sessões de desenvolvimento

Plataforma do Victor Zoré: portfólio e blog públicos + **Content Studio**, uma
ferramenta interna que leva um tema até artigo publicado, vídeo no YouTube e
uma semana de posts agendados.

Estado da entrega: **[STATUS.md](STATUS.md)**.
Arquitetura da pipeline de vídeo: **[PIPELINE_E2E_REVIEW.md](PIPELINE_E2E_REVIEW.md)**.
Leia os dois antes de mexer em qualquer coisa do Studio.

---

## Como deployar

**Não existe GitHub Actions.** É Cloud Build, com dois triggers na `main`:

| Trigger | Config | Cobre |
|---|---|---|
| `eozore` | `cloudbuild.yaml` | cmo-agent + frontend + cromex |
| `eozore-pipeline` | `cloudbuild-pipeline.yaml` | Cloud Run Jobs, filtrado em `agents/pipeline/**` |

Então `git push origin main` deploya o que mudou. Para disparar à mão, ou para
rodar as verificações de pré-voo antes:

```bash
./scripts/deploy.sh            # pipeline e depois web, com testes antes
./scripts/deploy.sh --check    # o que está no ar agora
```

**A ordem importa**: a pipeline vai primeiro. Se o frontend novo subir antes
dos jobs, aprovar um vídeo dispara a produção pelo caminho antigo.

Projeto GCP: `vazfy-417019`, região `us-central1`.

---

## As duas interfaces

`/admin/studio` é a atual — grafo LangGraph em `agents/cmo_agent/graph/`, com
dois gates de aprovação humana e checkpoint durável em Firestore.

`/admin/csm` é a anterior, **ainda no ar como rede de segurança** até o Studio
completar um ciclo real. Roda sobre os endpoints imperativos do `agent.py`.
Quando sair, levam junto os endpoints legados que só ela usa.

Ao mexer no Studio, mexa no grafo — não nos endpoints antigos.

---

## Coisas que já custaram caro

Cada uma destas nasceu de um defeito que foi a produção. Não as reintroduza.

**Nunca parseie JSON de LLM com regex.** Use `structured.generate_structured`,
que converte o modelo Pydantic no `responseSchema` do Vertex. Foi uma falha
dessa classe que virou um vídeo de 163 segundos de avatar puro.

**Com `responseSchema` ativo o modelo tende a devolver português sem acento.**
Por isso `PT_BR_ORTOGRAFIA` é prefixado — no começo da instrução, não no fim,
onde se dilui.

**O gate do vídeo é onde o dinheiro sai.** `avatar_v` custa US$4/min de avatar
gerado. Qualquer mudança que aumente segmentos de avatar aumenta a conta.

**Falhas de custo e crédito falham ABERTO de propósito** (`_credito_insuficiente`
devolve `None` quando não consegue ler o saldo). É deliberado — mas significa
que quebrar a leitura de saldo não dá erro, só desarma o gate em silêncio.

**Um formato só entra na `social_queue` se o publisher souber publicá-lo.**
Story do Instagram é uma imagem por documento: quatro frames num documento só
publicam o primeiro e descartam três sem erro.

**Áudio é a única entrada que o HeyGen tem para inferir fonema.** Não troque
o modelo do ElevenLabs nem o formato sem entender o efeito na sincronia labial
(ver PIPELINE_E2E_REVIEW.md).

**Estilos são compartilhados entre abas.** `ArticleTab` e `ReviewTab` importam
CSS modules de abas que já não existem. Apagar um `.module.css` "órfão" quebra
o build — confira os imports, não só o `.tsx`.

---

## Antes de abrir um PR ou deployar

```bash
cd agents/pipeline  && python3 -m pytest tests -q     # 122
cd agents/cmo_agent && python3 -m pytest tests -q     #  61
cd apps/web && npx tsc --noEmit && npm run build
```

O `tsc` acusa ~33 erros pré-existentes, todos em `tools/cromex` e em dois
`lib/` antigos. O que importa é não haver erro novo em `csm/` ou `studio/`.
O `next build` ignora erro de tipo (`ignoreBuildErrors`), então o `tsc` é a
única rede.

---

## Ambiente local

```bash
docker compose -f docker-compose.local.yml up --build
```

`http://localhost:3000/admin/studio`, senha `local`. Firestore e Pub/Sub
emulados, HeyGen e ElevenLabs em stub, **Vertex AI real** (centavos por ciclo).
Ao mudar contrato de API externa, atualize `infra/local/stub_server.py` — senão
a validação local passa a testar uma API que não existe mais.

---

## Convenções

- Comentário explica **por que**, não o que. Se registra um defeito real,
  diga qual foi — é o que impede alguém de reverter a correção.
- Nomes de domínio em português (é a língua do produto); nomes de framework
  como o framework os define.
- Teste que nasce de um bug de produção diz isso na docstring.
- Nada de segredo no repositório. `CSM_PASSWORD_HASH`, chaves de API e tokens
  vivem no Secret Manager.

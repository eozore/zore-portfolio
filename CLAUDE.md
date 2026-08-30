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

**Antes de aprovar um pacote**, e não antes de deployar:

```bash
./scripts/check-credentials.sh
```

Tokens de publicação expiram sozinhos. Sem esta checagem o vídeo é gerado,
gasta ElevenLabs e HeyGen, e falha só na hora de publicar. Renove com
`./scripts/renew_token.py youtube`.

A infra da pipeline está em `infra/pipeline/`. `terraform plan` deve dizer
`No changes`; se não disser, descubra qual lado está errado antes de aplicar.
A imagem dos jobs está sob `ignore_changes` — quem manda nela é o Cloud Build.

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

**O formato do áudio é o que VEIO, não o que foi pedido.** A ElevenLabs
aceita `pcm_44100` com HTTP 200 e devolve MP3. Embrulhar isso em cabeçalho
PCM faz o arquivo mentir a duração por 5,5x: o HeyGen decodifica e vê 18s, o
`ffprobe` lê o cabeçalho e vê 3,3s, e a ilustração é cortada em 18% da fala.
Nenhuma etapa dá erro.

**O CSS do slide não pode perder o `:root`.** É onde o `slide_designer`
declara as custom properties. Apagar o bloco (para evitar vazamento de regra
de documento) deixou o manifesto com 173 `var(--…)` e zero definições — todo
o design caiu no padrão do navegador e o vídeo saiu com texto corrido a 18px.
Re-alveje para `#sid`; não apague. E não processe CSS com regex: ela entra
dentro do `@keyframes` e escopa o `to {` como seletor.

**Existem dois renderizadores de slide, e o novo troca `setTimeout` por
relógio.** `RENDERIZADOR_SLIDE=hyperframes` percorre quadro a quadro em vez de
gravar em tempo real; os reveals viram `animation-delay` porque um
renderizador que percorre quadros nunca dispara um `setTimeout`. Duas colisões
de cascata, ambas silenciosas, decidem se funciona: a regra precisa de
`!important` para vencer o `#yt-10 .fd{animation:…}` que o slide_designer
emite (1,1,0 contra 0,1,0), e o `animation-delay` precisa ficar SEM
`!important`, porque é escrevendo nele que o renderizador posiciona o quadro.
O atalho `animation` não atende as duas — por isso a regra usa propriedades
longas. Errar a segunda não quebra nada visível: o slide sai completo e
bonito, com tudo entrando no segundo zero.

**A classe `slide` é do DECK, não do slide.** O deck navega com
`body>.slide{display:none!important}` + `.slide.active`. Sem o `body>`, um
container gerado pelo slide_designer que se chame `slide` é apagado junto: a
`<section>` ganha `.active` e aparece, o div aninhado homônimo não ganha nada
e some com o conteúdo inteiro. Foi assim que 4 dos 9 slides de 29/08 saíram em
branco — 115 segundos de tela preta num vídeo de 344, sem um único erro no
job, no upload ou no YouTube. Duas trancas hoje: o `body>` na regra e
`_renomear_container_slide`, que renomeia na origem.

**O recorte é negociado ANTES de pesquisar ou escrever.** A entrada do grafo
é `briefing`, não `planejamento`: o CMO propõe ângulo, público, ferramentas
concretas, o que aparece na tela e o que precisa de fonte, e o humano responde
em rodadas por `/graph/briefing/mensagem`. Existe porque o primeiro contato
humano era o gate do artigo — quando o ângulo já estava escolhido, pesquisado
e redigido. O vídeo de SDD de 29/08 ensinou a implementação em Python quando o
pedido era mostrar arquivos `.md` numa IDE: dois vídeos legítimos para o mesmo
tema, e nada tinha perguntado qual. A conversa é ACUMULATIVA (`conversa_briefing`),
diferente do `comentario` de gate, que é pontual e some depois de aplicado.

**A pesquisa cobre duas camadas, nunca uma.** Prática (documentação, repo,
changelog — o material mostrável) e fundamento (o que sustenta a recomendação).
Uma recomendação sem fundamento é opinião com cara de método; um fundamento
sem o passo concreto é aula que ninguém aplica. `run_research` sempre aceitou
`context` e `critic_notes`, e a chamada do grafo descartava os dois: pesquisava
o título no vazio. Pior, a instrução do pesquisador dizia "evite conceitos
básicos de tutorial" — proibindo exatamente a fonte certa para tema de uso de
ferramenta, onde o arXiv não tem nada.

**O slide nunca exibe a própria narração.** Ler e ouvir a mesma frase divide
a atenção sem ganho. A regra está no prompt, mas quem barra é
`_narracao_vazou_para_a_tela` — regra em prompt é sugestão.

**Toda URL de webhook é montada num lugar só.** O token do callback é query
string; concatenar o path depois dela põe o endpoint dentro do valor do token
e o HeyGen recebe 404 na URL que você mesmo mandou. O projeto fica em
`pending_callback` para sempre, com o crédito gasto.

**Retomar produção é reusar o `projectId`, nunca aprovar o gate de novo.**
Aprovar cria `slug-yt-{timestamp}` novo e refaz o avatar a US$4/min. Retomar
da edição reaproveita os clipes do GCS e custa zero. Reabra a etapa alvo E
todas as seguintes: reabrir só o alvo deixa a próxima como `completed`, o job
ignora a mensagem, e o projeto parece reprocessado sem ter sido.

**Republicar no YouTube ATUALIZA, não sobe de novo.** O YouTube não deixa
trocar o arquivo de um vídeo, mas deixa trocar tudo em volta. Limpar o
registro de publicações para forçar upload deixou três vídeos do mesmo tema no
canal em 27/08. Só a edição — que refaz o arquivo — justifica upload novo.

**O checkpoint do LangGraph é inlistável.** O doc pai da thread nunca é
criado, e no Firestore documento que só tem subcoleção não aparece em
listagem. Quem precisa listar sessões usa `studio_sessions`, não
`graph_threads`.

**Um formato só entra na `social_queue` se o publisher souber publicá-lo.**
Story do Instagram é uma imagem por documento: quatro frames num documento só
publicam o primeiro e descartam três sem erro.

**Áudio é a única entrada que o HeyGen tem para inferir fonema.** Não troque
o modelo do ElevenLabs nem o formato sem entender o efeito na sincronia labial
(ver PIPELINE_E2E_REVIEW.md).

**O ambiente local tem que gravar num banco só.** `FIRESTORE_DATABASE`
existe porque o emulador recusa `(default)` para o cliente Python. Ela precisa
valer para o Node também — quando valia só para o Python, o artigo ia para um
banco e o grafo, a `social_queue` e os agentes para outro, sem erro nenhum. O
ambiente seguia "passando" enquanto deixava de validar todo contrato que
cruza Node↔Python, que é metade do que ele existe para pegar.

**O `seed.py` local cria os topics do Pub/Sub, não só os agentes.** O emulador
sobe vazio, e sem topic o gate do vídeo aborta em `Topic not found` — o gate
mais caro do fluxo era o único que nunca rodava localmente.

**Um ciclo de teste tem que passar pela rota do frontend.** Quem grava o
artigo no blog e dispara a produção é `/api/csm/studio`, não o grafo. Falar
direto com o `cmo-agent` pula as duas coisas e ainda devolve `fase: concluido`.

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

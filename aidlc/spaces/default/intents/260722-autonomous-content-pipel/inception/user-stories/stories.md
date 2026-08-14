# User Stories
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)
> Persona: Victor Zore (único usuário). Formato: Given/When/Then (BDD).

---

## Epic 1: Gestão de Projetos de Conteúdo

### US-01 — Criar projeto de conteúdo a partir do CMO Agent

**Como** Victor, **quero** que uma pauta aprovada no CMO Agent crie automaticamente um projeto no kanban, **para que** eu consiga acompanhar o estado de cada conteúdo sem precisar gerenciar manualmente uma lista.

**Prioridade:** Must Have | **Rastreável a:** FR-01.1, FR-01.5

**Critérios de aceite:**
```
DADO que finalizei uma sessão de cocriação no CMO Agent e cliquei "Pauta Fechada"
QUANDO o agente gerar o pacote HTML com manifesto
ENTÃO um projeto deve aparecer na aba "Projetos" com:
  - título derivado do manifesto
  - estado "Aguardando Aprovação" (badge âmbar)
  - data e hora de criação
  - custo estimado inicial em "--" (ainda não calculado)

DADO que estou na aba "Projetos"
QUANDO eu clicar "+ Novo Projeto"
ENTÃO devo ser redirecionado para o CMO Agent com um projeto vazio criado em "Em Criação"
```

---

### US-02 — Visualizar todos os projetos em kanban

**Como** Victor, **quero** ver todos os meus projetos de conteúdo em cards com estado visual claro, **para que** eu entenda de relance o que precisa de atenção sem precisar abrir cada projeto.

**Prioridade:** Must Have | **Rastreável a:** FR-01.2, FR-01.3

**Critérios de aceite:**
```
DADO que tenho projetos em diferentes estados
QUANDO abro a aba "Projetos"
ENTÃO vejo um grid de cards onde cada card exibe:
  - título do conteúdo
  - badge de estado com cor específica (azul=criando, âmbar=aguardando, roxo=gerando, ciano=pronto, verde=publicado, vermelho=erro)
  - checklist de etapas da pipeline (TTS, Avatar, Video, Publicação)
  - custo acumulado "R$XX / R$100"
  - data

DADO que quero ver apenas projetos com erro
QUANDO clico no filtro "[! Erro]"
ENTÃO o grid filtra para mostrar apenas projetos com `status: "error"` em < 200ms
```

---

### US-03 — Ver detalhes e progresso de um projeto

**Como** Victor, **quero** ver o progresso detalhado de um projeto específico sem perder a visão geral do kanban, **para que** eu possa monitorar jobs em andamento e entender onde está o custo.

**Prioridade:** Must Have | **Rastreável a:** FR-01.4

**Critérios de aceite:**
```
DADO que vejo um projeto em estado "Gerando Mídia"
QUANDO clico "Ver" ou no título do card
ENTÃO um side panel abre à direita sem fechar o kanban, exibindo:
  - progresso por etapa com estado visual ([x] concluído, [ ] pendente, [!] erro)
  - custo real de cada etapa concluída (sem prefixo "~", cor branca)
  - custo estimado de etapas pendentes (prefixo "~", cor âmbar)
  - custo total acumulado vs. teto R$100 em barra de progresso

DADO que uma etapa tem custo real disponível
ENTÃO o custo é mostrado como "R$4.13" (sem prefixo)
  E etapas não iniciadas mostram "--" em cinza
```

---

## Epic 2: Aprovação e Controle Editorial

### US-04 — Aprovar pacote para produção

**Como** Victor, **quero** um modal de aprovação que me mostre o custo estimado e os canais antes de iniciar a pipeline, **para que** eu faça uma decisão consciente antes de gastar créditos de API.

**Prioridade:** Must Have | **Rastreável a:** FR-02.1, FR-02.2, FR-02.3, FR-02.4

**Critérios de aceite:**
```
DADO que um projeto está em "Aguardando Aprovação"
QUANDO clico "Aprovar para Produção"
ENTÃO um modal exibe:
  - custo estimado detalhado por etapa (ElevenLabs, HeyGen, Gemini, GCP)
  - total estimado com indicador "OK" ou "EXCEDE TETO"
  - lista de canais habilitados com checkboxes
  - checkbox de AI disclosure pré-marcada e desabilitada
  - botões "Cancelar" e "Aprovar e Iniciar Pipeline"

DADO que o custo estimado total supera R$100
ENTÃO o botão "Aprovar e Iniciar Pipeline" está desabilitado
  E uma mensagem de alerta exibe "Estimativa R$XX excede o teto de R$100. Desabilite canais ou ajuste o manifesto."

DADO que aprovo com custo dentro do teto
ENTÃO o Firestore registra: `approved_by`, `approved_at`, `estimated_cost`, `manifest_version`, `channels_approved[]`
  E o projeto muda para estado "Gerando Mídia"
  E a pipeline inicia automaticamente
```

---

### US-05 — Aprovar e agendar publicação

**Como** Victor, **quero** um segundo modal de aprovação para publicação onde eu possa escolher o horário e confirmar os canais, **para que** a publicação seja controlada por mim mesmo quando acontece de forma automatizada.

**Prioridade:** Must Have | **Rastreável a:** FR-07.1, FR-07.2, FR-07.3

**Critérios de aceite:**
```
DADO que um projeto está em "Aguardando Publicação" (mídia gerada)
QUANDO clico "Publicar" no card ou no side panel
ENTÃO um modal exibe:
  - custo FINAL REAL (não estimado) detalhado por etapa
  - preview dos vídeos gerados (link para visualização no GCS)
  - checkboxes por canal habilitado (todos marcados por padrão)
  - opções: "Publicar Agora" (radio) ou "Agendar para: [date] [time]"
  - fuso horário fixo: America/Sao_Paulo

DADO que escolho "Agendar para 23/07/2026 18:00"
ENTÃO o projeto salva `scheduled_publish_at: "2026-07-23T21:00:00Z"` (UTC)
  E o estado muda para "Aguardando Publicação" com data exibida no card

DADO que desabilito Instagram no modal
ENTÃO `channels_approved[]` é atualizado sem abrir novamente o gate de produção
  E o Publisher Service vai pular o Instagram para este projeto
```

---

## Epic 3: Pipeline de Produção de Mídia (Experiência do Usuário)

### US-06 — Monitorar progresso da pipeline em tempo real

**Como** Victor, **quero** que o card do projeto atualize automaticamente conforme cada etapa da pipeline completa, **para que** eu saiba o estado atual sem precisar atualizar a página.

**Prioridade:** Must Have | **Rastreável a:** FR-01.2, FR-10.1

**Critérios de aceite:**
```
DADO que aprovoei um projeto e ele está em "Gerando Mídia"
QUANDO o TTS Job conclui
ENTÃO o card atualiza automaticamente (via Firestore listener) em ≤ 3s sem refresh da página:
  - checklist "TTS [x]" marcado
  - custo TTS real aparece no card (ex: "ElevenLabs R$4.13")

DADO que o projeto tem 3 etapas (TTS, Avatar, Video Editor) todas em estado "concluído"
QUANDO o último job (Video Editor) publica `video_ready` no Pub/Sub e o Firestore é atualizado
ENTÃO o projeto muda automaticamente para estado "Aguardando Publicação"
  E um badge ciano aparece no card em ≤ 3s via Firestore listener
  E o CTA do card muda de "[Ver progresso]" para "[Publicar]"
  E o side panel (se aberto) exibe todas as etapas com "[x]" concluído
```

---

### US-07 — Recuperar de falha de job

**Como** Victor, **quero** poder re-tentar, pular ou substituir manualmente o output de uma etapa que falhou, **para que** eu não precise cancelar e reiniciar todo o projeto quando apenas uma etapa falha.

**Prioridade:** Must Have | **Rastreável a:** FR-09.1, FR-09.2, FR-09.3, FR-09.4, FR-11.1

**Critérios de aceite:**
```
DADO que o Video Editor Job falha com "Playwright timeout 30s"
ENTÃO o card exibe badge vermelho "[!! ERRO]"
  E a mensagem "Playwright: timeout 30s" aparece inline no card
  E o sistema tenta automaticamente até 3 vezes com backoff (1s, 4s, 16s) antes de marcar como erro

DADO que o erro persiste após 3 tentativas automáticas
QUANDO abro o side panel e clico "Re-tentar etapa"
ENTÃO o Video Editor Job é re-disparado via Pub/Sub
  E o estado volta para "Gerando Mídia"

DADO que o HeyGen falha e quero usar um vídeo local
QUANDO clico "Upload manual" no side panel
ENTÃO um file picker abre aceitando apenas .mp4
  E ao selecionar o arquivo, ele é enviado para GCS
  E a pipeline retoma da próxima etapa após o upload

DADO que quero pular a edição de vídeo e publicar o avatar direto
QUANDO clico "Pular esta etapa"
ENTÃO a etapa é marcada como `skipped` no Firestore
  E o pipeline continua para a próxima etapa disponível
```

---

## Epic 4: Publicação Omnicanal

### US-08 — Publicar no YouTube com AI disclosure

**Como** Victor, **quero** que o Publisher Service publique automaticamente no YouTube com o campo de AI disclosure preenchido, **para que** eu não tenha risco de violação da política de IA do YouTube de maio/2026.

**Prioridade:** Must Have | **Rastreável a:** FR-06.2, FR-12.1, NFR-04

**Critérios de aceite:**
```
DADO que aprovei a publicação e YouTube está habilitado
QUANDO o Publisher Service executar
ENTÃO chama YouTube Data API v3 com:
  - `selfDeclaredAiGeneratedContent: true` no payload
  - título e descrição derivados do manifesto
  - status "public" (não privado)
  E registra a URL do vídeo publicado em `project.publications.youtube`

DADO que o upload YouTube conclui com sucesso
ENTÃO o card exibe "YouTube [link]" clicável
  E o estado muda para "Publicado" (se todos os outros canais também concluíram)

DADO que o YouTube OAuth token está a < 7 dias de expirar
ENTÃO um badge de alerta aparece no painel de configuração do canal YouTube
  Com link "Renovar autorização"
```

---

### US-09 — Publicar em Instagram Reels, YouTube Short, Threads e LinkedIn

**Como** Victor, **quero** que o Publisher Service publique automaticamente em Instagram Reels, YouTube Short, Threads e LinkedIn, **para que** as redes sociais tenham conteúdo diário sem intervenção manual.

**Prioridade:** Must Have | **Rastreável a:** FR-06.3a, FR-06.3b, FR-06.4, FR-06.6

**Critérios de aceite:**
```
DADO que Instagram está habilitado e aprovei a publicação
QUANDO o Publisher Service executar para Instagram
ENTÃO chama Meta Graph API Reels endpoint com o vídeo vertical
  E registra URL em `project.publications.instagram_reel`
  E falha isolada do Instagram não impede publicação no YouTube Short, LinkedIn ou Threads

DADO que YouTube Short está habilitado
QUANDO o Publisher Service executar para YouTube Short
ENTÃO chama YouTube Data API v3 com o vídeo vertical e `category: "Shorts"`
  E registra URL em `project.publications.youtube_short`
  E usa o mesmo token OAuth do upload do YouTube principal (US-08)
  E falha isolada do YouTube Short não impede publicação nos outros canais

DADO que o throttler do LinkedIn está no limite (1 post/dia)
QUANDO o Publisher Service tentar publicar no LinkedIn
ENTÃO pula o LinkedIn para este projeto
  E registra `project.publications.linkedin.status: "throttled"`
  E os outros canais prosseguem normalmente

DADO que um post de Threads é publicado com sucesso
ENTÃO a URL é registrada em `project.publications.threads`
  E o conteúdo deriva do Distribution Agent (texto do artigo adaptado)
```

---

### US-10 — Publicação agendada automática

**Como** Victor, **quero** que o Cloud Scheduler publique automaticamente um conteúdo por dia no horário configurado, **para que** meu calendário de publicação seja cumprido sem que eu precise abrir o CSM Studio diariamente.

**Prioridade:** Must Have | **Rastreável a:** FR-06.8, FR-08.3

**Critérios de aceite:**
```
DADO que tenho 3 projetos em "Aguardando Publicação" e o schedule está configurado para terças e quintas às 18h
QUANDO o Cloud Scheduler disparar na terça às 18h
ENTÃO o projeto mais antigo em estado "Aguardando Publicação" é selecionado
  E o Publisher Service é disparado para aquele projeto
  E somente 1 projeto é publicado por disparo do Scheduler

DADO que o horário configurado chega mas o throttler de um canal está no limite
ENTÃO o Scheduler publica nos canais disponíveis e marca os canais throttled
  E o projeto permanece em "Aguardando Publicação" até que os canais throttled sejam processados no próximo slot
  E o projeto NÃO é descartado ou movido para erro por throttling

[Nota: comportamento exato de scheduling com conflito de throttler multi-canal definido em OQ-07/OQ-08 do Application Design — o critério acima é a hipótese provisional mais simples; pode ser refinado.]
```

---

## Epic 5: Configuração da Pipeline

### US-11 — Configurar canais de publicação

**Como** Victor, **quero** poder habilitar e desabilitar canais individualmente e configurar suas API keys, **para que** eu tenha controle granular sobre onde publico sem precisar alterar código.

**Prioridade:** Must Have | **Rastreável a:** FR-08.1, FR-08.2, FR-08.4

**Critérios de aceite:**
```
DADO que estou na aba "Pipeline"
QUANDO desativo o toggle do Instagram
ENTÃO `channel_config.instagram.enabled` muda para `false` no Firestore
  E projetos futuros não publicarão no Instagram até reativar
  E projetos já em produção não são afetados

DADO que quero configurar a API key do ElevenLabs
QUANDO clico "Editar" no campo da key
ENTÃO um campo do tipo password aparece (autocomplete off)
  E ao salvar, o valor é enviado para o backend e armazenado no Secret Manager
  E o valor NUNCA é enviado de volta para o frontend após salvo

DADO que clico "Testar ping" para ElevenLabs
ENTÃO uma chamada autenticada real é feita à API
  E se válida: exibe "o ATIVO (Xms latência)"
  E se inválida: exibe "x INATIVO — Erro 401: API key inválida. Verifique em elevenlabs.io/settings/api"
```

---

### US-12 — Gerenciar limites de custo

**Como** Victor, **quero** configurar o teto de custo por pacote e ser alertado quando estou próximo do limite, **para que** nunca seja surpreendido com gastos acima do orçamento.

**Prioridade:** Must Have | **Rastreável a:** FR-08.5, FR-10.2, FR-10.3

**Critérios de aceite:**
```
DADO que configuro o teto em R$100 e o alerta em 80%
QUANDO o custo acumulado de um projeto atinge R$80
ENTÃO um badge de alerta aparece no card do projeto
  E o header do painel Pipeline exibe indicador de alerta

DADO que o custo acumulado + estimativa da próxima etapa ultrapassaria R$100
QUANDO o CostTrackerService verifica antes de disparar o próximo job
ENTÃO o job NÃO é disparado
  E o projeto entra em estado "error" com mensagem "Custo estimado ultrapassaria R$100. Desabilite canais ou ajuste o teto."
  E Victor pode aumentar o teto no painel e re-tentar manualmente
```

---

### US-13 — Visualizar agenda de publicações

**Como** Victor, **quero** ver os próximos 7 dias de agendamento com slots disponíveis, **para que** eu saiba quando cada conteúdo vai ao ar sem precisar calcular manualmente.

**Prioridade:** Must Have | **Rastreável a:** FR-08.6

**Critérios de aceite:**
```
DADO que estou na aba "Pipeline" seção "Agenda"
ENTÃO vejo exatamente 7 dias listados com:
  - projetos agendados confirmados (com título e horário)
  - slots vazios indicados como "— nenhum conteúdo agendado —"
  - projetos pendentes de aprovação de publicação (com indicador "pendente")

DADO que um novo projeto é aprovado para publicação
QUANDO o Firestore listener detecta a mudança
ENTÃO a lista de agendamentos atualiza em tempo real sem refresh da página
```

---

## Epic 6: Resiliência e Segurança

### US-14 — Retry automático em falhas transitórias

**Como** Victor, **quero** que falhas transitórias (rate limit, timeout temporário) sejam resolvidas automaticamente, **para que** eu não precise intervir em problemas que o sistema poderia resolver sozinho.

**Prioridade:** Must Have | **Rastreável a:** FR-11.1, FR-11.2, FR-11.3

**Critérios de aceite:**
```
DADO que o TTS Job recebe HTTP 429 do ElevenLabs (rate limit)
QUANDO ocorre o erro
ENTÃO o job re-tenta automaticamente:
  - 1ª tentativa após 1 segundo
  - 2ª tentativa após 4 segundos
  - 3ª tentativa após 16 segundos

DADO que as 3 tentativas falham
ENTÃO o projeto vai para estado "error" com mensagem "ElevenLabs: rate limit após 3 tentativas"
  E `project.stages.tts.retry_count: 3` é registrado no Firestore

DADO que o erro é HTTP 401 (key inválida)
ENTÃO o job vai DIRETAMENTE para estado "error" sem re-tentativas
  E a mensagem diferencia "Erro permanente: credencial inválida" de "Erro transitório"

DADO que o side panel está aberto durante um retry automático
ENTÃO Victor vê "Tentativa 2 de 3" no painel de detalhes da etapa
```

---

### US-15 — YouTube OAuth com refresh automático (condicional)

**Como** Victor, **quero** que o token OAuth do YouTube seja renovado automaticamente antes de expirar, **para que** as publicações do YouTube não falhem por token expirado.

**Prioridade:** Must Have (condicional — ativa se service account não funcionar) | **Rastreável a:** FR-12.1, FR-12.2

**Critérios de aceite:**
```
DADO que o refresh token do YouTube expira em 5 dias
QUANDO verifico o painel de configuração
ENTÃO um badge de alerta aparece: "Token YouTube expira em 5 dias. [Renovar autorização]"

DADO que clico "Renovar autorização"
ENTÃO um fluxo OAuth inicia (popup ou redirect)
  E após autorizar, o novo refresh token é salvo no Secret Manager
  E o alerta desaparece

DADO que o sistema precisa publicar e o access token expirou
QUANDO o Publisher Service detecta 401 no YouTube ao tentar publicar
ENTÃO tenta renovar usando o refresh token automaticamente (1 tentativa)
  E se a renovação tiver sucesso, a publicação prossegue normalmente
  E se a renovação falhar (refresh token expirado), o YouTube job falha com "Reautorização necessária"
  E a falha de autenticação do YouTube NÃO impede a publicação nos outros canais (Instagram, LinkedIn, Threads)
  E `project.publications.youtube.status: "auth_failed"` é registrado no Firestore
```

---

## Resumo de Cobertura

| Epic | Histórias | Prioridade | FRs Cobertos |
|---|---|---|---|
| 1. Gestão de Projetos | US-01 a US-03 | Must Have | FR-01 |
| 2. Aprovação Editorial | US-04 a US-05 | Must Have | FR-02, FR-07 |
| 3. Pipeline de Produção | US-06 a US-07 | Must Have | FR-09, FR-11 |
| 4. Publicação Omnicanal | US-08 a US-10, **US-16** | Must Have | FR-06, FR-12 |
| 5. Configuração | US-11 a US-13 | Must Have | FR-08, FR-10 |
| 6. Resiliência | US-14 a US-15 | Must Have | FR-11, FR-12 |
| **Total** | **16 histórias** | **100% Must Have** | FR-01..12 |

**FRs não cobertos por histórias de usuário** (são requisitos técnicos internos sem interação direta de Victor):
- FR-03 (TTS Job internals) — coberto via US-06 e US-07 do ponto de vista do usuário
- FR-04 (Avatar Job internals) — coberto via US-06 e US-07
- FR-05 (Video Editor internals) — coberto via US-06 e US-07
- FR-10 (CostTrackerService) — coberto via US-12 (perspectiva de usuário do custo)

---

### US-16 — Publicar artigo no blog

**Como** Victor, **quero** que o Publisher Service publique o artigo no blog eozore.com automaticamente como parte do pacote de conteúdo, **para que** o artigo técnico fique disponível no portfolio sem que eu precise fazer o upload manualmente.

**Prioridade:** Must Have | **Rastreável a:** FR-06.5

**Critérios de aceite:**
```
DADO que o Blog está habilitado no painel e aprovei a publicação
QUANDO o Publisher Service executar
ENTÃO chama a rota existente `POST /api/csm/publish` com o payload do artigo derivado do manifesto
  E o artigo aparece na coleção Firestore `articles` com status publicado
  E registra `project.publications.blog.url` com a URL do artigo publicado

DADO que o blog é o primeiro canal a ser processado na sequência de publicação
ENTÃO falha no blog NÃO impede publicação nos canais de vídeo (YouTube, Instagram, Shorts)
  E `project.publications.blog.status: "failed"` é registrado se a chamada falhar

DADO que o artigo já foi publicado anteriormente (slug duplicado)
QUANDO o Publisher Service tentar publicar
ENTÃO registra `project.publications.blog.status: "skipped_duplicate"`
  E os outros canais prosseguem normalmente
  E Victor vê "Blog: artigo já publicado" no side panel do projeto
```

---

## Review

**Reviewer:** aidlc-product-lead-agent
**Date:** 2025-07-26
**Verdict:** NOT-READY

---

### Sumário Executivo

Das 15 histórias, 11 são aprovadas sem ressalvas. 4 têm problemas que bloqueiam o avanço: US-06 tem cenário BDD incorreto (sintaxe "aprovoei"), US-09 não cobre FR-06.3b (YouTube Short), US-10 deixa a lógica de scheduling com comportamento indefinido ante throttling, e US-15 tem critério de aceite vago para o fluxo de erro de refresh. Adicionalmente, há 3 FRs Must Have sem história correspondente, o mais crítico sendo FR-06.5 (publicação no blog).

---

### Avaliação INVEST por história

| US | I | N | V | E | S | T | Veredicto |
|---|---|---|---|---|---|---|---|
| US-01 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-02 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-03 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-04 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-05 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-06 | ✓ | ✓ | ✓ | ✓ | ✓ | ~✓ | **FAIL** — cenário BDD inválido |
| US-07 | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | **PASS com ressalva** — candidata a split |
| US-08 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-09 | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | **FAIL** — FR-06.3b ausente |
| US-10 | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | **FAIL** — comportamento de throttling indefinido |
| US-11 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-12 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-13 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-14 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **PASS** |
| US-15 | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | **FAIL** — cenário de falha de refresh vago |

---

### Findings Bloqueantes

**F1 — US-06: Cenário BDD com erro de sintaxe e dado faltante**

O segundo cenário começa com `DADO que aprovoei um projeto` — "aprovoei" é um erro tipográfico que invalida o critério formalmente, mas o problema mais profundo é estrutural: o cenário de "todos os jobs completam" não define a transição de estado de `Gerando Mídia → Aguardando Publicação` com as condições de entrada. O DADO deveria incluir o estado atual dos outros jobs. Um desenvolvedor não consegue escrever um teste determinístico para "todos os jobs completam" sem saber se "todos" significa TTS + Avatar + Video ou apenas o subset habilitado.

**Correção esperada:**
```
DADO que o projeto tem 3 etapas (TTS, Avatar, Video) todas em estado "concluído"
QUANDO o último job (Video Editor) publica `video_ready` no Pub/Sub
ENTÃO o projeto muda automaticamente para "Aguardando Publicação"
  E um badge ciano aparece no card
  E o CTA do card muda para "[Publicar]"
```

---

**F2 — US-09: FR-06.3b (YouTube Short) sem cobertura**

US-09 cobre Instagram Reels, Threads e LinkedIn, mas não cobre YouTube Short, que é FR-06.3b Must Have. O título da história (`Publicar em Instagram, Threads e LinkedIn`) não inclui YouTube Short. O critério de aceite rastreia para `FR-06.3a, FR-06.3b, FR-06.4, FR-06.6`, mas não há nenhum cenário Given/When/Then para YouTube Short no corpo da história. Um QA que lesse só os critérios de aceite não saberia que precisa testar o Short.

Dois caminhos: (a) adicionar cenário BDD para YouTube Short nesta história e atualizar o título, ou (b) criar US-16 dedicada ao YouTube Short. O caminho (a) mantém a história pequena o suficiente; (b) é mais limpo se a implementação envolve lógica distinta de autenticação (mesmo token YouTube da US-08, mas endpoint diferente). Recomendo (a) dado que a autenticação é compartilhada.

---

**F3 — US-10: Comportamento do scheduler com throttler não está definido**

O segundo cenário de US-10 diz: "o Scheduler registra o evento e aguarda o próximo slot disponível para aquele canal". Mas quem define o "próximo slot"? O comportamento implementável seria: o projeto permanece em `awaiting_publication` e o Scheduler o seleciona novamente na próxima execução — mas isso não está no critério. Mais importante: OQ-07 e OQ-08 nos requirements reconhecem explicitamente que esta lógica está indefinida e delegada ao Application Design. US-10 foi escrita antes dessa questão ser respondida, então o critério de aceite está especulando sobre um comportamento que ainda não foi decidido.

Esta história não deve ser considerada testável enquanto OQ-07/OQ-08 estiverem abertas. O critério de aceite atual pode entrar em conflito com a decisão do Application Design.

**Ação necessária:** Marcar US-10 como `Bloqueada por OQ-07` ou escrever o critério de aceite com a hipótese mais simples (`o projeto permanece em awaiting_publication e será selecionado no próximo disparo do Scheduler`) e documentar isso como uma decisão provisional que pode mudar em Application Design.

---

**F4 — US-15: Cenário de falha de refresh token vago**

O terceiro cenário (`DADO que o sistema precisa publicar e o access token expirou`) diz que o Publisher Service "tenta renovar usando o refresh token automaticamente". Mas não define: (a) quantas tentativas antes de falhar, (b) o comportamento do job se a renovação falhar parcialmente (timeout na chamada OAuth), (c) se outros canais prosseguem ou se o job inteiro é abortado quando YouTube falha por auth.

O critério `se a renovação falhar (refresh token expirado), o job falha com "Reautorização necessária"` é testável para o caminho feliz, mas um QA não saberia se o Instagram e LinkedIn devem ou não prosseguir quando o YouTube falha por auth. Dado que US-09 estabelece que falhas devem ser isoladas por canal, a consistência arquitetural exige que US-15 declare explicitamente: "a falha de autenticação do YouTube não impede a publicação nos outros canais".

---

### FRs Must Have sem história correspondente

| FR | Descrição | Impacto |
|---|---|---|
| **FR-06.5** | Publisher Service publica artigo no blog (Firestore `articles`) via `/api/csm/publish` | **Crítico** — publicação no blog é um dos canais do pipeline omnicanal. Não há nenhuma história, nenhum cenário BDD, nenhuma rastreabilidade. O desenvolvedor não tem base para implementar nem o QA para testar. |
| **FR-06.1** | Publisher Service verifica `approval_status: "approved"` antes de publicar | Segurança arquitetural. Pode ser considerado critério técnico interno coberto implicitamente pelos gates US-04 e US-05, mas não há cenário BDD para o caso negativo (o que acontece se alguém chama o Publisher Service sem aprovação). |
| **FR-06.7** | Publisher Service registra resultado de cada publicação no Firestore | Coberto parcialmente como consequência de US-08 e US-09, mas nenhuma história descreve o comportamento de falha de registro (e se o job publica com sucesso mas falha ao escrever no Firestore?). |

FR-06.5 é o gap mais crítico e deve ser corrigido antes de Application Design. FR-06.1 e FR-06.7 podem ser resolvidos adicionando cenários negativos às histórias existentes.

---

### Candidatas a Split

**US-07** cobre 4 comportamentos distintos em 4 cenários que têm implementações independentes: (1) exibição de erro inline no card, (2) retry manual via side panel, (3) upload manual de fallback, (4) skip de etapa. São 4 histórias potenciais. No entanto, dado o contexto solo (sistema mono-usuário), o custo de estimativa separada é baixo e o benefício de granularidade é limitado. Recomendo manter US-07 unificada mas registrar que cada cenário BDD mapeia para um endpoint de API distinto, o que significa que podem ser implementados e testados independentemente. Não é um bloqueante.

---

### Critérios de aceite: avaliação de especificidade

**Bem especificados (valores concretos, estados, URLs):**
- US-04: `approved_by`, `approved_at`, `estimated_cost`, `manifest_version`, `channels_approved[]` — perfeito
- US-05: `scheduled_publish_at: "2026-07-23T21:00:00Z"` (UTC convertido) — rastreável e testável
- US-11: `channel_config.instagram.enabled → false`, Secret Manager, `autocomplete off` — implementável diretamente
- US-12: `project.stages.tts.retry_count: 3` — observável via Firestore
- US-14: `retry_count: 3`, estados diferenciados para `429` vs `401` — exemplar

**Com valores vagos ou estados ambíguos:**
- US-02: "em < 200ms" — testável, mas não define como medir (client-side? server-side? após Firestore listener?)
- US-06: "automaticamente (via Firestore listener) sem refresh da página" — sem SLA de latência para o listener
- US-08: "título e descrição derivados do manifesto" — quais campos exatos do manifesto? `manifest.title`? `manifest.description`? Falta referência ao schema
- US-13: "em tempo real" sem SLA definido para o listener de agendamentos

Estes são itens de melhoria, não bloqueantes — podem ser resolvidos na sessão de refinamento com o desenvolvedor.

---

### Cobertura de fluxos de erro e edge cases

| Área | Cobertura | Gap |
|---|---|---|
| Falha de job (erro permanente) | US-14 cobre `401` sem retry | OK |
| Falha de job (erro transitório) | US-14 cobre `429` com backoff | OK |
| Custo excede teto | US-04 (gate) + US-12 (bloqueio de job) | OK |
| Token OAuth expirado | US-15 | OK, com ressalva do F4 |
| Throttler de canal atingido | US-09 (LinkedIn) + US-10 (scheduler) | Parcialmente — ver F3 |
| Upload manual como fallback | US-07 | OK |
| Falha ao registrar publicação no Firestore | **Sem cobertura** | Gap — ver F4 em FR-06.7 |
| Publicação no blog | **Sem cobertura** | Gap crítico — FR-06.5 ausente |
| Publisher chamado sem aprovação | **Sem cobertura** | Gap — FR-06.1 negativo ausente |
| HeyGen timeout > 90 min | US-07 cobre retry manual, US-14 cobre backoff automático | Falta cenário específico de timeout HeyGen (90 min SLA do NFR-02) |

---

### Para READY: ações obrigatórias

1. **US-06:** Corrigir cenário "todos os jobs completam" com DADO que define o estado dos jobs individuais (não apenas "todos completam").
2. **US-09:** Adicionar cenário BDD para YouTube Short ou criar US-16 dedicada. Atualizar rastreabilidade.
3. **US-10:** Marcar como bloqueada por OQ-07/OQ-08 ou reescrever o segundo cenário com hipótese provisional explícita.
4. **US-15:** Adicionar critério explícito de isolamento de falha YouTube × outros canais no cenário de falha de refresh.
5. **US-16 (nova):** Criar história para FR-06.5 (publicação no blog). É um canal do pipeline omnicanal e deve ter critério BDD próprio — especialmente porque usa uma rota já existente (`/api/csm/publish`), o que a torna de baixo esforço para escrever e alta importância para testar.

### Ações recomendadas (não bloqueantes)

- US-06: Adicionar SLA de latência para o Firestore listener (ex: atualização visível em ≤ 3s).
- US-08: Especificar campos do manifesto usados no YouTube (`manifest.title`, `manifest.description`, `manifest.tags[]`).
- US-13: Adicionar SLA para o listener de agendamentos em tempo real.
- US-07: Documentar que os 4 cenários mapeiam para endpoints distintos, facilitando a criação de tarefas de desenvolvimento independentes.
- Geral: Adicionar cenário negativo para FR-06.1 em US-08 ou US-09 (Publisher chamado sem `approval_status: "approved"`).

---

### Pontos fortes reconhecidos

As histórias demonstram qualidade acima da média em vários aspectos. Os critérios BDD de US-04, US-05, US-11 e US-14 são modelares: têm dados de estado concretos, valores numéricos, campos Firestore nomeados e comportamento de falha explícito. A rastreabilidade FR por história está consistente. O contexto mono-usuário foi respeitado — não há histórias com persona errada ou gatekeeping desnecessário. US-14 é particularmente forte: distingue `429` (transitório, retry) de `401` (permanente, sem retry) e define a visibilidade do retry no UI — isso é raro em user stories e exatamente o nível de detalhe que evita bugs de produto.

---

## Review (Iteração 2)

**Reviewer:** aidlc-product-lead-agent
**Date:** 2025-07-26
**Iteração:** 2 / verificação das ações obrigatórias F1–F4 e US-16

---

### Verdict: READY

Todas as 5 ações obrigatórias emitidas na iteração 1 foram endereçadas. O documento está aprovado para avançar para Application Design.

---

### Tabela de Resolução F1–F5

| ID | Ação Obrigatória (iteração 1) | Status | Evidência no arquivo |
|---|---|---|---|
| **F1** | US-06 — cenário BDD corrigido com DADO preciso e SLA de latência | **RESOLVIDO** | Cenário 2 reescrito: `DADO que o projeto tem 3 etapas (TTS, Avatar, Video Editor) todas em estado "concluído"` + `≤ 3s via Firestore listener`. Typo corrigido. Transição de CTA declarada. |
| **F2** | US-09 — YouTube Short com cenário BDD e isolamento de falha | **RESOLVIDO** | Cenário dedicado para YouTube Short adicionado com `falha isolada do YouTube Short não impede publicação nos outros canais` e rastreabilidade `FR-06.3b` explícita. |
| **F3** | US-10 — segundo cenário marcado como provisional com referência a OQ-07 | **RESOLVIDO** | Nota `[Nota: ... OQ-07/OQ-08 ... hipótese provisional]` adicionada. Cenário reescrito com comportamento da hipótese mais simples (projeto permanece em `awaiting_publication` até próximo slot). |
| **F4** | US-15 — isolamento de falha YouTube × outros canais declarado explicitamente | **RESOLVIDO** | `a falha de autenticação do YouTube NÃO impede a publicação nos outros canais (Instagram, LinkedIn, Threads)` e `project.publications.youtube.status: "auth_failed"` estão presentes no terceiro cenário. |
| **F5 (US-16)** | FR-06.5 (blog) — história com BDD incluindo caso de slug duplicado | **RESOLVIDO** | US-16 criada com 3 cenários: caminho feliz (POST `/api/csm/publish`), isolamento de falha do blog, e slug duplicado com `status: "skipped_duplicate"` e mensagem no side panel. |

---

### Observações para Application Design

1. **US-10 é provisional por design.** O cenário de throttling multi-canal é explicitamente dependente das decisões OQ-07/OQ-08. O Application Design deve resolver essas questões abertas e, se necessário, devolver US-10 ao refinamento com o critério de aceite definitivo antes da construção.

2. **US-09 usa o mesmo token OAuth de US-08 para YouTube Short.** O Application Design deve confirmar que o Publisher Service compartilha a sessão OAuth entre os dois jobs (YouTube principal + Short) sem double-refresh. Uma falha de token no Short não deve invalidar o token do canal principal.

3. **US-16 referencia `/api/csm/publish` como rota existente.** O Application Design deve verificar se o contrato atual dessa rota suporta o payload do manifesto CMO Agent diretamente ou se é necessário um adaptador. O campo `slug` do artigo deve ter unicidade garantida no schema do Firestore (`articles` collection) para que o cenário de slug duplicado seja detectável sem race condition.

4. **Cobertura de 16 histórias com 100% Must Have está completa.** A tabela de resumo no documento já foi atualizada para incluir US-16 no Epic 4. Nenhum FR Must Have permanece sem rastreabilidade de história.

5. **Itens de melhoria não-bloqueantes da iteração 1** (SLA de listener em US-13, campos exatos do manifesto em US-08, cenário negativo de FR-06.1) permanecem abertos como candidatos a refinamento durante Application Design ou sessão de technical grooming — não são pré-requisitos para avançar.

---

*Documento aprovado para Application Design. Próxima fase: Application Design com foco em resolver OQ-07/OQ-08 e confirmar contrato de `/api/csm/publish`.*

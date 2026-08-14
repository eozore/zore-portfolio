# User Flow
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [intent-statement.md](../intent-capture/intent-statement.md) | [scope-document.md](../scope-definition/scope-document.md) | [intent-backlog.md](../scope-definition/intent-backlog.md)

---

## Fluxo Principal: Semana Completa de Produção

```
+---------------------+
|  Victor abre CSM    |
|  Studio no browser  |
+---------------------+
          |
          v
+---------------------+     ja tem pacote?     +---------------------------+
|  Aba "Projetos"     | -------- SIM --------> |  Clica no card do projeto |
|  (kanban overview)  |                         |  para ver status atual    |
+---------------------+                         +---------------------------+
          |                                               |
          | NAO (nova semana)                             v
          v                                     [ver fluxo de revisao abaixo]
+---------------------+
|  Clica "+ Novo      |
|  Projeto"           |
+---------------------+
          |
          v
+---------------------+
|  Aba "Bate-Papo     |
|  CMO" (ja existe:   |
|  IdeaTab)           |
|  Sessao de          |
|  cocriacao          |
+---------------------+
          |
          | CMO emite "Pauta Fechada!"
          v
+---------------------+
|  CMO Agent gera     |
|  pacote HTML com    |
|  manifesto JSON     |
|  (automatico)       |
+---------------------+
          |
          v
+---------------------+
|  Aba "Projetos"     |
|  Card criado com    |
|  status:            |
|  "Aguardando        |
|  Aprovacao"         |
+---------------------+
          |
          | Victor clica "Aprovar para Producao"
          v
+---------------------+     custo estimado > R$100?     +---------------------+
|  Modal de           | ---------- SIM --------------> |  Alerta de custo:   |
|  confirmacao:       |                                 |  "Estimativa: R$XX  |
|  preview do pacote  |                                 |  acima do limite.   |
|  + custo estimado   |                                 |  Continuar?"        |
+---------------------+                                 +---------------------+
          |                                                        |
          | NAO (dentro do limite) ou usuario confirma             |
          v <------------------------------------------------------+
+---------------------+
|  Status: "Gerando   |
|  Midia"             |
|  Spinner animado    |
|  por etapa:         |
|  [x] TTS Audio      |
|  [ ] Avatar Video   |
|  [ ] Edicao Video   |
+---------------------+
          |
          | Pipeline completa (pode levar 30-60 min)
          v
+---------------------+
|  Status: "Aguardando|
|  Publicacao"        |
|  Notificacao no     |
|  browser/email      |
+---------------------+
          |
          | Victor decide: publicar agora ou agendar
          v
+---------------------+     Publicar Agora     +---------------------+
|  Modal de           | ----- clica ----------> |  Publicando em      |
|  publicacao:        |                          |  todos os canais    |
|  checkboxes por     |                          |  habilitados...     |
|  canal habilitado   |                          +---------------------+
|  + horario opcional |                                    |
+---------------------+                                    v
                                               +---------------------+
                                               |  Status: "Publicado"|
                                               |  Links por canal    |
                                               |  Custo final: R$XX  |
                                               +---------------------+
```

---

## Fluxo Secundário: Configuracao de Canal

```
+---------------------+
|  Aba "Pipeline"     |
|  (nova aba)         |
+---------------------+
          |
          v
+---------------------+
|  Secao: Canais      |
|  [toggle] YouTube   |
|  [toggle] Instagram |
|  [toggle] LinkedIn  |
|  [toggle] Threads   |
|  [toggle] Facebook  |
|  [toggle] Blog      |
+---------------------+
          |
          | Clica no canal para expandir
          v
+---------------------+
|  Configuracao do    |
|  Canal (expandido): |
|  - API Key/Token    |
|    [campo mascarado]|
|  - Horario padrao   |
|    [time picker]    |
|  - Limite diario    |
|    [numero]         |
|  [Salvar]           |
+---------------------+
          |
          v
+---------------------+
|  Confirmacao:       |
|  "Configuracoes     |
|  salvas com         |
|  seguranca no       |
|  Secret Manager"    |
+---------------------+
```

---

## Fluxo de Recuperacao: Etapa com Erro

```
+---------------------+
|  Card do projeto    |
|  com badge          |
|  "Erro na Edicao"   |
|  (red badge)        |
+---------------------+
          |
          | Clica no card
          v
+---------------------+
|  Detalhe do erro:   |
|  "Video Editor Job  |
|  falhou: Playwright |
|  timeout"           |
|  [mensagem do log]  |
+---------------------+
          |
          v
+---------------------+
|  Opcoes de          |
|  recuperacao:       |
|  [Re-tentar]        |
|  [Pular esta etapa] |
|  [Upload manual]    |
+---------------------+
```

---

## Hierarquia de Informacao — Aba Projetos

```
Aba "Projetos"
+-- Header: "Projetos de Conteudo" + botao "+ Novo"
+-- Filtros: [Todos] [Em Criacao] [Aguardando] [Publicado]
+-- Grid de cards (4 colunas desktop, 2 tablet, 1 mobile)
    +-- Card de Projeto
        +-- Titulo do conteudo (h3)
        +-- Status badge (color-coded)
        +-- Progress bar da pipeline (etapas)
        +-- Custo acumulado (R$XX / R$100)
        +-- Data de criacao
        +-- Acoes contextuais (Aprovar / Ver / Re-tentar)
```

---

## Hierarquia de Informacao — Aba Pipeline (Configuracao)

```
Aba "Pipeline"
+-- Secao: "Configuracao de Canais"
|   +-- Lista de canais com toggle
|   +-- Expandable: config por canal
|
+-- Secao: "Limites de Custo"
|   +-- Teto por video (R$100 default)
|   +-- Alerta em % do teto (80% default)
|
+-- Secao: "APIs Externas"
|   +-- ElevenLabs API Key [campo mascarado]
|   +-- HeyGen API Key [campo mascarado]
|   +-- Status de cada API (ping indicator)
|
+-- Secao: "Agenda"
    +-- Horario padrao de publicacao por dia da semana
    +-- Preview: proximo conteudo agendado
```

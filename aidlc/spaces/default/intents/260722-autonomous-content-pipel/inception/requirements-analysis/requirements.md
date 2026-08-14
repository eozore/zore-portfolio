# Requirements Analysis
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Referências: [intent-statement.md](../../ideation/intent-capture/intent-statement.md) | [scope-document.md](../../ideation/scope-definition/scope-document.md) | [team-practices.md](../practices-discovery/team-practices.md)

---

## Análise de Intent

**O que Victor está tentando alcançar:** Recuperar a consistência de presença nas redes sociais sem aumentar o tempo de produção. O problema não é gerar conteúdo de qualidade — o CMO Agent já faz isso. O problema é a **cadeia de transformação** entre o conteúdo gerado e a publicação distribuída em múltiplos formatos. A pipeline deve automatizar essa cadeia completamente, com Victor intervindo apenas na cocriação intelectual e na aprovação.

**Não é sobre:** volume de conteúdo. É sobre **eliminar o silêncio** que ocorre quando Victor não tem tempo para a cadeia manual.

---

## Requisitos Funcionais

### FR-01: Gestão de Projetos de Conteúdo (Kanban)

**Domínio:** CSM Studio — Aba "Projetos"

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-01.1 | O sistema deve criar um documento de projeto no Firestore (`content_projects`) quando Victor aprovar uma pauta no CMO Agent | Must | Projeto criado com `status: "awaiting_approval"`, `manifest_url`, `created_at`, `created_by` |
| FR-01.2 | O CSM Studio deve exibir todos os projetos como cards num kanban com 7 estados visuais distintos | Must | Cards exibem: título, status badge colorido, progress bar das etapas, custo R$XX/R$100, data |
| FR-01.3 | Victor deve poder filtrar projetos por estado (Todos, Em Criação, Aguardando, Gerando, Pronto, Publicado, Erro) | Must | Filtro atualiza a grid em < 200ms sem recarregar a página |
| FR-01.4 | O side panel de detalhes deve exibir o progresso de cada etapa do pipeline com custo real vs. estimado por etapa | Must | Custo estimado em âmbar (`~R$XX`), custo real em branco (`R$XX`), não executado em cinza (`--`) |
| FR-01.5 | Victor deve poder criar um novo projeto a partir da aba "Projetos" com navegação direta para o CMO Agent | Must | Botão "+ Novo Projeto" → cria projeto em Firestore com `status: "creating"` → navega para IdeaTab |

### FR-02: Gate de Aprovação para Produção

**Domínio:** Modal de Aprovação (Tela 4 nos wireframes)

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-02.1 | Victor deve aprovar explicitamente antes da pipeline de geração de mídia iniciar | Must | Modal exibe: custo estimado por etapa, canais configurados, checkbox de AI disclosure |
| FR-02.2 | O sistema deve bloquear o início da pipeline se o custo estimado total exceder R$100 | Must | Modal exibe alerta de custo excedido; botão "Aprovar" desabilitado; opção "Editar canais" disponível |
| FR-02.3 | Os dados de aprovação devem ser armazenados no Firestore | Must | Documento contém: `approved_by`, `approved_at`, `estimated_cost`, `manifest_version`, `channels_approved[]` |
| FR-02.4 | O campo de AI disclosure deve ser pré-preenchido como `true` e não editável pelo usuário | Must | Checkbox marcada e desabilitada com tooltip explicando a política YouTube |

### FR-03: Pipeline de TTS — ElevenLabs

**Domínio:** TTS Job (Cloud Run Job)

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-03.1 | O TTS Job deve ler o manifesto JSON do pacote HTML aprovado no Firestore e gerar um arquivo de áudio MP3 por segmento | Must | Para cada `segment.id` no manifesto: arquivo `{video_id}__{segment_id}.mp3` gerado no GCS |
| FR-03.2 | O TTS Job deve usar a voz clonada de Victor (configurada no painel) via ElevenLabs API | Must | `voice_id` lido do Secret Manager; modelo `eleven_flash_v2_5` usado por padrão (Flash v2.5: <75ms latência, 32 idiomas, recomendado pelo ElevenLabs sobre Turbo) |
| FR-03.3 | O TTS Job deve publicar uma mensagem Pub/Sub `tts_completed` com referências para os arquivos de áudio no GCS após conclusão | Must | Mensagem contém: `project_id`, `gcs_audio_paths[]`, `segment_count`, `total_chars`, `cost_usd` |
| FR-03.4 | O TTS Job deve reportar o custo de cada chamada ElevenLabs ao CostTrackerService | Must | Custo calculado como `chars * rate_per_char` e salvo em `project.cost_breakdown.tts` |
| FR-03.5 | O TTS Job deve suportar reprocessamento de um subconjunto de segmentos (fallback manual) | Should | Endpoint de invocação aceita `segment_ids[]` opcionais; se ausentes, processa todos |

### FR-04: Pipeline de Avatar — HeyGen Lipsync

**Domínio:** Avatar Job (Cloud Run Job)

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-04.1 | O Avatar Job deve concatenar os áudios por segmento em um único arquivo de áudio para o vídeo horizontal | Must | Concatenação respeita a ordem dos segmentos do manifesto com `pause_after_s` aplicado |
| FR-04.2 | O Avatar Job deve fazer upload do áudio concatenado para HeyGen Assets API e obter um `asset_id` | Must | `POST /v3/assets` retorna `asset_id` válido armazenado no Firestore do projeto |
| FR-04.3 | O Avatar Job deve criar um job de Lipsync via `POST /v3/lipsyncs` usando o avatar base e o áudio, no modo `precision` | Must | Job criado com `mode: "precision"`, `callback_url` configurado para o Publisher Service |
| FR-04.4 | O Avatar Job deve processar separadamente o vídeo horizontal (1920×1080) e o vertical (1080×1920) | Must | Dois jobs HeyGen criados por pacote de conteúdo; dois `lipsync_id` armazenados |
| FR-04.5 | Quando o callback HeyGen confirmar conclusão, o Avatar Job deve baixar os vídeos para GCS | Must | Vídeos salvos em `gs://{bucket}/projects/{project_id}/avatar_horizontal.mp4` e `avatar_vertical.mp4` |
| FR-04.6 | O Avatar Job deve reportar o custo HeyGen ao CostTrackerService | Must | Custo calculado e salvo em `project.cost_breakdown.heygen` |
| FR-04.7 | Victor deve poder fazer upload manual de um arquivo MP4 de avatar como fallback | Must | Endpoint `POST /api/csm/projects/{id}/stages/avatar/manual-upload` aceita arquivo MP4, salva no GCS e retoma o pipeline |

### FR-05: Pipeline de Edição de Vídeo

**Domínio:** Video Editor Job (Cloud Run Job)

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-05.1 | O Video Editor Job deve ler o manifesto e renderizar cada slide HTML como clipe de vídeo pela duração exata do segmento de áudio correspondente | Must | Mapeamento `segment.id → segment.slide` do manifesto; duração = duração do arquivo MP3 do segmento + `pause_after_s` |
| FR-05.2 | O Video Editor Job deve compor o vídeo horizontal sobrepondo os clips de slides sobre o vídeo avatar em 1920×1080 | Must | FFmpeg filter_complex com overlay; saída `final_horizontal.mp4` |
| FR-05.3 | O Video Editor Job deve compor o vídeo vertical sobrepondo os clips de slides sobre o vídeo avatar em 1080×1920 | Must | FFmpeg filter_complex com overlay; saída `final_vertical.mp4` |
| FR-05.4 | O Video Editor Job deve aplicar jump cuts (remover silêncios > 0.8s) nos vídeos finais | Should | `final_horizontal_cut.mp4` e `final_vertical_cut.mp4` após processamento |
| FR-05.5 | O Video Editor Job deve publicar `video_ready` no Pub/Sub com as URLs dos vídeos finais | Must | Mensagem contém: `project_id`, `horizontal_url`, `vertical_url`, `duration_seconds` |
| FR-05.6 | Playwright deve renderizar slides HTML em resolução correspondente ao formato (1920×1080 ou 1080×1920) | Must | Chromium headless com viewport correto; cada slide renderizado como WebM e convertido para MP4 |

### FR-06: Publisher Service — Publicação Omnicanal

**Domínio:** Publisher Service (Cloud Run Job)

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-06.1 | O Publisher Service deve verificar `approval_status: "approved"` no Firestore antes de publicar em qualquer canal | Must | Publicação bloqueada com log de erro se status ≠ "approved" |
| FR-06.2 | O Publisher Service deve publicar o vídeo horizontal no YouTube com AI disclosure obrigatório | Must | YouTube Data API v3 com `selfDeclaredAiGeneratedContent: true`; título, descrição e tags do manifesto |
| FR-06.3a | O Publisher Service deve publicar o vídeo vertical como Instagram Reel | Must | Meta Graph API Reels endpoint chamado com sucesso; URL do Reel publicado salva em `project.publications[instagram_reel]`; falha isolada não afeta publicação no YouTube Short |
| FR-06.3b | O Publisher Service deve publicar o vídeo vertical como YouTube Short | Must | YouTube Data API v3 chamada com `category: "Shorts"`; URL do Short salva em `project.publications[youtube_short]`; falha isolada não afeta publicação no Instagram Reel |
| FR-06.4 | O Publisher Service deve publicar posts de texto derivados no LinkedIn e Threads | Must | LinkedIn `ugcPosts` API + Meta Graph API Threads; conteúdo do Distribution Agent |
| FR-06.5 | O Publisher Service deve publicar o artigo no blog (Firestore `articles`) | Must | Usa rota existente `/api/csm/publish` |
| FR-06.6 | O Publisher Service deve respeitar o throttler configurado no painel (max N posts/dia/canal) | Must | Consulta `channel_config.{channel}.max_per_day`; cancela publicação naquele canal se limite atingido |
| FR-06.7 | O Publisher Service deve registrar resultado de cada publicação no Firestore | Must | `project.publications[].{channel, url, published_at, status}` para cada canal |
| FR-06.8 | O Cloud Scheduler deve verificar diariamente se há projetos em `awaiting_publication` e publicar o mais antigo no horário configurado | Must | Job diário lê `channel_config.schedule`, seleciona projeto mais antigo aprovado, dispara Publisher Service |

### FR-07: Gate de Aprovação de Publicação

**Domínio:** Modal de Publicação (Tela 4B nos wireframes)

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-07.1 | Victor deve aprovar explicitamente a publicação antes do Publisher Service executar | Must | Modal exibe: custo final real, preview dos vídeos (links GCS), canais com checkboxes, opção "Publicar Agora" vs "Agendar" |
| FR-07.2 | Victor deve poder selecionar um horário de publicação no modal | Must | Date/time picker com fuso `America/Sao_Paulo`; salvo em `project.scheduled_publish_at` |
| FR-07.3 | Victor deve poder desabilitar canais individuais antes da publicação | Must | Checkbox por canal no modal; desabilitar um canal atualiza `channels_approved[]` sem reabrir o gate de produção |

### FR-08: Painel de Configuração da Pipeline

**Domínio:** CSM Studio — Aba "Pipeline"

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-08.1 | Victor deve poder habilitar/desabilitar cada canal de publicação individualmente | Must | Toggle por canal com persistência em `channel_config.{channel}.enabled` no Firestore |
| FR-08.2 | Victor deve poder configurar API keys (ElevenLabs, HeyGen) e tokens OAuth via interface | Must | Campos mascarados (`type="password"`); valores salvos no GCP Secret Manager via Cloud Run backend |
| FR-08.3 | Victor deve poder configurar o horário padrão de publicação por dia da semana por canal | Must | Time picker + seletor de dias; salvo em `channel_config.{channel}.schedule` |
| FR-08.4 | O painel deve exibir o status de conectividade de cada API externa com botão "Testar ping" | Must | Ping testa autenticação real (ElevenLabs: `GET /v1/models`, HeyGen: `GET /v3/voices`); exibe latência ou erro inline |
| FR-08.5 | Victor deve poder configurar o teto de custo por pacote e o percentual de alerta | Must | Campo numérico para limite (default: R$100) e percentual de alerta (default: 80%); salvo em `pipeline_config.cost_limit` |
| FR-08.6 | O painel deve exibir a fila dos próximos 7 dias de agendamentos, com indicação de slots vazios e projetos pendentes de aprovação de publicação | Must | Lista exibe exatamente 7 dias; cada dia mostra: projeto agendado (se houver), slot vazio, ou projeto pendente de aprovação; dados atualizados em tempo real via Firestore listener |

### FR-09: Recuperação Manual e Fallback

**Domínio:** Side Panel do Kanban + endpoints de fallback

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-09.1 | Victor deve poder re-tentar uma etapa com falha individualmente | Must | Botão "Re-tentar etapa" no side panel; re-dispara o job específico via Pub/Sub |
| FR-09.2 | Victor deve poder pular uma etapa com falha | Must | Botão "Pular esta etapa"; marca etapa como `skipped` no Firestore; pipeline continua da próxima etapa |
| FR-09.3 | Victor deve poder fazer upload manual de vídeo MP4 para substituir o output de qualquer job de vídeo | Must | `POST /api/csm/projects/{id}/stages/{stage}/manual-upload`; aceita MP4; salva no GCS; retoma pipeline |
| FR-09.4 | Erros de jobs devem aparecer inline no card do kanban com a mensagem do log | Must | `project.stages[].error_message` exibida no card em badge vermelho com texto do erro |

### FR-11: Retry Automático e Resiliência

**Domínio:** Transversal — todos os Cloud Run Jobs

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-11.1 | Cada Cloud Run Job deve re-tentar automaticamente em falhas transitórias (HTTP 429, 503, timeout de rede) com backoff exponencial | Must | Máximo 3 tentativas automáticas com backoff (1s, 4s, 16s) antes de mover para estado `error`; cada tentativa registrada no log do projeto |
| FR-11.2 | Falhas permanentes (HTTP 401/403, formato inválido, asset_id não encontrado) não devem ser re-tentadas automaticamente | Must | Erros 4xx (exceto 429) movem o job diretamente para estado `error` sem retry; mensagem de erro diferencia falha permanente de transitória |
| FR-11.3 | O status de cada tentativa de retry deve ser visível no side panel do kanban | Should | `project.stages[].retry_count` exibido no side panel; "Tentativa 2 de 3" visível no card |

### FR-12: Autenticação YouTube — Fluxo Alternativo

**Domínio:** Publisher Service — YouTube

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-12.1 | Se YouTube Data API v3 não aceitar service account para upload em nome do canal de Victor, o sistema deve suportar autenticação OAuth 2.0 de usuário com refresh token de longa duração | Must (condicional A-05) | Token OAuth salvo no Secret Manager; refresh automático antes de expiração; upload de vídeo bem-sucedido via token renovado |
| FR-12.2 | O painel deve exibir alerta quando o refresh token do YouTube estiver próximo de expirar (< 7 dias) | Must (condicional A-05) | Badge de alerta no card de configuração do canal YouTube; link direto para reautorização |



### FR-10: CostTrackerService

**Domínio:** Transversal — todos os jobs

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| FR-10.1 | O CostTrackerService deve acumular e exibir o custo em tempo real por etapa e por pacote | Must | Firestore `project.cost_breakdown` atualizado após cada chamada de API paga; exibido no kanban |
| FR-10.2 | O CostTrackerService deve bloquear o início de uma etapa se o custo acumulado + estimativa da próxima etapa exceder o teto | Must | Gate verificado antes de cada job; se exceder: job não inicia, erro exibido no painel |
| FR-10.3 | O CostTrackerService deve alertar Victor via notificação no painel quando custo atingir 80% do teto | Should | Badge de alerta no card do projeto + indicador no header do painel quando cost ≥ 80% do limite |

---

## Requisitos Não-Funcionais

| ID | Categoria | Requisito | Métrica | Fonte |
|---|---|---|---|---|
| NFR-01 | **Custo** | Custo máximo por pacote completo | ≤ R$100 (todos os canais habilitados) | constraint-register CO-01 |
| NFR-02 | **Performance** | Latência de processamento total (TTS + Avatar + Editor), excluindo o tempo assíncrono de renderização HeyGen | ≤ 30 min para vídeo de 15 min (TTS + upload assets + disparo dos jobs). O tempo de renderização HeyGen é assíncrono (callback); SLA separado: timeout de alerta após 60 min de renderização sem callback, timeout de falha após 90 min. | feasibility R03 |
| NFR-03 | **Segurança** | API keys e OAuth tokens protegidos | 100% via Secret Manager, nunca em env vars | constraint-register CT-05 |
| NFR-04 | **Conformidade** | AI disclosure preenchido em uploads YouTube | 100% dos vídeos da pipeline | constraint-register CC-01 |
| NFR-05 | **Disponibilidade** | Pipeline processa ao menos 5 pacotes/semana do início ao fim sem intervenção manual de Victor (excetuando gates de aprovação deliberados) | 5 pacotes/semana completados com `status: "published"` sem que Victor precise clicar "Re-tentar" ou "Upload manual" | RQ3 |
| NFR-06 | **Testabilidade** | Cada Cloud Run Job testável isoladamente | Endpoint de invocação manual + 1 teste Nyquist por job | team-practices Testing Posture |
| NFR-07 | **Observabilidade** | Erros de todos os jobs visíveis no CSM Studio | 100% dos erros com mensagem human-readable no Firestore | FR-09.4 |
| NFR-08 | **Conformidade de API** | Somente Meta Graph API oficial para publicação Meta | Zero uso de browser automation / scrapers | discovered-rules |
| NFR-09 | **Idempotência** | Consumers Pub/Sub processam mensagem duplicada sem efeito duplicado | Reprocessar qualquer mensagem Pub/Sub produz o mesmo estado final | team-practices |
| NFR-10 | **Portabilidade de fornecedor** | TTS e Avatar encapsulados em interfaces abstratas | Trocar ElevenLabs ou HeyGen requer modificação em ≤ 2 arquivos | build-vs-buy |

---

## Constraints

| ID | Tipo | Constraint |
|---|---|---|
| C-01 | Tecnológico | LLMs obrigatoriamente do Google (Gemini 2.5 Flash via Vertex AI) |
| C-02 | Tecnológico | HeyGen API v3 exclusivamente (v2 descontinua out/2026) |
| C-03 | Tecnológico | CSS Modules para todos os novos componentes Next.js — sem Tailwind no CSM Studio |
| C-04 | Tecnológico | Firebase Admin SDK como única fonte de credenciais GCP no backend Next.js |
| C-05 | Tecnológico | Cloud Run Jobs (não Services) para TTS, Avatar, Video Editor, Publisher |
| C-06 | Negócio | Victor é o único aprovador; sistema não publica sem `approval_status: "approved"` |
| C-07 | Negócio | Teto de custo de R$100/pacote é um gate arquitetural, não apenas um alerta |
| C-08 | Regulatório | AI disclosure obrigatório e automático no YouTube |
| C-09 | Regulatório | Somente APIs oficiais para publicação em todas as plataformas sociais |
| C-10 | Deploy | Cloud Run Jobs da content pipeline deployados via `cloudbuild-pipeline.yaml` separado |

---

## Assumptions

| ID | Assumption | Risco se Falsa | Quando Validar |
|---|---|---|---|
| A-01 | HeyGen Lipsync API v3 (`POST /v3/lipsyncs`) aceita áudio externo via `asset_id` com lip-sync de qualidade aceitável. Critério de rejeição do spike: sincronização labial visualmente fora de sincronia em mais de 2 frames consecutivos em > 10% dos segmentos do vídeo de teste, avaliada por Victor assistindo o vídeo completo. | Pipeline de vídeo não funciona como arquitetada | Bolt 1 spike — Victor assiste o vídeo de teste e emite veredicto binário GO/NO-GO |
| A-02 | ElevenLabs Turbo v2.5 com Instant Voice Clone produce voz indistinguível da voz de Victor em mais de 70% das frases quando avaliada por Victor em teste cego. Critério de rejeição: se Victor identifica a voz como "claramente sintética" em mais de 3 de 10 frases de teste, upgrade para Creator Pro ($99/mês) é obrigatório. | Pode requerer plano Creator Pro ($99/mês) | Antes do Bolt 1 — Victor escuta 10 frases e emite veredicto |
| A-03 | Custo real HeyGen PAYG para vídeo de 15 min ≤ R$80 (deixando margem para outras etapas) | Teto R$100 insuficiente; requer replanejamento | Bolt 1 spike |
| A-04 | Playwright rodando em Alpine Linux num Cloud Run Job consegue renderizar slides HTML com animações CSS | Video Editor Job pode falhar em container headless | Bolt 2 spike |
| A-05 | YouTube OAuth com service account ou conta pessoal do Google é viável para upload automático | Publisher Service não consegue publicar no YouTube | Setup pré-Bolt 3 |
| A-06 | Meta Graph API permite publicação de Reels e posts de texto via token OAuth de longa duração | Precisa refresh manual periódico ou nova estratégia de autenticação | Setup pré-Bolt 3 |

---

## Fora do Escopo

| Item | Razão |
|---|---|
| Multi-tenancy / SaaS para outros criadores | Roadmap de longo prazo |
| Geração automática de thumbnails com IA | Requer modelo de geração de imagem separado |
| Integração com TikTok | Restrições severas na API; não solicitado |
| Análise de métricas de performance de canal | YouTube Analytics API — escopo separado |
| Automação de respostas a comentários | Risco de ban; fora do escopo |
| Fine-tuning de modelos próprios | Escopo de ML engineering |
| Stories do Instagram (schedlued) | TTL de 24h torna timing crítico; Bolt 5 opcional |

---

## Questões Abertas (para estágios seguintes)

| ID | Questão | Impacto | Responsável |
|---|---|---|---|
| OQ-01 | Custo real HeyGen Lipsync API PAYG — precisa de spike antes do Bolt 1 | Define viabilidade do teto R$100 | Victor (spike externo) |
| OQ-02 | ElevenLabs Instant vs. Professional Clone — qualidade pt-BR | Define plano ElevenLabs ($22 vs $99/mês) | Victor (spike externo) |
| OQ-03 | Painel de configuração: aba no CsmDashboard ou route dedicada `/pipeline` | Impacta routing Next.js e UX de navegação | Application Design |
| OQ-04 | Carrosseis e image posts: design template HTML renderizado por Playwright ou geração de imagem por Gemini Imagen | Impacta Bolt 5 — são formatos visuais diferentes do pipeline de vídeo | Application Design |
| OQ-05 | YouTube Community Posts API — endpoint e escopos OAuth disponíveis | Bolt 5 pode ser simplificado se API não disponível publicamente | Feasibility spike pré-Bolt 5 |
| OQ-06 | YouTube Data API v3 — confirmar se service account (ADC) funciona para upload em nome do canal de Victor, ou se OAuth de usuário é obrigatório | Define se FR-12 (fluxo alternativo OAuth) é necessário; bloqueia Publisher Service do YouTube | Victor: testar upload com 1 vídeo de teste antes do Bolt 3 |
| OQ-07 | Comportamento do Cloud Scheduler quando projeto mais antigo não pode ser publicado (throttler no limite de um canal): pular para próximo projeto, aguardar próximo slot, ou falhar? | Define lógica do Publisher Service para fila de publicação | Application Design |
| OQ-08 | FR-06.8 — quando o Cloud Scheduler dispara, a decisão de qual projeto publicar deve considerar os canais individualmente (ex: projeto A está pronto para LinkedIn mas não para YouTube porque throttler atingiu)? | Define complexidade da lógica de scheduling | Application Design |


---

## Review

**Reviewer:** aidlc-product-lead-agent
**Date:** 2025-07-26
**Verdict:** NOT-READY

---

### Findings

**1. Assumptions com linguagem não-mensurável (A-01, A-02) — bloqueante**

A-01 usa "qualidade adequada" e A-02 usa "qualidade aceitável" sem nenhum threshold. Estas assumptions protegem o coração do pipeline. Se forem falsas, a arquitetura inteira falha — mas você não definiu o que "falhar" significa. A-01 precisa: resolução mínima de lipsync aceitável (ex: erro de sincronização labial ≤ X frames), ou pelo menos o critério de rejeição manual. A-02 precisa: nota mínima de MOS (Mean Opinion Score) ou métrica subjetiva documentada que Victor usará para rejeitar o clone. Sem isso, não há critério de aceite para o spike do Bolt 1.

**2. NFR-02 não tem método de medição definido — bloqueante**

"≤ 90 min para vídeo de 15 min" cobre TTS + Avatar + Editor, mas o tempo de processamento do HeyGen Lipsync é assíncrono (callback). Falta especificar: o SLA de 90 min inclui o tempo de espera do callback HeyGen? Se sim, como o sistema detecta timeout? Se não, qual é o SLA separado para o job de lipsync? NFR-02 é não-verificável como está.

**3. FR-06.3 mistura dois canais com critérios de aceite distintos em um único requisito**

"Instagram Reel + YouTube Short" num único FR-06.3 cria ambiguidade de falha: se o upload para Instagram falha mas YouTube Short tem sucesso, qual é o status do projeto? O critério de aceite não define comportamento de falha parcial. Recomendo separar em FR-06.3a e FR-06.3b, cada um com critério de aceite independente.

**4. FR-08.6 — "próximos N agendamentos" sem definir N**

"Exibir a fila de próximos N agendamentos" usa N como variável sem valor default ou range. O critério de aceite diz "próximos 7 dias", o que contradiz o uso de N no requisito. Alinhe: ou é "próximos 7 dias" (fixo) ou "próximos N agendamentos" com N configurável e default definido.

**5. NFR-05 tem métrica não-verificável**

"0 timeout de jobs por falta de recursos" é uma métrica de causa raiz (recursos), não de SLO. Um job pode dar timeout por bug de rede, rate limit de API externa, ou lentidão do HeyGen — sem relação com recursos de Cloud Run. A métrica correta é: 5 pacotes/semana processados do início ao fim sem intervenção manual de Victor (excetuando gates de aprovação deliberados). Reescreva a métrica para ser observável e falsificável.

**6. Ausência de requisito de retry automático — gap crítico**

Nenhum FR cobre retry automático de falhas transitórias nos jobs Cloud Run (ex: rate limit do ElevenLabs, timeout temporário do HeyGen). FR-09 trata de retry manual por Victor. Mas um sistema classificado como "autônomo" que exige intervenção manual em toda falha transitória falha na promessa core do produto. Precisa de pelo menos um requisito explícito: "O sistema deve re-tentar automaticamente até X vezes com backoff exponencial em falhas transitórias antes de mover para estado de erro." Se retry automático está fora do escopo desta entrega, isso precisa estar documentado em "Fora do Escopo" com justificativa.

**7. FR-06.8 — comportamento não definido quando múltiplos projetos estão em `awaiting_publication`**

O scheduler "seleciona o projeto mais antigo aprovado". Mas e se o mais antigo foi aprovado para um canal que está com throttler no limite? O critério de aceite não define: (a) se pula para o próximo projeto, (b) se aguarda o próximo slot do canal, ou (c) se falha o job com erro. Isso é um edge case de produto real que o Publisher Service vai encontrar na primeira semana de uso.

**8. Assumption A-05 oculta um requisito crítico ausente**

A-05 documenta a incerteza sobre YouTube OAuth com service account. Se esta assumption for falsa (e há boa razão para suspeitar — YouTube Data API v3 geralmente exige OAuth de usuário real para uploads em nome de um canal), o Publisher Service do YouTube não é implementável como arquitetado. Isso deveria ser uma Questão Aberta com spike obrigatório pré-Bolt 3 (está em OQ-06, mas OQ-05 e OQ-06 conflacionam coisas distintas). Mais importante: se a resposta for "service account não funciona", existe algum requisito para o fluxo alternativo de autenticação? Não há. Isso é um requisito condicional ausente.

**9. Pontos fortes reconhecidos (para registro)**

- Cobertura funcional dos 5 Bolts é genuinamente abrangente: 10 domínios FR com critérios de aceite em tabela é o padrão correto.
- NFR-09 (idempotência Pub/Sub) e NFR-10 (portabilidade de fornecedor) mostram maturidade arquitetural — não são óbvios e estão bem definidos.
- FR-02.2 e C-07 são exemplares: o teto de custo R$100 como gate arquitetural, não apenas alerta, é exatamente o nível de precisão que torna um requisito testável.
- A seção "Fora do Escopo" é bem delimitada e protege o escopo do Bolt 5.
- C-01 a C-10 são todos rastreáveis a fontes upstream (constraint-register, discovered-rules).

---

**Para READY:** Resolver itens 1, 2, 3, 5, 6, 8 antes de avançar para User Stories. Itens 4 e 7 podem ser resolvidos em Application Design se houver registro de decisão explícito nas Questões Abertas.

---

## Review (Iteração 2)

**Reviewer:** aidlc-product-lead-agent
**Date:** 2025-07-26
**Verdict:** READY

---

### Findings Resolvidos

| # | Finding (Iteração 1) | Status | Evidência no documento |
|---|---|---|---|
| F1 | A-01 e A-02 sem critério de rejeição mensurável | **RESOLVIDO** | A-01: threshold de "2 frames consecutivos em > 10% dos segmentos"; A-02: "mais de 3 de 10 frases de teste" com consequência ($99/mês) documentada |
| F2 | NFR-02 sem SLA separado para callback HeyGen | **RESOLVIDO** | NFR-02 define ≤ 30 min para TTS+upload+disparo; SLA assíncrono HeyGen: alerta em 60 min, falha em 90 min |
| F3 | FR-06.3 misturando dois canais num único critério | **RESOLVIDO** | FR-06.3a (Instagram Reel) e FR-06.3b (YouTube Short) com critérios independentes e isolamento de falha explícito em cada um |
| F4 | FR-08.6 "N agendamentos" sem valor definido | **RESOLVIDO** | FR-08.6 agora especifica "próximos 7 dias" fixos; critério de aceite confirma "exatamente 7 dias" |
| F5 | NFR-05 com métrica de causa raiz não-observável | **RESOLVIDO** | NFR-05 reescrito como "5 pacotes/semana com `status: published` sem clicar Re-tentar ou Upload manual" — observável via Firestore |
| F6 | Ausência de requisito de retry automático | **RESOLVIDO** | FR-11 adicionado com 3 sub-requisitos: retry transitório com backoff (1s/4s/16s), exclusão de erros permanentes de retry, visibilidade no side panel |
| F7 | FR-06.8 sem comportamento definido para throttler + fila | **RESOLVIDO** | OQ-07 e OQ-08 adicionados explicitamente, delegando decisão ao Application Design com contexto de impacto documentado |
| F8 | Requisito condicional de YouTube OAuth ausente | **RESOLVIDO** | FR-12 adicionado com FR-12.1 (OAuth 2.0 + refresh token, condicional a A-05) e FR-12.2 (alerta de expiração); OQ-06 alinhado |

---

### Observações Finais

**Para User Stories:** todos os requisitos funcionais estão com critérios de aceite testáveis e rastreáveis. FR-11 e FR-12 são novos domínios que precisam de user stories próprias — FR-11 como critério técnico transversal e FR-12 como fluxo de configuração do canal YouTube no painel. FR-10 (CostTrackerService) está tecnicamente completo mas perdeu o cabeçalho de seção `### FR-10` no documento — defeito cosmético sem impacto funcional, corrigir na próxima edição.

**Para Application Design:** OQ-03 (roteamento do painel Pipeline), OQ-07 e OQ-08 (lógica do scheduler com throttler) são as três questões abertas com maior impacto arquitetural. Recomendo que Application Design as resolva antes de definir os contratos de serviço do Publisher Service e do Cloud Scheduler. OQ-06 (YouTube service account vs. OAuth) bloqueia a implementação do FR-12 — se confirmado que service account não funciona, FR-12 passa de condicional a Must, o que pode impactar o Bolt 3.

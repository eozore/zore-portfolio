# Intent Capture — Perguntas de Alinhamento
## Pipeline Autônoma de Conteúdo Omnicanal éozoré
**Escopo:** enterprise | **Profundidade:** Comprehensive

---

### Q1. Problema central a resolver

O fluxo atual é: você conversa com o Claude, ele gera um arquivo HTML de pacote de conteúdo, você grava voz manualmente, envia ao HeyGen, monta o vídeo, edita manualmente, publica. Qual é o gargalo **mais doloroso** que precisa ser eliminado primeiro?

A. A gravação manual de voz para cada segmento do roteiro (é o passo que mais consome tempo e bloqueia tudo downstream)
B. A edição manual de vídeo (cortar silêncios, identificar timing dos slides) após receber o avatar do HeyGen
C. A falta de derivação automática para redes sociais (vertical/Reels/LinkedIn/Threads) — o conteúdo do YouTube não vira conteúdo social sozinho
D. A ausência de uma conversação estruturada com um agente CMO — hoje você vai até o Claude sem um fluxo guiado de cocriação
E. A publicação manual — copiar descrição, gerar thumbnail, publicar no YouTube e nas redes um a um

[Answer]: C — A ausência de derivação automática para redes sociais é o maior gargalo. O conteúdo do YouTube existe mas não vira conteúdo social porque não há tempo para o processo manual de adaptação.

---

### Q2. Modo de acionamento preferido

Você descreveu querer "conversar com o agente CMO" diariamente. Como você imagina acionar essa conversa?

A. Direto pelo CSM Studio no browser (a interface já existe em `apps/web`) — sem precisar de nova interface
B. Via um chat no WhatsApp ou Telegram integrado ao agente (acesso mobile, qualquer hora)
C. Via CLI / terminal no computador de desenvolvimento
D. Via um painel dedicado com agendamento automático — o próprio agente inicia a conversa quando detecta que não houve conteúdo novo no dia
E. Via API chamada por n8n/Make ou outro orquestrador externo que Victor controla

[Answer]: A — CSM Studio no browser. A interface já existe e é o ponto central de trabalho.

---

### Q3. Gravação de voz — direção estratégica

A voz é o ponto mais crítico da pipeline. Hoje é 100% manual. Qual direção você quer tomar?

A. **Manter voz humana** — gravar a própria voz em sessões batch (gravar 5-7 segmentos de uma vez em vez de um por um), com um fluxo guiado que mostra o roteiro e facilita a gravação
B. **Voz sintética imediata via ElevenLabs/Google TTS** — gerar áudio automaticamente com uma voz clonada do Victor, sem gravação humana alguma
C. **Híbrido com aprovação** — o agente gera voz sintética por padrão, mas Victor pode sobrescrever qualquer segmento com sua própria voz antes de enviar ao HeyGen
D. **HeyGen faz tudo** — usar o HeyGen com a opção de voz do avatar, sem áudio externo; o avatar fala o roteiro diretamente
E. Outra abordagem

[Answer]: B modificado — ElevenLabs API gera o áudio com voz clonada do Victor. Esse áudio é então combinado com o vídeo do avatar via HeyGen API. Princípio orientador: buscar a máxima naturalidade possível; custo é considerado mas tem peso menor que qualidade.

---

### Q4. Grau de autonomia esperado por etapa

Para cada etapa abaixo, qual é o grau de controle que você quer manter? (selecione o modelo que melhor descreve sua preferência geral)

A. **Totalmente autônomo** — o agente executa tudo, você só revisa o resultado final antes de publicar (ou publica automaticamente com base em aprovação prévia do pacote)
B. **Checkpoint na cocriação** — você conversa com o CMO, aprova o pacote de conteúdo, depois tudo roda automaticamente (HeyGen, edição, publicação)
C. **Checkpoint em cada formato** — aprova artigo, aprova roteiro YT, aprova derivações sociais separadamente antes de cada etapa executar
D. **Aprovação antes de qualquer publicação** — o agente gera tudo, você revisa num painel, aprova e clica "publicar"
E. **Autonomia total com rollback** — publica automaticamente, mas você pode reverter/esconder qualquer peça a qualquer momento pelo painel

[Answer]: D — Aprovação obrigatória antes de qualquer publicação. Os dados de aprovação (quem aprovou, quando, qual versão) devem ser armazenados no Firestore para rastreabilidade.

---

### Q5. Canais e formatos prioritários

Quais canais e formatos são OBRIGATÓRIOS no MVP da pipeline autônoma? (selecione todos que se aplicam)

A. YouTube horizontal (vídeo longo, 10-20 min, com slides + avatar HeyGen)
B. YouTube Shorts / Reels verticais (30-90 seg, com slides verticais + avatar)
C. Artigo de blog no portfolio eozore.com (já funciona via CSM Studio)
D. LinkedIn (posts escritos derivados do artigo/vídeo)
E. Instagram Reels (vídeo vertical diferente do Shorts, ou o mesmo)
F. Threads (texto longo, fragmentos do artigo)
G. Comunidade do YouTube (posts de texto/imagem para membros)
H. Carrosséis para Instagram/LinkedIn (slides estáticos com design)
I. Posts de imagem única com copy (feed Instagram/LinkedIn)

[Answer]: A+B+C+D+E+F+G+H+I — Todos os formatos. Instagram Reels e YouTube Shorts usam o mesmo arquivo de vídeo vertical. Requisito adicional crítico: painel de controle para ligar/desligar cada canal individualmente, configurar API keys com segurança, definir horários de publicação por rede e outros parâmetros operacionais por canal.

---

### Q6. Integração com o pacote HTML existente

A ferramenta `tool-videoyoutube` já tem um sistema completo de pipeline de vídeo (STT → alinhamento via Gemini → composição FFmpeg → corte de silêncios). O manifesto v2 (`manifesto.md`) define um schema JSON que alimenta a produção. Como você quer integrar isso na nova pipeline autônoma?

A. **Manter e evoluir o pacote HTML** — o CMO Agent continua gerando o arquivo HTML com o manifesto JSON embutido, e a `tool-videoyoutube` o consome para produzir vídeos (é o contrato de dados já especificado)
B. **Abandonar o HTML como formato intermediário** — o agente gera o manifesto JSON diretamente sem o wrapper HTML; as ferramentas de vídeo consomem o JSON puro
C. **Usar o pacote HTML apenas para o vídeo principal do YouTube** — para Reels/Shorts usar um fluxo mais simples sem slides HTML
D. **Separar completamente** — pipeline de blog/texto independente do pipeline de vídeo; cada um roda de forma assíncrona
E. Outra visão de integração

[Answer]: A com adaptação crítica — manter o pacote HTML como contrato de dados com manifesto JSON embutido. O mapeamento segmento→slide já está no manifesto (campo `slide` por segmento), eliminando completamente a necessidade do Gemini para alignment. O editor de vídeo recebe: (1) o vídeo do avatar gerado pelo HeyGen com o áudio do ElevenLabs já sincronizado, e (2) o manifesto com as posições exatas de cada ilustração. O editor apenas sobrepõe as ilustrações nos momentos definidos pelo contrato — sem inferência.

---

### Q7. Frequência e gatilho de publicação

"Quero que diariamente os conteúdos sejam gerados automaticamente" — como você imagina que isso funciona na prática?

A. **Agenda fixa** — todo dia às X horas o sistema verifica se há conteúdo novo aprovado e publica; se não houver, não faz nada
B. **Batch semanal** — você faz uma sessão CMO por semana, gera 5-7 pacotes de conteúdo, e o sistema distribui um por dia automaticamente
C. **Event-driven** — quando você aprovа um pacote no CSM Studio, um Cloud Run job ou Cloud Scheduler dispara a pipeline completa de geração e publicação
D. **Manual disparado** — você clica "gerar e publicar" no CSM Studio; o sistema é autônomo na execução mas requer seu acionamento inicial
E. **Totalmente automático** — agente roda em background, detecta tendências, sugere pauta e executa sem que você precise acionar nada

[Answer]: B — Batch semanal. Uma sessão CMO por semana gera múltiplos pacotes de conteúdo. O sistema distribui automaticamente conforme agenda configurada no painel. Cada pacote de conteúdo é um "projeto" com visibilidade kanban no CSM Studio.

---

### Q8. Autenticação e publicação nas redes sociais

Você mencionou que LinkedIn, Instagram e Threads já estão configurados. Qual é o estado atual das integrações?

A. OAuth tokens ativos e salvos no Firestore/Secret Manager — pronto para chamar as APIs de publicação automaticamente
B. Tokens configurados localmente (`.env`) mas não no ambiente cloud — precisam ser migrados para produção
C. Tenho as credenciais de desenvolvedor (App ID, secrets) mas ainda não fiz o fluxo OAuth — precisa ser implementado
D. Apenas as contas existem — nenhuma integração técnica configurada ainda; precisa ser feito do zero
E. Parte está configurada (especifique em X quais redes estão prontas vs. quais precisam de trabalho)

[Answer]: E — Instagram, Threads, Facebook e LinkedIn já operacionais (publicação funcionando). YouTube via GCP é simples dado que o projeto já está no GCP (YouTube Data API v3 com service account ou OAuth). Premissa do painel: usuário configura os apps das mídias sociais externamente e passa apenas as keys/tokens pelo painel de configuração. Segurança via GCP Secret Manager obrigatória.

---

### Q9. Infraestrutura e onde a pipeline roda

A arquitetura atual usa Cloud Run para o `cmo_agent` Python e Next.js para o frontend. Onde você quer que a pipeline autônoma de vídeo+publicação rode?

A. **Tudo no Cloud Run existente** — expandir o microserviço `cmo_agent` para incluir as etapas de vídeo e publicação (uma única API Python que faz tudo)
B. **Cloud Run Job separado** — um job dedicado para a pipeline de vídeo/publicação, disparado via Cloud Scheduler ou Pub/Sub, separado do `cmo_agent` que é interativo
C. **Máquina local (Mac do Victor)** — durante o desenvolvimento e uso pessoal, rodar localmente com uma ferramenta CLI; só vai para cloud quando virar produto
D. **Cloud Run + Workflows (GCP)** — usar o GCP Workflows para orquestrar as etapas da pipeline como um DAG, com cada step num Cloud Run separado
E. **Vertex AI Agent Engine** — usar o Agente do Vertex AI para orquestração; é o target arquitetural de longo prazo do roadmap

[Answer]: Arquitetura de microserviços com Pub/Sub como barramento de comunicação — como um escritório onde especialistas trocam contratos/arquivos entre si. Cada etapa da pipeline é um microserviço independente (Cloud Run). Cada "pacote de conteúdo" é um projeto com visibilidade kanban no CSM Studio. O painel mostra o estado de cada projeto (em cocriação → aguardando aprovação → gerando mídia → publicando → publicado).

---

### Q10. Definição de sucesso e métricas

Como você vai saber que a pipeline autônoma funcionou? Quais métricas definem sucesso nos primeiros 3 meses?

A. **Velocidade de produção** — conseguir publicar 1 vídeo/semana no YouTube + derivações diárias nas redes sem gastar mais de 1h/dia do Victor
B. **Consistência** — nunca ficar mais de 3 dias sem postar em nenhuma rede social (o maior problema hoje é o silêncio quando Victor não tem tempo)
C. **Qualidade técnica** — os vídeos gerados automaticamente têm qualidade comparable aos feitos manualmente (sem cortes ruins, sincronização ok, avatar natural)
D. **Crescimento de canal** — aumento mensurável em inscritos no YouTube e seguidores nas redes em 90 dias
E. **ROI de tempo** — o tempo total gasto por Victor em produção de conteúdo cai para menos de 25% do tempo atual

[Answer]: A+B — Velocidade (1 vídeo/semana + derivações diárias com máximo 1h/dia de Victor) e Consistência (zero silêncios prolongados nas redes).

---

### Q11. Riscos e constraints críticos

Quais são as maiores preocupações ou limitações que devem ser consideradas no planejamento?

A. **Custo de API** — HeyGen cobra por vídeo gerado; ElevenLabs cobra por caracteres; Gemini tem custos de inferência; precisa de um orçamento/teto definido
B. **Qualidade do avatar HeyGen** — o avatar não tem expressão variada; vídeos longos ficam repetitivos; isso limita o formato
C. **Políticas de plataforma** — YouTube e Instagram têm regras contra conteúdo 100% gerado por IA; precisa de um nível de curadoria humana para não ser penalizado
D. **Coerência de voz** — o tom técnico e rigoroso de Victor é difícil de replicar automaticamente; conteúdo genérico vai frustrar a audiência
E. **Manutenção e debt técnico** — a pipeline vai ficar complexa; quem mantém quando quebra? precisa ser simples o suficiente para Victor operar sozinho

[Answer]: A+C+E — Teto de R$100 por vídeo completo com mapeamento de custos por etapa (ElevenLabs + HeyGen + Gemini + infra GCP). Operabilidade manual de fallback obrigatória caso automações falhem. Conformidade com políticas das plataformas é crítica — nenhum ban é aceitável.

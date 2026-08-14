# Requirements — tool-videoyoutube Refactor

## Intent Analysis

O objetivo é transformar a ferramenta `tool-videoyoutube` de um protótipo frágil (com dependências faltando, lógica duplicada, e paths hardcoded) em uma **API de produção** que recebe um vídeo MP4 de uma pessoa falando + um deck HTML com ilustrações animadas e produz dois vídeos editados automaticamente (horizontal e vertical).

O conceito central: **alternância entre avatar falando e ilustrações contextuais** — os slides cobrem totalmente o avatar quando ativos, criando um vídeo dinâmico para YouTube.

## Functional Requirements

### FR-01: API REST de Edição de Vídeo
- Endpoint que recebe: 1 arquivo MP4 (avatar falando, até 2h) + 1 arquivo HTML (deck de slides animados)
- Retorna: 2 vídeos — horizontal (16:9) e vertical (9:16)
- Streaming de progresso durante o processamento

### FR-02: Transcrição com Timestamps (Speech-to-Text)
- Extrair áudio do MP4
- Transcrever com timestamps por palavra (word-level)
- Suporte a pt-BR (prioridade) + outros idiomas (futuro)
- Preferência GCP Speech-to-Text (manter)

### FR-03: Extração de Slides do HTML
- Ler o deck HTML e identificar os slides (`section.slide`)
- Renderizar cada slide como clipe de vídeo (animações preservadas)
- Usar Playwright para captura de tela/vídeo

### FR-04: Alinhamento Inteligente (Visão × Fala)
- Usar LLM (Gemini 2.5 Flash preferencialmente) para alinhar slides à transcrição
- Input: transcrição com timestamps + descrição semântica dos slides
- Output: lista de timings `{slide_index, start_time, end_time}`
- Regras de pacing: mínimo 3s por slide, sem sobreposição, respeitar limites semânticos

### FR-05: Composição de Vídeo (FFmpeg)
- Overlay dos slides sobre o vídeo do avatar
- Slide cobre totalmente o avatar quando ativo (fullscreen overlay)
- Transições limpas nos limites semânticos da fala
- Output horizontal: 1920×1080
- Output vertical: 1080×1920 (crop/resize adequado)

### FR-06: Jump Cuts (Remoção de Silêncios)
- Detectar silêncios longos na transcrição
- Remover silêncios com cortes limpos (padding para naturalidade)
- Aplicar nos dois outputs (horizontal e vertical)

### FR-07: Armazenamento do Resultado
- Salvar vídeos processados no Google Cloud Storage
- Gerar URLs de download temporárias
- Cleanup automático após expiração

## Non-Functional Requirements

### NFR-01: Confiabilidade
- Pipeline não deve crashar por dependência faltando — `requirements.txt` completo e versionado
- Fallbacks para cada etapa (se jump cuts falham, entregar vídeo sem cortes)
- Logging estruturado em cada etapa

### NFR-02: Performance
- Suportar vídeos de até 2 horas
- Processamento não deve exceder 3x a duração do vídeo (ex: vídeo de 1h → máx 3h de processamento)
- Heartbeat para evitar timeout do cliente

### NFR-03: Modularidade
- Cada etapa do pipeline como módulo independente (STT, slide_export, alignment, compose, jump_cuts)
- Possibilidade de trocar qualquer módulo sem afetar os outros
- Interface clara entre módulos (inputs/outputs tipados)

### NFR-04: Manutenibilidade
- Eliminar código duplicado (remover `editor_pipeline.py` legacy)
- Remover arquivos de teste hardcoded (`RAG2.mp4`, `RAG.html`, etc.)
- Estrutura de pastas clara e documentada

### NFR-05: Plataforma
- Priorizar serviços GCP (STT, Gemini, GCS, Cloud Run)
- Docker-ready para deploy em Cloud Run
- Configuração via variáveis de ambiente (sem hardcoded project IDs)

## Constraints

- **Infraestrutura**: GCP como cloud provider principal (projeto `ainewz-project`)
- **Budget**: STT e Gemini têm custo por uso — pipeline deve minimizar chamadas desnecessárias (cache de transcrição)
- **Dependência**: FFmpeg e Playwright precisam estar no container Docker
- **Tamanho**: Vídeos de até 2h geram arquivos grandes — pipeline precisa de storage adequado

## Assumptions

- O HTML de entrada segue o padrão de deck de slides do éozoré (sections com classe `.slide`, animações CSS)
- O vídeo MP4 de entrada contém áudio em português (pt-BR) como idioma principal
- O GCP project já está configurado com as APIs necessárias habilitadas
- FFmpeg, Playwright e Python 3.10+ estão disponíveis no ambiente de execução

## Out of Scope

- `tool-cromex` (não faz parte deste refactor)
- Interface frontend (será conectada via API — frontend é outro workstream)
- Edição manual/interativa de vídeo (tudo é automático)
- Suporte a formatos além de MP4 + HTML
- Legendas/captions automáticas no vídeo final

## Decisions (Resolved)

### Vídeo Vertical (9:16)
- Layout: slide cobre totalmente o avatar (fullscreen), mesma lógica do horizontal
- **CRÍTICO**: O HTML do vertical é gerado AUTOMATICAMENTE pelo sistema a partir do HTML horizontal
- O sistema recebe apenas 1 HTML (horizontal) e adapta/re-renderiza para 9:16
- São dois pipelines paralelos: um renderiza em 1920×1080 (horizontal), outro adapta e renderiza em 1080×1920 (vertical)

### Upload
- Maioria dos vídeos < 20 minutos — upload direto é viável
- Solução mais robusta a critério da implementação (GCS signed URL recomendado para > 100MB)

### Processamento
- **Assíncrono com WebSocket** para progresso em tempo real
- Cada vídeo é tratado como um **projeto com memória** (estado persistido, pode ser re-executado, consultado, etc.)
- Job ID + websocket channel para o frontend acompanhar

## Open Questions

_(Todas resolvidas — nenhuma pendente.)_

# CMO Final — Planejamento de Evolução

## Objetivo

Evoluir a plataforma CSM para que, a partir de uma conversa com o CMO AI, o sistema entregue um **pacote de conteúdo completo** (como o `pacote-finetuning-v2.html`) com todos os artefatos prontos para revisão, aprovação e publicação automatizada — sem intervenção manual em nenhuma etapa de criação.

---

## O que é o pacote final (modelo de referência: `pacote-finetuning-v2.html`)

Um pacote de conteúdo é composto por:

| Artefato | Quem escreve | Formato |
|---|---|---|
| **Manifesto JSON** (fonte única) | Pipeline interno | JSON com segmentos, âncoras, metadados |
| **Roteiro YouTube segmentado** | Agente Roteirista | Texto falado por segmento + âncoras de animação |
| **Título + Thumbnail (2 opções)** | Agente de Título/Design | Texto + HTML dark premium |
| **Descrição YouTube** (com capítulos) | Agente Roteirista | Markdown com timestamps |
| **Slides YouTube (deck 16:9)** | Agente de Design | HTML+SVG animado (Playwright-ready) |
| **Roteiro Reel/Short (2-3 versões)** | Agente de Shorts | Script fonético + slides 9:16 |
| **Copy dos Reels (post)** | Agente de Copy | Texto + hashtags |
| **Mini-decks Reels (9:16)** | Agente de Design | HTML+SVG (3 slides por reel) |
| **Posts LinkedIn (2-3 ângulos)** | Agente de Copy LinkedIn | Texto editorial |
| **Posts Threads (2-3 threads)** | Agente de Copy Threads | Série encadeada |
| **Imagens dos posts** | Gerador de Imagem (Playwright) | PNG via HTML |

---

## O que existe hoje vs. o que falta

### Existente (funcional)

| Componente | Status |
|---|---|
| Chat CMO → define tema/tese | ✅ |
| Geração de artigo de blog (Critic → Research → Writing) | ✅ |
| Publicação do artigo no Firestore | ✅ |
| Geração do roteiro YouTube (texto Markdown com cenas) | ✅ |
| Derivação omnicanal (LinkedIn, Threads, Shorts, Reels, Stories) | ✅ |
| Publisher (LinkedIn, Instagram, Facebook, Threads, YouTube) | ✅ testado |
| Pipeline de vídeo (TTS → Avatar → Editor) | ✅ deployado |
| Thumbnails (Playwright) | ✅ testado |
| Manifesto builder (roteiro → manifesto HTML) | ✅ funcional |

### Gaps entre o estado atual e o pacote v2

| Gap | Descrição | Impacto |
|---|---|---|
| **G1 — Agentes especialistas separados** | Hoje um único `writing_agent` faz tudo. O pacote v2 exige que cada artefato seja escrito pelo especialista correto (roteirista ≠ copywriter ≠ designer) | Qualidade e tom por formato |
| **G2 — Slides SVG animados** | O `manifest_builder.py` gera slides HTML básicos. O pacote v2 usa SVGs complexos com animações CSS + âncoras por frase | Qualidade visual do vídeo |
| **G3 — Âncoras de animação** | O roteiro do pacote v2 tem `anchors[]` por segmento que sincronizam fala ↔ animação. O sistema atual ignora isso | Sincronização visual |
| **G4 — Pacote visual unificado** | O usuário deveria ver TUDO (roteiro + slides + copies + thumbnails) numa interface de preview antes de aprovar | UX de aprovação |
| **G5 — Pipeline "tema → pacote" sem etapas manuais** | Hoje o fluxo tem 5 abas manuais. O ideal: conversa → aprovação de conceito → geração automática de tudo → revisão final → publicação | Eficiência |
| **G6 — Lifecycle de mídia (60 dias)** | Após 60 dias publicado, conteúdos devem ser compactados e movidos para cold storage (ou deletados do bucket quente) | Custo de armazenamento |
| **G7 — Título da pauta ≠ última frase do chat** | Hoje o `topic` vira a última mensagem do usuário. Deveria ser o título proposto pelo CMO e aprovado explicitamente | Qualidade do título |

---

## Plano de execução (AIDLC scope: feature)

### Fase 1 — Arquitetura de Agentes Especialistas

**Objetivo:** Separar a geração em agentes especializados que produzem artefatos distintos.

| Agente | Input | Output |
|---|---|---|
| `cmo_agent` (existente) | Conversa com CEO | Pauta aprovada: título, tese, público, formato, duração alvo |
| `scriptwriter_agent` (novo) | Pauta aprovada | Roteiro segmentado com âncoras (JSON do manifesto v2) |
| `slide_designer_agent` (novo) | Roteiro segmentado | Deck HTML+SVG animado (16:9 + 9:16) |
| `copy_agent` (existente, refatorar) | Roteiro + artigo | LinkedIn posts, Threads, copys de Reels, descrição YouTube |
| `thumbnail_agent` (refatorar) | Título + frame do vídeo | 2 opções de thumbnail (Playwright HTML) |
| `shorts_agent` (novo) | Roteiro longo | 2-3 roteiros de Shorts/Reels com mini-decks próprios |

**Entregável:** Sistema multi-agente onde cada agente recebe input estruturado e devolve artefato no formato final.

### Fase 2 — Manifesto v2 com Âncoras

**Objetivo:** Gerar manifestos no formato exato do `pacote-finetuning-v2.html`.

- [ ] Atualizar `manifest_builder.py` para incluir campo `anchors[]` por segmento
- [ ] Cada âncora mapeia `on_phrase` → `action` (show_slide, reveal, highlight)
- [ ] O `scriptwriter_agent` deve gerar as âncoras junto com o texto (são parte do roteiro)
- [ ] O `video_editor_job` deve consumir âncoras para disparar transições de slide no timing correto

### Fase 3 — Slide Designer (decks SVG animados)

**Objetivo:** Gerar decks HTML+SVG+CSS no padrão visual da série éozoré.

- [ ] Criar `slide_designer_agent` que recebe os conceitos do roteiro e gera SVGs inline
- [ ] Design system: paleta `#0d0f14/#e8873a/#5fce8a`, font Space Grotesk + JetBrains Mono
- [ ] Animações CSS: `.draw` (stroke-dasharray), `.fadein`, `.pulse`, `.bar`
- [ ] Cada deck é self-contained: funciona offline, Playwright renderiza direto
- [ ] Dois modos: 16:9 (YouTube) e 9:16 (Reels) com layout adaptado

### Fase 4 — Interface de Pacote (preview unificado)

**Objetivo:** O usuário vê o pacote inteiro numa tela antes de aprovar.

- [ ] Nova aba "Pacote" no CSM (substitui as abas separadas YouTube/Derivações)
- [ ] Layout com tabs: YouTube | Reels/Shorts | LinkedIn | Slides (igual ao pacote v2)
- [ ] Preview dos decks embutido (iframe com srcdoc)
- [ ] Botão "Copiar roteiro" / "Copiar copy" por bloco
- [ ] Preview de thumbnail lado a lado (2 opções)
- [ ] Botão "Aprovar Pacote" → dispara pipeline completo

### Fase 5 — Fluxo Simplificado (conversa → pacote → publicação)

**Objetivo:** Reduzir de 5 abas manuais para 2 interações: conversar + aprovar.

```
Aba 1: Conversa CMO (define tema, tese, público, formato)
         ↓ CMO emite "PAUTA CONCEBIDA"
         ↓ Sistema gera pacote automaticamente (30-60s)
         ↓
Aba 2: Preview do Pacote Completo
         ↓ Usuário revisa, edita copys, aprova/rejeita peças
         ↓ Clica "Publicar Pacote"
         ↓
         LinkedIn/Threads → publicados imediatamente
         YouTube/Reels → pipeline TTS → Avatar → Editor → Upload
         Blog → publicado automaticamente
```

- [ ] Após "PAUTA CONCEBIDA", o sistema chama todos os agentes em paralelo
- [ ] Resultado: JSON do pacote completo (manifesto + copies + decks + thumbnails)
- [ ] Frontend renderiza preview do pacote (formato igual ao HTML v2)
- [ ] "Aprovar" dispara tudo de uma vez

### Fase 6 — Lifecycle de Mídia (60 dias)

**Objetivo:** Após 60 dias, conteúdos publicados são compactados e movidos para cold storage.

- [ ] Cloud Scheduler job diário: verifica `content_projects` com `published_at > 60 dias`
- [ ] Para cada projeto expirado:
  - Compacta todos os assets (vídeos, áudios, thumbnails) em `.tar.gz`
  - Move para bucket `vazfy-417019-pipeline-archive` (Nearline ou Coldline)
  - Remove do bucket quente `vazfy-417019-pipeline-media`
  - Atualiza status no Firestore: `archived`
- [ ] Assets da social_queue (imagens de posts) seguem a mesma regra
- [ ] Dashboard no CSM: seção "Arquivo" com listagem de pacotes archivados + botão "Restaurar"

### Fase 7 — Correção do Título (G7)

**Objetivo:** O título do pacote vem do CMO (proposta estruturada), não da última frase do chat.

- [ ] O CMO Agent, ao emitir "PAUTA CONCEBIDA", deve incluir no response um bloco estruturado:
  ```json
  {
    "pauta": {
      "titulo": "Fine-Tuning de LLMs: As 5 Técnicas",
      "subtitulo": "de 70 Bilhões a 13 Parâmetros",
      "tese": "B — Engenharia/GCP",
      "publico": "líderes e técnicos em IA/ML",
      "duracao_alvo": "5 min",
      "serie": "rag-para-lideres"
    }
  }
  ```
- [ ] O frontend extrai esse JSON do response do CMO e usa como input para a geração do pacote
- [ ] O `topic` do draft passa a ser o `titulo` aprovado pelo CMO — não a última frase do CEO

---

## Prioridade de execução (sprints)

| Sprint | Fases | Resultado |
|---|---|---|
| **Sprint 1** | G7 (título) + G5 parcial (conversa → geração automática) | Conversa gera pacote básico automaticamente |
| **Sprint 2** | G1 (agentes especialistas) + G2 (slides SVG) | Qualidade do pacote = nível do v2 |
| **Sprint 3** | G3 (âncoras) + G4 (interface de pacote) | Preview unificado antes de aprovar |
| **Sprint 4** | G5 completo + G6 (lifecycle) | Fluxo 2-interações + economia de storage |

---

## Restrições técnicas

- Modelos LLM: Google (Gemini 2.5 Flash para agentes, Vertex AI)
- Sem dependências novas de IA de imagem para slides (HTML+SVG+Playwright)
- Pipeline de vídeo: mantém ElevenLabs + HeyGen + FFmpeg
- Frontend: Next.js (mantém stack existente, sem migração)
- Deploy: GCP Cloud Run + Pub/Sub (mantém infra existente)

---

## Métricas de sucesso

1. **Tempo conversa → pacote pronto:** < 2 minutos (hoje ~10 min com interações manuais)
2. **Qualidade visual dos slides:** equivalente ao pacote v2 (SVG animado, não HTML estático)
3. **Publicação automática pós-aprovação:** 100% das plataformas sem intervenção
4. **Custo por pacote (TTS + HeyGen + infra):** < $0.50 por vídeo de 5 min
5. **Lifecycle:** zero assets > 60 dias no bucket quente

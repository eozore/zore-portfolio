# Market Research — Registro de Decisões
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> Este estágio foi conduzido via pesquisa direta (web search) a partir do intent-statement aprovado.
> As decisões foram derivadas da análise de mercado e confirmadas pelos dados coletados.

---

### D1. Soluções concorrentes existentes

Existem plataformas all-in-one (Opus Clip, Jasper, Synthesia) que tentam resolver partes do problema. Nenhuma cobre o caso específico do éozoré: geração de conteúdo técnico com rigor matemático + pipeline de vídeo com avatar + distribuição omnicanal.

[Answer]: Não há concorrente direto que resolva o problema completo. A decisão de construir um sistema proprietário é justificada.

---

### D2. Modelo de custo viável dentro do teto de R$100/vídeo

Baseado nos preços de julho/2026: ElevenLabs Turbo v2.5 (~$0.75) + HeyGen (~$10.80 para horizontal+vertical) + Gemini ($0.15) + GCP infra (~$0.50) = ~$12.20 total ≈ R$67. Dentro do teto com margem de 33%.

[Answer]: Custo estimado R$67/pacote completo. Teto de R$100 é atingível. Confirmar preços reais do HeyGen no feasibility.

---

### D3. Decisão build vs. buy por componente

Ver `build-vs-buy.md` para análise completa. Resumo: BUILD para orquestração/edição/publicação/painel; PARTNER para TTS (ElevenLabs) e avatar (HeyGen).

[Answer]: Decisões tomadas e documentadas em build-vs-buy.md.

---

### D4. Compliance com políticas de plataformas

YouTube exige disclosure de IA desde 2024 e aplica label automaticamente desde maio/2026. Risco de suspensão do canal se não divulgar. Instagram/Meta: publicação via Graph API oficial é segura (~0% ban risk). Nunca usar bots/scrapers.

[Answer]: Disclosure de IA obrigatório no upload do YouTube. Todas as publicações via APIs oficiais. Campo de AI disclosure deve ser preenchido automaticamente no Publisher Service.

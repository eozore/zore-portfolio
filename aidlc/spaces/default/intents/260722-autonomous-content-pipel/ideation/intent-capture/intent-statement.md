# Intent Statement
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

**Intent ID:** 260722-autonomous-content-pipel
**Data:** 2026-07-22
**Scope:** enterprise | **Depth:** Comprehensive

---

## Problema Central

Victor Zore é um criador de conteúdo técnico de altíssima qualidade sobre IA, ML e Estatística. O processo atual de produção é uma cadeia de passos manuais que consome tempo desproporcional ao valor de cada etapa: conversar com Claude → gerar pacote HTML → gravar voz manualmente → enviar ao HeyGen → editar vídeo → publicar no YouTube → adaptar para redes sociais (etapa que frequentemente é simplesmente pulada por falta de tempo).

O resultado prático: **as redes sociais ficam em silêncio** mesmo quando o conteúdo principal (YouTube) existe. O gargalo não é falta de ideias nem falta de conteúdo — é a fricção de transformar um conteúdo em múltiplos formatos distribuídos.

**O problema a resolver:** eliminar a fricção de produção e distribuição omnicanal, permitindo que Victor gaste tempo apenas com o que só ele pode fazer — cocriação intelectual do conteúdo — enquanto o sistema executa todo o resto de forma autônoma e confiável.

---

## Target: Quem se Beneficia e Como

**Usuário primário:** Victor Zore — criador de conteúdo técnico, opera sozinho, sem equipe de produção.

**Dor experimentada:**
- Sessão de produção de 1 vídeo consome 4-8h de trabalho manual fragmentado
- Redes sociais ficam sem conteúdo por dias porque a adaptação manual é inviável solo
- A qualidade do conteúdo técnico exige rigor que ferramentas genéricas não respeitam

**Ganho esperado:**
- 1 sessão semanal de cocriação com o CMO Agent (30-60 min) gera uma semana inteira de conteúdo para todos os canais
- Tempo total de Victor em produção cai para menos de 1h/dia
- Zero silêncio prolongado nas redes sociais (máximo 3 dias sem post em qualquer canal)

**Audiência final (indireta):** Engenheiros de dados, cientistas de ML, líderes técnicos que consomem o conteúdo do éozoré nos múltiplos canais.

---

## Visão do Sistema

Um **Content Production Studio autônomo** integrado ao CSM Studio existente, onde cada peça de conteúdo é tratada como um **projeto com ciclo de vida rastreável**:

```
[Cocriação CMO]  →  [Pacote de Conteúdo Aprovado]  →  [Pipeline de Produção]  →  [Fila de Publicação]
     (Victor)              (kanban card)                  (microserviços)           (agendado)
```

### Os três objetivos de conteúdo (não negociáveis)

1. **Educativo:** ensinar técnicas de IA/ML com rigor matemático — o "porquê" antes do "como"
2. **Tráfego para YouTube:** conteúdos sociais são fragmentos do vídeo principal, não peças independentes — cada post social é um gancho para o canal
3. **Naturalidade máxima:** a qualidade e naturalidade do conteúdo gerado por IA têm peso maior que economia de custo (teto de R$100/vídeo completo, mas dentro desse teto priorizar qualidade)

---

## Arquitetura de Alto Nível (sinal inicial)

### Microserviços comunicando via Pub/Sub

O sistema funciona como um **escritório de especialistas** onde cada profissional recebe um contrato/arquivo, executa sua especialidade e passa o resultado para o próximo:

```
CMO Agent (interativo)
    |-- Pub/Sub: "pacote_aprovado" -->
                                    Content Writer Agent
                                    YouTube Script Agent
                                    Distribution Agent
                                         |-- Pub/Sub: "roteiro_pronto" -->
                                                                         ElevenLabs TTS Service
                                                                              |-- Pub/Sub: "audio_pronto" -->
                                                                                                           HeyGen Avatar Service
                                                                                                                |-- Pub/Sub: "avatar_pronto" -->
                                                                                                                                              Video Editor Service
                                                                                                                                                   |-- Pub/Sub: "video_pronto" -->
                                                                                                                                                                                 Publisher Service
```

### O Contrato Central: Pacote HTML com Manifesto JSON

O `pacote-conteudo-{tema}.html` permanece como contrato de dados central. O manifesto JSON embutido define:
- Segmentos do roteiro com mapeamento explícito `segmento → slide` (sem necessidade de inferência por IA)
- Scripts por segmento (texto que vai para ElevenLabs → áudio → HeyGen)
- Posições das ilustrações no timeline do vídeo (o editor recebe o avatar já falando e insere as ilustrações nas posições declaradas)

### Kanban de Projetos

Cada pacote de conteúdo é um projeto visível no CSM Studio como um card kanban com estados:
- **Em Cocriação** → **Aguardando Aprovação** → **Gerando Mídia** → **Aguardando Publicação** → **Publicado**

---

## Métricas de Sucesso (primeiros 3 meses)

| Métrica | Target |
|---|---|
| Tempo de Victor por conteúdo completo | ≤ 1h (vs. 4-8h atual) |
| Frequência YouTube | 1 vídeo/semana consistente |
| Silêncio máximo nas redes | ≤ 3 dias sem post em qualquer canal |
| Custo por vídeo completo (todos os formatos) | ≤ R$100 |
| Canais ativos simultaneamente | 6+ (YouTube, Shorts, Instagram, LinkedIn, Threads, Comunidade YT) |

---

## Trigger da Iniciativa

**Por que agora:** A infraestrutura base já existe — o CSM Studio funciona, o `cmo_agent` produz conteúdo de qualidade, a `tool-videoyoutube` tem uma pipeline de edição completa, as integrações sociais estão parcialmente ativas. O que falta é a **cola** entre essas peças: os microserviços de orquestração que conectam a aprovação de um pacote à publicação final em todos os canais, sem intervenção manual.

---

## Initial Scope Signal

**Scope:** `enterprise` — sistema completo com múltiplos microserviços, painel de configuração, kanban de projetos, integrações com 6+ plataformas, pipeline de vídeo com ElevenLabs + HeyGen + FFmpeg, sistema de aprovação com auditoria, controle de custos, conformidade com políticas de plataformas.

**Não é um MVP** — é a construção completa do sistema que Victor precisa operar sozinho de forma sustentável. Complexidade justificada pela ausência de equipe de produção.

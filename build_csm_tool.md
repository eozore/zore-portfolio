# 📐 Blueprint de Produto e UX: CSM Studio (Content Strategy Machine)

Este documento dita as regras de Arquitetura, Persona e Experiência do Usuário (UX) para a suíte de ferramentas de marketing autônomo da plataforma `eozore.com`.

---

## 1. Filosofia Operacional e Personas

O CSM Studio não é um gerador de textos genérico. A dinâmica de uso simula uma **Reunião Executiva de Pauta e Estratégia**:

- **O Usuário (Victor Zore):** Atua no papel de **CEO** e Líder Técnico. Ele detém a visão de mercado, os aprendizados práticos de engenharia e direciona filosoficamente o que deve ser ensinado.
- **A IA Principal (CMO / Especialista em Conteúdo):** Atua no papel de **Diretor de Marketing Crítico e Estrategista Sênior**. Não aceita ordens superficiais sem questionar. Provoca o CEO sobre posicionamento de SEO, rigor matemático, ganchos provocativos e adequação ao público de engenharia de dados.

---

## 2. As 5 Fases da Experiência (Workflow de Abas)

### 💬 Fase 1: Bate-Papo Consultivo de Concepção (Aba 1 - Bate-Papo CMO)
1. **Início Proativo:** Ao abrir a aba, o CMO consulta automaticamente o histórico do Firestore e recepciona o CEO com sugestões quentes ou perguntando sobre novidades de produção.
2. **Entrevista Socrática:** Através de um chat elegante e responsivo, CEO e CMO debatem o tema. O CMO faz perguntas diretas e simples para estruturar o artigo.
3. **Handoff Criativo:** Quando a pauta atinge maturidade conceitual, o CMO emite o diagnóstico final e disponibiliza o comando: **`[✨ Pauta Fechada! Acionar Time de Redação Técnica →]`**.

---

### 📝 Fase 2: Redação de Artigo Rico (Aba 2 - Geração)
O redator técnico recebe a pauta consolidada do CMO e emite o texto mestre no padrão `ARTICLE_FORMAT.md`:
1. **Hierarquia Didática:** Introdução direta → Fundamentação Teórica e Matemática (o PORQUÊ) → Implementação Prática Comentada (o COMO) → Resumo comparativo.
2. **Fórmulas LaTeX:** Fórmulas inline com `$expr$` e blocos de equações centralizados com `$$expr$$`.
3. **Diagramas Arquiteturais (Mermaid):** Blocos de diagramas ` ```mermaid ` com renderização interativa clara e botões de zoom/pan.
4. **Gráficos Científicos e Sandbox Python (Matplotlib):** Qualquer bloco de código `` ```python `` que contenha comandos de plotagem (ex: `plt.plot`, `matplotlib`) é interceptado pelo sandbox local (`code_executor.py`), executado em backend `Agg` e tem sua imagem gerada e injetada no preview automaticamente, garantindo que o blog exiba os gráficos de perda e dados em tempo real.

---

### 🌐 Fase 3: Metadados e Publicação no Blog (Aba 3 - Publicação)
1. **Curadoria de Metadados**: Permite a revisão e edição amigável do título sugerido, slug da URL do artigo, imagem de capa, tempo estimado de leitura e data de agendamento do post.
2. **Publicação Direta**: Publica o artigo no banco de dados Cloud Firestore (`articles`), tornando-o disponível imediatamente no site público sob a rota `/blog`.

---

### 📹 Fase 4: Roteiro de Vídeo Didático (Aba 4 - YouTube Roteiro)
1. **Vídeo Scripting**: O agente especializado lê o artigo finalizado e gera um roteiro detalhado do YouTube com streaming em tempo real via Vertex AI.
2. **Estrutura do Vídeo**: O roteiro obedece a blocos de ação (HOOK forte, Teoria profunda com LaTeX, Prática de Código e CTAs para o blog).
3. Indicações visuais e diretrizes de tela são posicionadas em blocos de blockquote:
   > [CENA: Victor falando para a câmera com fundo desfocado]

---

### 🗓️ Fase 5: Derivações Massivas & Fila Social (Aba 5 - Derivações)
O time de marketing consome o artigo e o roteiro para criar a campanha de distribuição omnicanal:
1. **Formatos Derivados:**
   - **LinkedIn**: 2 posts de alto engajamento técnico.
   - **YouTube Shorts & Reels**: Roteiros verticais e rápidos de 30-60 segundos.
   - **Carrosséis**: Slides de conteúdo prontos e estruturados.
   - **Posts com Imagem**: Feed do Instagram com design sugerido.
   - **Stories**: 10 a 12 stories sequenciais com ideias de interações.
2. **Geração de Avatar Realista (HeyGen)**: Nos formatos Reels e Shorts, você pode gerar um avatar digital realista do Victor Zoré falando o script. O CSM Studio faz a chamada real ou simulada no HeyGen V2, exibe o progresso de renderização e reproduz o resultado no player mobile nativo.
3. **Commit de Aprovados**: Por padrão, todos nascem como `🟡 Em Revisão`. Apenas os itens explicitamente alterados para `🟢 Aprovado` são salvos no Firestore (`social_queue`) para agendamento.

---

## ⚙️ 6. Painel de Configurações (Aba 6 - Configurações)
*   **Customização de Prompts**: Permite que o CEO edite as System Instructions de cada agente de IA separadamente e salve-as no banco.
*   **Gerenciador de Chaves**: Permite salvar chaves integradas com segurança (com Firestore no modo local de desenvolvimento e GCP Secret Manager em produção).

---

## 📐 7. Decisões Arquiteturais & Estratégia de Dados V2 (SaaS-Ready)

As seguintes decisões de design de dados e infraestrutura foram homologadas para orientar o desenvolvimento com menor atrito na transição para a V2:

### A. Estratégia de Mídia Serverless (Cloud Storage)
*   **Decisão**: Todos os arquivos de mídia gerados dinamicamente (plots científicos do matplotlib, arquivos PDF, avatares HeyGen e assets estáticos) devem ser persistidos no **Google Cloud Storage (GCS)** sob a hierarquia de caminhos `/tenants/{tenantId}/sessions/{sessionId}/plots/`.
*   **Objetivo**: Evitar colisões de arquivos no disco local em instâncias concorrentes serverless (Cloud Run) e habilitar a entrega via CDN distribuída.
*   **Políticas de Custo**: Será configurada uma Lifecycle Policy no bucket para expirar e **deletar automaticamente** mídias temporárias e intermediárias da subpasta `/sessions/` após 30 dias, reduzindo custos de armazenamento ao mínimo.

### B. Resiliência de Checkpoint e Auditoria no Firestore
*   **Decisão**: Durante as fases da V1 e transição para a V2, o estado dos checkpoints do pipeline de geração (papers retornados do arXiv, outlines brutos, revisões parciais) deve ser **totalmente persistido** no Firestore da sessão para garantir auditoria total em cada transição da linha de produção.
*   **Evolução de Escala**: Quando o volume de sessões crescer a ponto de impactar os limites do Firestore (1MB/documento e custos de I/O), os históricos detalhados de rascunhos antigos serão compactados e arquivados em arquivos JSON no próprio Cloud Storage, mantendo o Firestore com referências ativas leves.

### C. Simplificação Pragmática de Fluxos
*   **Decisão**: Integrações de autenticação OAuth completas (como integração direta e publicação autônoma em canais do YouTube ou mídias via tokens dinâmicos) serão mantidas de forma simplificada e manual na V1/V2 inicial, focando os recursos na estabilidade da orquestração de conteúdo e na partição de tenants antes de escalar as permissões OAuth do SaaS.


# éozoré — Plataforma de Criação e Curadoria de Conteúdo por IA (CSM Studio)

Plataforma unificada do Victor Zoré contendo a apresentação profissional, blog técnico avançado, portfólio e o **CSM Studio (Content Studio Manager)**: uma suíte interna de curadoria e criação de conteúdo operada por agentes autônomos de IA.

---

## 🏗️ Estrutura do Ecossistema

O projeto é estruturado em um monorepo que separa a aplicação web (Next.js) do microserviço de IA (Python/FastAPI):

```
├── apps/web/                  # Next.js (App Router) — O Frontend & APIs
│   ├── src/app/               # Páginas públicas e administrativas do CSM
│   │   ├── admin/csm/         # CSM Studio (/admin/csm)
│   │   └── api/csm/           # Endpoints de proxy, integração HeyGen, Firestore e Configs
│   ├── src/components/csm/    # Componentes e abas do painel (Idea, Generate, Publish, etc.)
│   ├── src/lib/               # Conexão Firebase Admin, Vertex AI, SEO e i18n
│   └── src/styles/            # Temas e folhas de estilo globais do site
│
├── agents/cmo_agent/          # Python Agent Framework (FastAPI) — Orquestrador de IA
│   ├── agent.py               # Entrada do servidor FastAPI (porta 8090)
│   ├── research_agent.py      # Agente de Pesquisa (integração arXiv para artigos)
│   ├── critic_agent.py        # Agente Revisor/Crítico
│   ├── distribution_agent.py  # Agente Distribuidor (derivação de mídias estruturadas)
│   ├── code_executor.py       # Sandbox Python para execução de gráficos (matplotlib)
│   └── tools.py               # Helpers de banco e integrações externas
│
├── cloudbuild.yaml            # Pipeline de deploy (Cloud Run standalone)
└── README.md                  # Este arquivo de documentação
```

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Detalhes |
|---|---|---|
| **Frontend & APIs** | Next.js (App Router) + TypeScript | Standalone build com Tailwind CSS e CSS Modules |
| **Orquestrador de IA** | Python 3.12 + FastAPI + Uvicorn | Microserviço executando na porta **8090** |
| **Modelos de Linguagem**| Google Vertex AI (Gemini 2.5) | Chamadas estruturadas e streaming via Server-Sent Events (SSE) |
| **Banco de Dados** | Cloud Firestore | Armazenamento de artigos publicados, sessões de chat e fila social |
| **Chaves de API** | GCP Secret Manager / Firestore | Armazenamento das chaves do HeyGen e prompts customizados |
| **Renderizador de Vídeo**| HeyGen V2 Video API | Geração automatizada de avatares com falas traduzidas (Reels/Shorts) |
| **Deploy & Infra** | Google Cloud Run + Cloud Build | Push na branch `main` dispara o deploy contínuo automático |

---

## 🚀 CSM Studio — Pipeline de Criação de Conteúdo

O painel administrativo do CSM Studio está dividido em um fluxo sequencial estruturado por abas:

1. **💬 01. Bate-papo CMO (IdeaTab)**: Interface de chat interativa em tempo real com o *CMO Agent* para amadurecimento conceitual do tema do artigo, gerando um briefing técnico estruturado.
2. **✍️ 02. Geração & Editor (GenerateTab)**: Aciona o pipeline de redação. O agente pesquisa artigos científicos relevantes no **arXiv**, escreve o post em markdown técnico avançado e renderiza fórmulas matemáticas (KaTeX), diagramas de fluxo (Mermaid) e **gráficos matemáticos/científicos interativos** (matplotlib executado dinamicamente).
3. **🌐 03. Publicação (PublishTab)**: Configura slug, categoria, capa do artigo e realiza o deploy direto no Firestore para visualização imediata no blog público.
4. **📹 04. YouTube Roteiro (YoutubeTab)**: Gera um roteiro de vídeo completo estruturado em blocos de cena (HOOK, Teoria com fórmulas e Código) no tom de voz técnico de Victor Zore.
5. **📱 05. Derivações (RepurposeTab)**: Deriva o artigo em uma campanha semanal de mídias: posts de LinkedIn, Reels/Shorts (com botão para renderizar avatar realista no **HeyGen** e player nativo de simulação no mockup do celular), Carrosséis para o Instagram, posts com fotos e Stories. Agende tudo diretamente para o Firestore.
6. **⚙️ 06. Configurações (SettingsTab)**: Permite o ajuste fino das instruções de sistema (`System Instruction`) de cada agente e a gravação de chaves de API integradas.

---

## ⚙️ Setup Local

### 1. Requisitos de Variáveis de Ambiente

Crie o arquivo `apps/web/.env.local` na pasta correspondente:

```env
FIREBASE_PROJECT_ID=vazfy-417019
GOOGLE_APPLICATION_CREDENTIALS=/caminho/para/seu-gcp-key.json
CSM_PASSWORD_HASH=sua_senha_hash_sha256
CMO_AGENT_URL=http://localhost:8090
```

Crie o arquivo `agents/cmo_agent/.env`:

```env
FIREBASE_PROJECT_ID=vazfy-417019
PORT=8090
```

### 2. Rodando o microserviço de IA (Python)

Instale as dependências e inicie o servidor:

```bash
cd agents/cmo_agent
pip3 install -r requirements.txt
python3 agent.py
```
O servidor rodará em `http://localhost:8090`.

### 3. Rodando o Frontend (Next.js)

Instale e rode em modo de desenvolvimento:

```bash
cd apps/web
npm install
npm run dev
```
O painel estará disponível em `http://localhost:3000/admin/csm`.

---

## 🔒 Licença

Privado — © 2026 Victor Zoré. Todos os direitos reservados.

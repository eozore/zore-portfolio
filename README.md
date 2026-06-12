# éozoré — Portfólio & Plataforma

Repositório monorepo do Victor Zoré. Contém o site/portfólio público, blog com artigos gerados por IA, e a plataforma de marketing agêntico.

## Estrutura

```
├── apps/
│   ├── web/          # Next.js — portfólio público (SSG) + blog (ISR) + área logada
│   ├── agents/       # Python (ADK) — time de agentes de marketing (Cloud Run)
│   └── renderer/     # Puppeteer headless — renderização de mídia (Cloud Run)
├── mcp/postiz/       # MCP Server auto-hospedado (publicação em redes sociais)
├── packages/shared/  # Tipos e utilitários compartilhados (TypeScript)
├── infra/            # Terraform — infraestrutura GCP
├── blogs/            # Artigos de blog (HTML estático, legado — migrando para Next.js)
├── tools/            # Tools públicas (em construção)
└── eozoreIA/         # Documentação interna da plataforma de IA
```

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Next.js (App Router) + TypeScript |
| Agentes | Google ADK (Python) + Vertex AI / Gemini |
| Auth | Firebase Authentication |
| Banco | Cloud Firestore (Native mode) |
| Infra | GCP (Cloud Run, Secret Manager, Pub/Sub, Cloud Storage) |
| IaC | Terraform |
| CI/CD | Cloud Build |

## Setup Local

```bash
# 1. Copie o arquivo de variáveis de ambiente
cp .env.example .env

# 2. Frontend (Next.js)
cd apps/web
npm install
npm run dev

# 3. Agentes (Python)
cd apps/agents
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Deploy

O deploy é feito automaticamente via Cloud Build ao fazer push na branch `main`.

- **Site estático**: synced para Cloud Storage via `cloudbuild.yaml`
- **Apps (web + agents)**: Cloud Run (via Dockerfile em cada app)
- **Infra**: Terraform em `infra/`

## Segurança

- Tokens OAuth armazenados exclusivamente no Secret Manager (por tenant)
- Artigos enviados via API autenticada (somente agentes autorizados)
- Firestore Security Rules com isolamento multi-tenant
- Service Accounts com least-privilege

## Licença

Privado — © 2025 Victor Zoré. Todos os direitos reservados.

# éozoré — Portfólio

Site/portfólio do Victor Zoré. Contém a apresentação profissional, projetos, blog com artigos gerados por IA, e tools.

## Estrutura

```
├── apps/web/             # Next.js (App Router) — o site completo
│   ├── src/app/          # Páginas (home, blog, tools)
│   ├── src/app/api/      # API de artigos (recebe posts dos agentes de IA)
│   ├── src/components/   # Componentes React
│   ├── src/lib/          # Firebase, i18n, validação
│   └── public/image/     # Assets estáticos
├── cloudbuild.yaml       # Pipeline de deploy (Cloud Run)
└── ARTICLE_FORMAT.md → apps/web/ARTICLE_FORMAT.md
```

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Framework | Next.js (App Router) + TypeScript |
| Estilo | Tailwind CSS |
| Banco (artigos) | Cloud Firestore |
| Deploy | Cloud Run (GCP) via Cloud Build |
| CI/CD | Push na `main` → deploy automático |

## Setup Local

```bash
cd apps/web
npm install
npm run dev
```

## API de Artigos

Os agentes de IA publicam artigos via:

```
POST /api/articles
Authorization: Bearer <ARTICLE_API_KEY>
Content-Type: application/json
```

O formato completo está documentado em `apps/web/ARTICLE_FORMAT.md`.

## Deploy

Push na `main` dispara o Cloud Build que:
1. Build da imagem Docker (Next.js standalone)
2. Push para Container Registry
3. Deploy no Cloud Run (us-central1)

## Licença

Privado — © 2025 Victor Zoré. Todos os direitos reservados.

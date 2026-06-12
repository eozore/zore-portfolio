# Postiz MCP Server

Servidor MCP (Model Context Protocol) auto-hospedado para publicação em redes sociais. Baseado no [Postiz](https://github.com/gitroomhq/postiz-app), oferece interface unificada para publicação no LinkedIn, Instagram, YouTube e outras plataformas.

## Arquitetura

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Serviço de      │────▶│  Postiz MCP      │────▶│  APIs Sociais    │
│  Agentes         │     │  (Cloud Run)     │     │  (LinkedIn, IG,  │
│  (FastAPI + ADK) │     │  INTERNAL_ONLY   │     │   YouTube)       │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                │
                         ┌──────┴──────┐
                         │             │
                    ┌────▼────┐  ┌─────▼─────┐
                    │Cloud SQL│  │Memorystore│
                    │(Postgres)│  │  (Redis)  │
                    └─────────┘  └───────────┘
```

## Desenvolvimento Local

### Pré-requisitos

- Docker e Docker Compose v2
- Credenciais OAuth de desenvolvimento (Meta, LinkedIn, YouTube)

### Setup

```bash
cd mcp/postiz

# Copiar variáveis de ambiente
cp .env.example .env

# Editar .env com suas credenciais OAuth
# (META_APP_ID, META_APP_SECRET, LINKEDIN_CLIENT_ID, etc.)

# Subir os serviços
docker compose up -d

# Verificar logs
docker compose logs -f postiz

# Verificar saúde
curl http://localhost:5000/api/health
```

### Serviços Locais

| Serviço    | Porta | Descrição                     |
|-----------|-------|-------------------------------|
| Postiz    | 5000  | Aplicação MCP                 |
| PostgreSQL| 5432  | Banco de dados                |
| Redis     | 6379  | Cache e filas de publicação   |

### Parar serviços

```bash
docker compose down

# Para remover volumes (banco de dados):
docker compose down -v
```

## Deploy em Produção (Cloud Run)

### Infraestrutura Provisionada

O deploy do Postiz no Cloud Run é gerenciado pelo Terraform em `infra/main.tf`:

- **Serviço Cloud Run**: `postiz` com `INGRESS_TRAFFIC_INTERNAL_ONLY`
- **Service Account**: `sa-postiz` (acesso mínimo)
- **Rede**: Apenas o serviço de agentes (`sa-agents`) pode invocar o Postiz
- **Secret Manager**: `postiz-config` para configurações sensíveis

### Características de Produção

- **Sem acesso público**: Ingress configurado como `INTERNAL_ONLY`
- **Isolamento**: Apenas `sa-agents` tem permissão `roles/run.invoker`
- **Escalabilidade**: 0-2 instâncias (scale to zero quando inativo)
- **Recursos**: 1 vCPU, 512Mi memória por instância

### Dependências em Produção

| Dependência | Serviço GCP       | Configuração via                      |
|-------------|-------------------|---------------------------------------|
| PostgreSQL  | Cloud SQL         | `DATABASE_URL` em Secret Manager      |
| Redis       | Memorystore       | `REDIS_URL` em Secret Manager         |
| OAuth creds | Secret Manager    | `social-tokens/{tenantId}/{platform}` |

### Deploy

O deploy é feito via Cloud Build, que constrói a imagem a partir do `Dockerfile` e atualiza o serviço Cloud Run:

```bash
# Build e push da imagem
gcloud builds submit --tag gcr.io/${PROJECT_ID}/postiz .

# Atualizar o serviço Cloud Run
gcloud run services update postiz \
  --image gcr.io/${PROJECT_ID}/postiz \
  --region us-central1 \
  --set-secrets="DATABASE_URL=postiz-config:latest" \
  --set-secrets="REDIS_URL=postiz-config:latest"
```

### Variáveis de Ambiente (Produção)

As variáveis sensíveis são injetadas via Secret Manager. As variáveis de configuração são definidas no Cloud Run:

```
NODE_ENV=production
PORT=5000
DATABASE_URL=<Cloud SQL connection string via Secret Manager>
REDIS_URL=<Memorystore connection string via Secret Manager>
JWT_SECRET=<via Secret Manager>
```

Os tokens OAuth dos tenants são gerenciados separadamente pelo serviço de agentes, que os busca do Secret Manager (`social-tokens/{tenantId}/{platform}`) e os passa por chamada ao MCP.

## Integração com Agentes (ADK)

O serviço de agentes conecta ao Postiz via `McpToolset` do ADK:

```python
from google.adk.tools import McpToolset

async def get_mcp_toolset(tenant_id: str, platform: str) -> McpToolset:
    token = await read_secret(f"social-tokens/{tenant_id}/{platform}")
    return McpToolset(
        endpoint=POSTIZ_BASE_URL,  # URL interna do Cloud Run
        credentials={"tenant_id": tenant_id, "token": token}
    )
```

**Princípios de segurança:**
- Credencial por chamada (nunca em memória entre requisições)
- Token lido do Secret Manager a cada operação
- Nenhum token global ou compartilhado entre tenants
- Abort limpo se token não encontrado ou Secret Manager indisponível

## Estrutura de Arquivos

```
mcp/postiz/
├── .env.example          # Template de variáveis de ambiente
├── .gitkeep              # Placeholder git
├── docker-compose.yml    # Dev local (Postiz + Postgres + Redis)
├── Dockerfile            # Build para Cloud Run (wrapper da imagem oficial)
└── README.md             # Este arquivo
```

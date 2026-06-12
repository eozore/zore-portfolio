# Postiz MCP Server — Cloud Run Deployment
# Referência: https://github.com/gitroomhq/postiz-app
#
# Este Dockerfile usa a imagem oficial do Postiz como base.
# Em produção (Cloud Run), as dependências (PostgreSQL via Cloud SQL,
# Redis via Memorystore) são injetadas via variáveis de ambiente.

FROM ghcr.io/gitroomhq/postiz-app:latest

# Labels para rastreabilidade
LABEL maintainer="zore-marketing-platform"
LABEL description="Postiz MCP Server for social media publishing"
LABEL org.opencontainers.image.source="https://github.com/gitroomhq/postiz-app"

# Cloud Run define PORT automaticamente; Postiz escuta na 5000 por padrão
ENV PORT=5000
ENV NODE_ENV=production

# Healthcheck para Cloud Run
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || exit 1

EXPOSE ${PORT}

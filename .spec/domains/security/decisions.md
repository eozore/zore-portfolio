# CSM Studio — Setup de Segurança

> **Atualização:** os passos 1 e 2 abaixo já foram executados nesta sessão (segredo
> criado, IAM vinculada, deploy feito com `ENVIRONMENT=production` e
> `CMO_INTERNAL_SECRET` propagado). Documento mantido como referência — só é preciso
> agir de novo se o segredo for rotacionado ou se um novo ambiente for provisionado.

Esta sessão endureceu a comunicação Next.js ↔ cmo-agent e a postura de SSL/CORS do
serviço Python.

## 1. Criar o segredo compartilhado `cmo-internal-secret`

O `cmo-agent` roda em Cloud Run com `--allow-unauthenticated` (necessário porque o
Next.js e o Python são serviços separados sem IAM invoker configurado). Como mitigação,
todo request do Next.js para o cmo-agent agora carrega um header `X-Internal-Auth`, e o
FastAPI rejeita qualquer request sem esse header **quando o segredo está configurado**.
Sem o segredo criado, o comportamento de hoje é preservado (endpoint aberto, com um log
de aviso) — nada quebra até você rodar isto:

```bash
# Gera um segredo aleatório forte e cria no Secret Manager
openssl rand -base64 32 | gcloud secrets create cmo-internal-secret \
  --project=vazfy-417019 --data-file=-

# Dá acesso de leitura às service accounts do Cloud Run que usam o segredo
gcloud secrets add-iam-policy-binding cmo-internal-secret \
  --project=vazfy-417019 \
  --member="serviceAccount:$(gcloud projects describe vazfy-417019 --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Depois disso, o próximo deploy via `cloudbuild.yaml` / `agents/cloudbuild-agents.yaml`
já injeta `CMO_INTERNAL_SECRET` nos dois serviços (frontend e cmo-agent) — os arquivos
foram atualizados nesta sessão com `--set-secrets=...,CMO_INTERNAL_SECRET=cmo-internal-secret:latest`.

## 2. Confirmar `ENVIRONMENT=production` no cmo-agent

Os dois `cloudbuild*.yaml` agora setam `ENVIRONMENT=production` no deploy do cmo-agent.
Isso desativa o bypass de verificação SSL que antes rodava sempre (mesmo em produção) —
ver `agents/cmo_agent/agent.py`. Verifique após o deploy:

```bash
curl -s https://cmo-agent-4zffe4l4lq-uc.a.run.app/health | python3 -m json.tool
```

Campo `security.ssl_verification` deve ser `true` e `security.internal_auth_enforced`
deve ser `true` após o passo 1.

## 3. (Opcional, recomendado) CORS explícito

Por padrão, sem a env `ALLOWED_ORIGINS`, o cmo-agent não libera nenhuma origem de
browser (o Next.js chama server-to-server, então CORS de browser é irrelevante para o
fluxo normal). Só configure `ALLOWED_ORIGINS` se algum client browser precisar chamar o
cmo-agent diretamente:

```bash
gcloud run services update cmo-agent --region=us-central1 --project=vazfy-417019 \
  --update-env-vars=ALLOWED_ORIGINS=https://eozore.com
```

## 4. Próximo passo mais forte (não implementado ainda)

Trocar o segredo compartilhado por **IAM invoker** — remover `--allow-unauthenticated`
do cmo-agent e usar tokens OIDC assinados automaticamente pelo metadata server do Cloud
Run nas chamadas server-to-server do Next.js (`google-auth-library` já é dependência do
projeto). Isso elimina qualquer segredo estático rotacionável manualmente.

## O que já mudou no código nesta sessão (sem precisar de ação)

- `agents/cmo_agent/agent.py`: SSL bypass agora só roda com `ENVIRONMENT != production`;
  CORS restrito a `ALLOWED_ORIGINS` (vazio por padrão); middleware `X-Internal-Auth`
  ativo em todo endpoint exceto `/health` e `/pubsub/subscription`.
- `apps/web/src/lib/cmoAgent.ts`: ponto único que injeta o header em toda chamada
  Next.js → cmo-agent (11 rotas atualizadas).
- `/api/csm/config/security`: painel de leitura em Configurações → Segurança mostra o
  status atual (ambiente, SSL, CORS, auth interna) sem expor nenhum segredo.

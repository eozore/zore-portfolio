# 🚀 Roteiro de Desenvolvimento (Workflow): CSM Studio V2

Este workflow guia o agente de IA no passo a passo prático de codificação para implementar a refatoração preventiva e transicionar a plataforma para a V2 (SaaS-Ready/Multi-Tenant), mantendo a estabilidade monotenant atual do portfólio.

---

## 📋 Checklist de Execução

### 🏗️ Fase 1: Abstração e Resolvedores de Banco (Firestore Paths)
*   [ ] **Passo 1.1**: Criar o arquivo `apps/web/src/lib/dbPaths.ts` contendo o mapeamento de coleções com suporte opcional a `tenantId` conforme definido no plano preventivo.
*   [ ] **Passo 1.2**: Mapear e substituir todas as chamadas `db.collection(...)` e `db.doc(...)` nos endpoints de API do Next.js:
    *   `api/csm/generate/route.ts`
    *   `api/csm/session/route.ts`
    *   `api/csm/repurpose/route.ts`
    *   `api/csm/youtube/route.ts`
    *   `api/csm/publish/route.ts`
    *   `api/csm/config/route.ts`
    *   `api/csm/config/keys/route.ts`
*   [ ] **Passo 1.3**: Criar o resolvedor correspondente em Python em `agents/cmo_agent/db_paths.py` e refatorar as conexões Firestore no microserviço FastAPI (`agents/cmo_agent/tools.py`).

### 🔒 Fase 2: Criptografia e BYOK Seguro
*   [ ] **Passo 2.1**: Criar um helper utilitário de criptografia `apps/web/src/lib/crypto.ts` usando a Web Crypto API nativa (AES-GCM-256) para cifrar e decifrar chaves de API usando uma chave mestre de ambiente (`ENCRYPTION_KEY`).
*   [ ] **Passo 2.2**: Atualizar o endpoint `/api/csm/config/keys` (GET/POST) para salvar as chaves criptografadas no Firestore e decifrá-las ao exibir (mascaradas) no painel.
*   [ ] **Passo 2.3**: Atualizar a rota `/api/csm/heygen` para decifrar as chaves antes de enviar o payload para a API oficial do HeyGen.

### 💾 Fase 3: Resiliência de Checkpoint e Cache
*   [ ] **Passo 3.1**: Atualizar a definição do objeto de sessão e do estado de `draft` no Firestore para incluir os metadados de checkpoint por etapa (arXiv papers em cache, outlines gerados).
*   [ ] **Passo 3.2**: Refatorar o pipeline de geração de artigos para consultar o Firestore. Se os papers em cache já existirem no checkpoint, pular a chamada ao arXiv e passar os dados direto para o redator de IA, agilizando execuções repetidas.

### 📊 Fase 4: Telemetria de Uso e Custos
*   [ ] **Passo 4.1**: Criar o middleware ou helper de log em `/api/csm/generate` e rotas irmãs para capturar os tokens de entrada/saída (`input_tokens`, `output_tokens`) retornados pelo Vertex AI.
*   [ ] **Passo 4.2**: Computar a estimativa de custos com base na tabela do Gemini 2.5 e gravar cada chamada na coleção `usage_logs`.

---

## 🧪 Critérios de Aceitação e Testes locais
1.  **Sem regressão visual**: O CSM Studio e o blog público devem continuar funcionando exatamente da mesma forma que hoje para o Victor Zoré (com `tenantId = null`).
2.  **Validação de Criptografia**: As chaves salvas em `/agent_configurations/api_keys` no Firestore real devem aparecer sob criptografia irreversível em texto puro em caso de inspeção do banco.
3.  **Logs de Uso**: Toda geração de artigo ou roteiro deve criar com sucesso um documento detalhando os custos de tokens na coleção `usage_logs`.

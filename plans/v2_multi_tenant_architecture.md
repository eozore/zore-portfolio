# 📐 Plano de Arquitetura: CSM Studio V2 Multi-Tenant

Este documento descreve a análise técnica, o modelo de isolamento de dados e as mudanças necessárias para transformar o CSM Studio V1 de uma ferramenta de usuário único em um **SaaS Multi-tenant (V2)** robusto e seguro.

---

## 1. Diagnóstico do Estado Atual (V1 Monotenant)

A V1 atual do CSM Studio foi projetada para uso estritamente privado de Victor Zore (`eozore.com`). As seguintes dependências e acoplamentos monolíticos existem:

```
┌────────────────────────────────────────────────────────┐
│                      CSM V1                            │
└──────────────────────────┬─────────────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐ ┌─────────────────────────┐
│     Firestore (Único)   │ │  Secret Manager (Único) │
│ - csm_sessions (global) │ │ - HEYGEN_API_KEY        │
│ - articles (global)     │ │ - GEMINI_API_KEY        │
│ - agent_configs         │ │   (Chaves do Admin)     │
└─────────────────────────┘ └─────────────────────────┘
```

*   **Autenticação**: Baseada em cookie/header simplificado (`x-csm-session = authenticated`) e validação de hash estático (`CSM_PASSWORD_HASH`).
*   **Armazenamento (Firestore)**:
    *   `csm_sessions`: Coleção global indexada apenas por `sessionId`. Qualquer usuário com acesso ao admin enxergaria e alteraria o rascunho de outro se soubesse o ID da sessão.
    *   `articles`: Coleção global de posts do portfólio pessoal.
    *   `agent_configurations`: Documento único (`api_keys`) na raiz salvando chaves globais.
*   **Chaves de API**: Lidas diretamente das variáveis de ambiente (`process.env`) ou do GCP Secret Manager do projeto `vazfy-417019`.

---

## 2. A Estratégia de Isolamento Multi-Tenant (V2)

Para tornar a plataforma multi-tenant, precisamos isolar o contexto de três camadas: **Identidade**, **Banco de Dados (Partição)** e **Chaves de API (Billing/BYOK)**.

### A. Modelo de Dados Firestore (Particionado por `tenantId`)

Usaremos o modelo de **Isolamento Lógico em Coleção Única** (Shared Database, Shared Schema) com filtragem estrita por índice de `tenantId` (Tenant-ID Identifier Pattern). Isso mantém o custo de infraestrutura no patamar gratuito do Firestore e permite escalar de forma instantânea.

```
/tenants/{tenantId}/
    ├── profile: { name, email, planType, createdAt }
    ├── api_keys/keys: { HEYGEN_API_KEY, GEMINI_API_KEY, ... } (Criptografado)
    ├── agent_configurations/{agentName}: { activePrompt, fallbackPrompt }
    ├── sessions/{sessionId}: { messages, draft: {...} }
    └── articles/{articleId}: { title, content, slug, status }
```

> [!IMPORTANT]
> **Segurança de Dados**: Para evitar o risco de *data leakage* (vazamento de dados entre clientes), as **Security Rules** do Firestore devem validar a hierarquia estrita de subcoleções:
> ```javascript
> service cloud.firestore {
>   match /databases/{database}/documents {
>     match /tenants/{tenantId}/{document=**} {
>       allow read, write: if request.auth != null && request.auth.uid == tenantId;
>     }
>   }
> }
> ```

---

### B. Gestão de Chaves de API (Bring Your Own Key - BYOK)

Uma plataforma SaaS de IA que gera roteiros, artigos longos e renderiza avatares HeyGen reais tem custos operacionais insustentáveis se o dono da plataforma arcar com a conta de processamento de todos. O CSM V2 deve operar no modelo **BYOK**:

*   **Chaves do Admin (Default)**: O sistema fornece créditos de teste limitados usando a infraestrutura do Victor Zoré (via chaves no Secret Manager do projeto base).
*   **Chaves do Cliente (Custom)**: O usuário insere suas próprias chaves de API (Gemini, HeyGen, YouTube Client ID) no painel de configurações.
*   **Segurança de Chaves Locais**: As chaves digitadas pelos usuários **não** devem ser salvas em texto puro no Firestore. Devem ser criptografadas no backend (Next.js Edge) usando uma chave de criptografia master (`AES-GCM-256`) antes da persistência no documento `/tenants/{tenantId}/api_keys/keys`.

---

### C. Arquitetura de Cache e Sessão do Agente Python

O microserviço Python (`agents/cmo_agent/`) na porta 8090 atualmente não tem estado em memória de usuário único, mas interage com o Firestore usando conexões diretas.
Para a V2, o endpoint de agentes FastAPI deve receber o cabeçalho `X-Tenant-Id` em todas as requisição.

```
[Client App] ──(Next.js Route)──► [FastAPI (8090)] ──► [Firestore Partition]
   tenantId          JWT Proxy        X-Tenant-Id          /tenants/{tenantId}
```

*   **Identidade Federada**: O Next.js valida o JWT do usuário (via **Firebase Authentication** ou **NextAuth.js**), extrai o `uid` (que serve de `tenantId`) e o repassa em cabeçalhos assinados nas requisições ao backend de agentes Python.
*   **Isolamento no Python**: O framework de agentes autônomos (`tools.py`) passa a carregar as pautas de pauta e as referências históricas (`getEcosystemMemory`) exclusivamente da subcoleção `/tenants/{tenantId}/sessions`.

---

## 3. Matriz de Complexidade: V1 ➔ V2

| Funcionalidade | V1 (Atual) | V2 (Multi-Tenant) | Complexidade de Refatoração |
|---|---|---|---|
| **Autenticação** | Senha estática (`admin123`) compartilhada | Firebase Auth (Google Sign-In + Email/Senha) | **Média** (Substituir `AuthGate.tsx` por SDK de Auth Client) |
| **Pautas & Sessões** | `/csm_sessions/{sessionId}` global | `/tenants/{tenantId}/sessions/{sessionId}` | **Baixa** (Apenas atualizar caminhos de queries e rotas de APIs) |
| **Config. de Agentes**| `/agent_configurations/` global | `/tenants/{tenantId}/agent_configurations/` | **Baixa** |
| **API Keys** | Env vars / Secret Manager único | Firestore criptografado por Tenant | **Média** (Criar utilitário de cifra AES no Next.js) |
| **Fila Social (Repurpose)**| `/social_queue` único | `/tenants/{tenantId}/social_queue` | **Baixa** |

---

## 4. Plano de Ação Recomendado para V2

1. **Camada de Autenticação**:
   * Adicionar o Firebase Auth no frontend Next.js.
   * Modificar o middleware `/api/csm/*` para validar o token JWT e extrair o `tenantId`.
2. **Refatorar barramento de banco (Firebase Admin)**:
   * Atualizar todas as leituras e escritas do Firestore no Next.js e no Python para iniciarem sob o prefixo `/tenants/{tenantId}/`.
3. **Módulo de Criptografia de Chaves**:
   * Escrever um utilitário simples em `src/lib/crypto.ts` usando o módulo nativo Web Crypto API (Node/Edge compatível) para cifrar e decifrar chaves de API individuais usando uma chave de criptografia de ambiente.
4. **Isolamento de Domínio no Blog**:
   * O blog público precisará suportar subdomínios (ex: `cliente1.eozore.com/blog`) ou caminhos dedicados (ex: `eozore.com/t/{tenantId}/blog`) para renderizar os artigos do banco particionado daquele tenant.

---

### Perguntas e Decisões de Design para o Victor Zoré:
1. **Escolha de Identidade**: Você prefere usar o **Firebase Authentication** nativo (mais simples de integrar com o banco Firestore que já temos) ou **NextAuth.js** (melhor se formos plugar outras contas de mídias de forma integrada no futuro)?
2. **BYOK vs. Créditos Base**: Devemos forçar que o usuário obrigatoriamente coloque a `GEMINI_API_KEY` dele desde o primeiro login, ou forneceremos um trial gratuito (por ex, 5 gerações grátis) sob a sua conta base?

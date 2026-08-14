# 📐 Plano de Ação: Refatoração Preventiva para Futuro Multi-Tenant (Atrito Zero)

Este plano descreve como preparar a infraestrutura e o código atual do CSM Studio (Next.js e Python) para a futura transição multi-tenant, mantendo o funcionamento **100% monotenant e local** no seu portfólio no primeiro momento.

O objetivo é estruturar a base de código para que o salto para o SaaS V2 seja feito apenas alternando chaves de ambiente, sem precisar reescrever consultas, rotas de API ou lógicas de orquestração de IA.

---

## 1. Abstração dos Caminhos do Firestore (Path Resolvers)

Atualmente, o código do Next.js e do Python acessa coleções do Firestore usando caminhos estáticos ("hardcoded") espalhados em vários arquivos (ex: `db.collection('csm_sessions')`).

### Solução Preventiva:
Criar um arquivo centralizador de caminhos `src/lib/dbPaths.ts` no Next.js (e equivalente em Python `db_paths.py`). Toda a aplicação consumirá caminhos gerados por essas funções.

```typescript
// src/lib/dbPaths.ts
const CURRENT_TENANT_ID = process.env.NEXT_PUBLIC_TENANT_ID || null; // nulo na V1

export const dbPaths = {
  sessions: () => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/sessions` : `csm_sessions`,
    
  sessionDoc: (id: string) => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/sessions/${id}` : `csm_sessions/${id}`,
    
  articles: () => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/articles` : `articles`,
    
  articleDoc: (id: string) => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/articles/${id}` : `articles/${id}`,
    
  configDoc: (agentName: string) => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/agent_configurations/${agentName}` : `agent_configurations/${agentName}`,
    
  apiKeysDoc: () => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/api_keys/keys` : `agent_configurations/api_keys`,
    
  socialQueue: () => 
    CURRENT_TENANT_ID ? `tenants/${CURRENT_TENANT_ID}/social_queue` : `social_queue`,
};
```

*   **Vantagem**: Na V1, `NEXT_PUBLIC_TENANT_ID` é deixado em branco, e o sistema funciona exatamente como está hoje. Na V2, basta definir o `tenantId` da sessão logada no resolvedor e toda a persistência é isolada instantaneamente.

---

## 2. Unificação de Identidade Visual e Markdown (BYO-Brand)

O cliente precisará configurar a própria identidade visual (marca, cores do blog, cabeçalhos, etc.). 

### Solução Preventiva:
Extrair as configurações visuais do CSS hardcoded para um documento de preferências no Firestore (`agent_configurations/theme`).
*   No blog, carregamos essas variáveis de cor (ex: `--primary-color`, `--bg-color`) a partir de CSS Variables injetadas no HTML de forma dinâmica.
*   **Vantagem**: A V1 continua consumindo a identidade padrão do Victor Zoré, mas o sistema já estará pronto para renderizar marcas personalizadas por usuário.

---

## 3. Repasse de Contexto de Tenant para o Agente Python

O microserviço FastAPI (`agents/cmo_agent/`) precisa processar a geração de roteiros e posts utilizando o perfil de agentes e prompts customizados daquele tenant específico.

### Solução Preventiva:
*   Passar um cabeçalho customizado opcional `X-Tenant-ID` em todas as chamadas HTTP feitas do Next.js para o Python agent (`http://localhost:8090`).
*   No Python agent, se o cabeçalho `X-Tenant-ID` for enviado, ele busca os prompts do agente e as chaves de API da pasta do Tenant correspondente no Firestore. Se não for enviado, ele usa as tabelas globais da V1.

---

## 4. Resiliência de Processos (Cache & Checkpoint por Etapa)

Para evitar perda de progresso no meio de gerações longas (seja por timeouts de rede, estouro de cotas ou interrupções), estruturaremos um modelo de **Máquina de Estados de Transição Persistida** no Firestore da sessão.

### Solução Preventiva:
No campo `draft` da coleção de sessões, em vez de salvar apenas o `generatedContent` final, persistiremos um dicionário de checkpoints das fases do pipeline:

```typescript
interface GenerationCheckpoint {
  currentStage: 'idle' | 'researching' | 'writing' | 'coding' | 'done';
  stages: {
    research: {
      papers: Array<{ title: string, pdfUrl: string, summary: string }>;
      updatedAt: number;
    };
    writing: {
      outline: string[];
      rawDraft?: string;
      updatedAt: number;
    };
    coding: {
      generatedPlots: Array<{ code: string, imageUrl: string }>;
      updatedAt: number;
    };
  };
}
```

*   **Lógica de Execução**: Antes de disparar o agente de redação de IA, o sistema consulta se já existem `papers` catalogados no checkpoint daquela sessão. Se existirem, ele ignora a etapa de busca de papers no arXiv e passa diretamente o cache para o redator, economizando tempo e chamadas de API.

---

## 5. Telemetria de Custos e Tokens (Usage Tracking)

Para viabilizar a cobrança por uso e o monitoramento financeiro de cada cliente no SaaS V2, o sistema deve computar e registrar o custo de tokens gerados em cada chamada de IA.

### Solução Preventiva:
1. **Coleção de Uso**: Criar uma coleção Firestore `/tenants/{tenantId}/usage_logs` (global `usage_logs` na V1) onde registramos cada transação.
2. **Formato do Registro**:
   ```typescript
   interface UsageLog {
     timestamp: number;
     stage: 'article_generation' | 'youtube_script' | 'social_repurpose' | 'heygen_render';
     model: string; // ex: gemini-2.5-flash
     inputTokens: number;
     outputTokens: number;
     estimatedCostUsd: number;
     latencyMs: number;
   }
   ```
3. **Cálculo de Custos (Exemplo Gemini 2.5 Flash)**:
   * Entrada: `$0.075` por milhão de tokens.
   * Saída: `$0.30` por milhão de tokens.
   * *Formula*: `(inputTokens * 0.075 / 10^6) + (outputTokens * 0.30 / 10^6)`.

---

## 5.1. Log de Decisões de Infraestrutura e Dados

As seguintes decisões de escala e resiliência foram formalmente definidas para guiar a codificação com o menor atrito técnico de transição:

1. **Estratégia de GCS para Mídias (Decisão 1-A)**:
   * Em vez de salvar plots e imagens localmente, os assets temporários de cada sessão do usuário serão salvos no **Google Cloud Storage (GCS)** sob a chave `/tenants/{tenantId}/sessions/{sessionId}/plots/`.
   * **Custo**: Uma Lifecycle Policy de 30 dias será configurada no bucket para autolimpar arquivos de sessões antigas, mantendo os custos de armazenamento próximos de zero.
2. **Auditoria de Linha de Produção (Decisão 1-B)**:
   * Manteremos por padrão a gravação completa do estado dos checkpoints (papers, outlines brutos e revisões intermediárias) no Firestore local na V1 e no início da V2 para permitir auditoria total em caso de erros.
   * **Estratégia de Escala**: No futuro, se os documentos crescerem, as versões de auditoria antigas serão serializadas em arquivos `.json` e arquivadas no GCS, deixando apenas os ponteiros no Firestore.
3. **YouTube & OAuth Simplificados (Decisão 1-D)**:
   * A publicação automática via fluxos complexos de OAuth 2.0 (Google Tokens) por cliente será simplificada em prol da robustez da geração e da partição de dados do SaaS em suas primeiras fases.

---

## 6. Cronograma de Implementação (Zero Atrito)

```
[Mapeamento de Paths] ──► [Checkpoint & Cache] ──► [Telemetria & Custos] ──► [Repasse X-Tenant-ID]
       (Fase 1)                  (Fase 2)                  (Fase 3)                 (Fase 4)
```

1.  **Fase 1 (Next.js)**: Substituir acessos diretos do Firestore por `dbPaths`.
2.  **Fase 2 (Resiliência)**: Implementar checkpoints no `draft` da sessão do Firestore para caching de papers e rascunhos.
3.  **Fase 3 (Telemetria)**: Criar o helper de log de uso no Vertex AI proxy no Next.js para rastrear input/output tokens e computar custos.
4.  **Fase 4 (Python Agent)**: Refatorar `tools.py` para receber a chave do HeyGen e do Gemini com base no Tenant.
5.  **Fase 5 (Verificação)**: Testar localmente no portfólio. Nenhuma tela ou comportamento deve ser alterado visualmente para o Victor Zoré.

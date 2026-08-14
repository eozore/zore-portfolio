---
trigger: model_decision
description: Decisões de Arquitetura Técnica Imutáveis — Guia para agentes IA no projeto
---

# Regra: Respeitar as Decisões de Arquitetura do Projeto

Antes de propor qualquer mudança técnica, o agente deve verificar se ela viola alguma das decisões abaixo. Estas são decisões **imutáveis** que não devem ser revertidas sem aprovação explícita do Victor Zore.

---

## 1. Vertex AI: REST direto + Firebase Admin ADC (NÃO usar SDKs pesados)

**Decisão:** O acesso ao Vertex AI (Gemini) é feito via chamada REST direta com Bearer token obtido do Firebase Admin SDK (`credential.getAccessToken()`).

**Proibido propor:**
- Instalar `@google-cloud/vertexai` ou `google-cloud-aiplatform` no Next.js
- Usar API Keys hardcoded no código
- Inicializar um segundo mecanismo de autenticação paralelo ao Firebase Admin

**Por quê:** Firebase Admin SDK já tem ADC. Duplicar mecanismos de autenticação cria debt técnico e risco de segurança.

---

## 2. Firebase Admin SDK APENAS no servidor (Route Handlers do Next.js)

**Decisão:** O Firebase Admin SDK é importado SOMENTE em arquivos dentro de `src/app/api/` (Route Handlers) ou `src/lib/`.

**Proibido propor:**
- Importar `firebase-admin` em arquivos de componentes React (`src/components/`)
- Usar o Firebase Client SDK (`firebase/app`, `firebase/firestore`) para operações de leitura/escrita no servidor

**Por quê:** O Admin SDK expõe o service account. Se importado no lado cliente (bundle), vazaria credenciais privilegiadas.

---

## 3. CSS Modules para estilização (NÃO TailwindCSS)

**Decisão:** Estilização feita exclusivamente com CSS Modules (`.module.css`) por componente.

**Proibido propor:**
- Instalar ou configurar TailwindCSS neste projeto
- Usar classes utilitárias inline como `className="flex items-center p-4"`
- Usar styled-components ou emotion

**Por quê:** CSS Modules oferecem escopo automático, sem conflitos globais e não dependem de um compilador separado.

---

## 4. Agentes Python AGY/ADK são microserviços SEPARADOS do Next.js

**Decisão:** A lógica de agentes Python (AGY SDK, ADK) deve viver em **serviços separados** (Cloud Run Jobs ou Cloud Run Services), não embutida no runtime do Next.js.

**Proibido propor:**
- Criar arquivos `.py` dentro do diretório `apps/web/`
- Usar `child_process` ou `exec` para chamar scripts Python de dentro do Next.js

**Por quê:** O runtime do Next.js (Node.js) não é o ambiente correto para processos Python de longa duração. A comunicação entre Next.js e agentes Python deve ser via Pub/Sub, HTTP ou Firestore.

---

## 5. Next.js App Router (NÃO Pages Router)

**Decisão:** O projeto usa exclusivamente o App Router (`src/app/`).

**Proibido propor:**
- Criar arquivos em `src/pages/`
- Usar `getServerSideProps`, `getStaticProps` ou `getInitialProps`
- Criar API routes no padrão Pages Router (`pages/api/`)

---

## 6. Variáveis de Ambiente: Secret Manager em Produção

**Decisão:** Segredos de produção são injetados via Google Cloud Secret Manager, não via arquivo `.env` commitado.

**Proibido propor:**
- Adicionar segredos reais ao arquivo `.env` e commitar no repositório
- Hardcodar project IDs ou tokens no código fonte

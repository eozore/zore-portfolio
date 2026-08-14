# Referência Técnica: Google Antigravity SDK (AGY)

> Fonte: Documentação oficial do plugin `google-antigravity` instalado neste workspace.
> Última Revisão: Junho 2026. Leia este documento antes de qualquer tarefa de construção de agentes.

---

## 1. Arquitetura Central: Agent, Conversation, Connection

O AGY SDK é construído sobre **3 pilares**:

| Pilar | Responsabilidade |
|---|---|
| **`Agent`** | Ponto de entrada. Gerencia configuração (modelo, tools, policies, hooks), lifecycle da sessão e orquestra triggers. |
| **`Conversation`** | Representa uma sessão stateful. Acumula histórico, gerencia compactação de contexto e expõe o método `chat()` com streaming. |
| **`Connection`** | Interface abstrata de transporte (local, cloud). Desacopla a API de alto nível do backend específico. |

### Fluxo de Dados
```
AgentConfig → Agent → Conversation (state + history) → Connection (transport)
```

---

## 2. Configuração Básica

```python
from google.antigravity import Agent, LocalAgentConfig

config = LocalAgentConfig(
    system_instructions="Você é um estrategista sênior de conteúdo.",
)

async with Agent(config) as agent:
    response = await agent.chat("Olá! Que tópico devemos cobrir esta semana?")
    print(await response.text())
```

> **REGRA CRÍTICA:** Nunca assuma identificadores de modelos. Deixe o modelo padrão (`gemini-3.5-flash`) ou consulte https://ai.google.dev/gemini-api/docs/models/gemini antes de setar explicitamente.

---

## 3. Persistência de Conversação (Memória de Curto Prazo)

Para retomar uma sessão após reinicialização (curto prazo), use `save_dir` + `conversation_id`:

```python
import tempfile
from google.antigravity import Agent, LocalAgentConfig

save_dir = tempfile.mkdtemp()

# Sessão 1
config1 = LocalAgentConfig(save_dir=save_dir)
async with Agent(config1) as agent:
    await agent.chat("Lembre: o artigo desta semana será sobre LoRA.")
    conv_id = agent.conversation_id  # <- salve este ID

# Sessão 2 (retomando contexto)
config2 = LocalAgentConfig(conversation_id=conv_id, save_dir=save_dir)
async with Agent(config2) as agent:
    response = await agent.chat("Qual era o tema do artigo?")
    # Agente lembrará de LoRA
```

> **Nota:** `save_dir` persiste o histórico de conversação. `app_data_dir` controla onde artefatos (`task.md`, mídia) são gravados.

---

## 4. Sub-Agentes (Orquestração Multi-Agente)

Sub-agentes são habilitados por padrão via `CapabilitiesConfig`. Um agente principal pode delegar subtarefas para agentes especializados:

```python
from google.antigravity import Agent, LocalAgentConfig, types

config = LocalAgentConfig(
    capabilities=types.CapabilitiesConfig(enable_subagents=True),
    system_instructions="Você é o CMO orquestrador. Delegue redação técnica ao sub-agente especializado.",
)

async with Agent(config) as agent:
    response = await agent.chat(
        "Use um sub-agente para redigir o esboço matemático do artigo sobre LoRA."
    )
    print(await response.text())
```

---

## 5. Hooks do Ciclo de Vida (Interceptação e Rastreamento)

Hooks permitem interceptar cada etapa do agente para auditoria, bloqueio ou customização:

```python
from google.antigravity import types
from google.antigravity.hooks import hooks

# Executa ANTES de cada turno
@hooks.pre_turn
async def pre_turn(data: str) -> types.HookResult:
    print(f"[PRE-TURN] Prompt recebido: {data[:50]}...")
    return types.HookResult(allow=True)

# Executa APÓS cada turno
@hooks.post_turn
async def post_turn(data: str):
    print(f"[POST-TURN] Resposta gerada: {data[:50]}...")

# Executa APÓS cada tool call (útil para auditoria de chamadas ao Firestore/Vertex)
@hooks.post_tool_call
async def audit_tool(data):
    print(f"[AUDIT] Tool executado: {data}")

# Registro dos hooks na config
config = LocalAgentConfig(hooks=[pre_turn, post_turn, audit_tool])
```

---

## 6. Triggers Periódicos e por Eventos (Agentes Proativos)

Triggers permitem que agentes acordem periodicamente ou reajam a eventos externos:

```python
from google.antigravity import Agent, LocalAgentConfig
from google.antigravity.triggers import every, on_file_change, TriggerContext
import asyncio

# Trigger periódico (a cada 60 segundos)
async def check_new_papers(ctx: TriggerContext):
    # Ex: verificar novos papers no arXiv e enviar ao agente para análise
    await ctx.send("Há novos papers de GenAI publicados hoje no arXiv? Sugira 2 temas de artigo.")

timer_trigger = every(60, check_new_papers)

# Trigger por mudança de arquivo (ex: novo rascunho salvo)
async def on_draft_saved(ctx: TriggerContext, changes):
    for change in changes:
        await ctx.send(f"Novo rascunho detectado em {change.path}. Gere sugestões de melhoria.")

file_trigger = on_file_change("/path/to/drafts", on_draft_saved)

config = LocalAgentConfig(
    system_instructions="Você é o CMO AI de plantão.",
    triggers=[timer_trigger, file_trigger],
)
```

---

## 7. Integração MCP (Model Context Protocol)

O AGY suporta dois modos de conexão com servidores MCP:

```python
from google.antigravity import Agent, LocalAgentConfig, types

# Modo Stdio (processo local gerenciado pelo SDK)
mcp_servers = [
    types.McpStdioServer(command="python3", args=["mcp_firestore_server.py"]),
]

# Modo SSE (servidor remoto via Server-Sent Events)
mcp_servers_remote = [
    types.McpSseServer(
        url="https://mcp.eozore.com/sse",
        headers={"Authorization": "Bearer <token>"},
    ),
]

config = LocalAgentConfig(mcp_servers=mcp_servers)
```

> **Permissões:** MCP tools são permitidas pela política padrão `confirm_run_command()`. Em setup deny-by-default, liste explicitamente: `policy.allow("nome_da_ferramenta")`.

---

## 8. Políticas de Segurança

| Política | Comportamento | Uso |
|---|---|---|
| `policy.confirm_run_command()` | **Padrão.** Bloqueia `run_command`, permite todo o resto. | Desenvolvimento |
| `policy.allow_all()` | Permite absolutamente tudo | Dev local sem restrição |
| `policy.deny_all()` | Nega tudo; requer lista explícita de allows | Produção hardened |
| `policy.workspace_only(dirs)` | Restringe file tools ao workspace configurado | Isolamento de código |

```python
# Produção recomendada: deny-by-default + allows seletivos
from google.antigravity.hooks import policy

policies = [
    policy.deny_all(),
    policy.allow("view_file"),
    policy.allow("firestore_read"),
    policy.ask_user("run_command"),
]
```

---

## 9. Observabilidade: Rastreamento de Tokens e Custos

```python
async with Agent(config) as agent:
    response = await agent.chat("Analise o histórico editorial.")
    usage = agent.conversation.total_usage
    print(f"Prompt tokens: {usage.prompt_token_count}")
    print(f"Thinking tokens: {usage.thoughts_token_count}")  # ⚠️ Pode ser alto
    print(f"Total tokens: {usage.total_token_count}")
```

> ⚠️ `thoughts_token_count` (tokens de raciocínio interno) pode aumentar significativamente o custo em modelos com Extended Thinking habilitado.

---

## 10. Personas e System Instructions

```python
from google.antigravity.types import TemplatedSystemInstructions

# Recomendado: APPEND à instrução padrão (preserva safety guidelines)
identity = "Você é o CMO AI da plataforma éozoré, especialista sênior em conteúdo técnico educacional."
config = LocalAgentConfig(
    system_instructions=TemplatedSystemInstructions(identity=identity)
)

# Avançado: SOBRESCREVER completamente (usar com cautela — perde safety policies)
from google.antigravity.types import CustomSystemInstructions
config = LocalAgentConfig(
    system_instructions=CustomSystemInstructions(text="Instrução totalmente customizada.")
)
```

---

## Referências Externas
- Documentação Oficial ADK: https://google.github.io/adk-docs/
- Modelos Gemini válidos: https://ai.google.dev/gemini-api/docs/models/gemini
- Plugin local instalado: `/Users/victorzore/.gemini/config/plugins/google-antigravity-sdk/`

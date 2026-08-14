# Scalability Design — Bolt 0+1

---

## Design para Volume Atual (uso solo)

Todos os serviços configurados com `min-instances=0` — zero custo idle.

| Serviço | Scaling | Justificativa |
|---|---|---|
| `heygen-callback` | 0→1 | Um callback por vez — sem concorrência |
| `publisher-immediate` | 0→2 | Raramente chamado manualmente |
| Cloud Run Jobs | N/A | Executados sequencialmente por projeto |

## Path para Escalar (futuro — fora do escopo)

Quando houver múltiplos criadores:
1. Pub/Sub ordering keys por `project_id` — garante processamento sequencial por projeto mas paralelo entre projetos
2. `heygen-callback` max-instances=10 — suporta callbacks simultâneos de diferentes projetos
3. Firestore transactions para `cost_breakdown` — evita race conditions em atualizações de custo

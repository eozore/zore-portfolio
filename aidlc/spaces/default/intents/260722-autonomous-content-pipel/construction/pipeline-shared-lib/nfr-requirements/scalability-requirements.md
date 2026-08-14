# Scalability Requirements — Bolt 0 + Bolt 1

> Referências: [requirements.md](../../inception/requirements-analysis/requirements.md)

---

## Volume Alvo (uso solo — Victor Zore)

| Métrica | Target | Observação |
|---|---|---|
| Pacotes/semana | 3 vídeos × 5-6 min | Conforme decisão de intent-capture |
| Concorrência de pipelines simultâneas | 1 (sequential, não paralelas) | Uso solo — sem necessidade de paralelismo |
| Pacotes/mês | ~12-15 | Bolt Plan batch semanal |
| Crescimento esperado | Nenhum até produto SaaS | Multi-tenancy fora do escopo desta entrega |

## Limites de Escala dos Componentes

| Componente | Min instances | Max instances | Justificativa |
|---|---|---|---|
| `heygen-callback` | 0 | 1 | Volume baixo, sem concorrência de callbacks |
| `publisher-immediate` | 0 | 2 | "Publicar Agora" pode ser chamado raramente |
| Cloud Run Jobs | N/A | N/A | Jobs são executados um por vez por projeto |

## Quando Revisar

Escalar para múltiplos criadores (SaaS) requer:
1. Multi-tenancy de Firestore (`tenants/{id}/content_projects`)
2. Pub/Sub com ordering keys por projeto
3. Max instances > 1 para heygen-callback

Tudo fora do escopo desta entrega (documentado em `scope-document.md` como OUT).

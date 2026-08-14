# Security Test Instructions — Bolt 0 + Bolt 1

## Verificações Aplicadas

| Controle | Verificação | Status |
|---|---|---|
| SEC-01: Sem secrets no código | `grep -r "sk_\|GOCSPX\|hg_" agents/pipeline/` → 0 matches | ✅ |
| SEC-03: Webhook autenticado | Test: token inválido → 401 (ver test_heygen_callback.py) | Pendente (Bolt 1) |
| SEC-07: Sem log de secrets | `get_secret()` não loga o retorno | ✅ revisado no código |

## Scan de Secrets (local)

```bash
grep -r "sk_3f\|GOCSPX\|hg_\|1042120168838" agents/pipeline/ apps/web/src/ --include="*.py" --include="*.ts"
# Deve retornar 0 matches
```

#!/usr/bin/env python3
"""
agents/pipeline/scripts/create_tenant.py
=========================================
Cria (ou gira a chave de) um tenant em `tenants/{tenant_id}` no Firestore.

O tenant "default" NUNCA precisa passar por aqui — ele é o operador único de
hoje e não exige chave nenhuma (ver agents/pipeline/shared/tenancy.py). Este
script é para o dia em que um SEGUNDO tenant existir.

Uso:
    python create_tenant.py acme --name "Acme Inc" --monthly-budget-brl 500
    python create_tenant.py acme --rotate-key         # gira a chave de um tenant existente
    python create_tenant.py acme --suspend            # kill switch: bloqueia sem apagar dados

A chave gerada é mostrada UMA VEZ e nunca fica salva em lugar nenhum —
só o hash HMAC vai para o Firestore. Perdeu a chave? Rode --rotate-key.

Pré-requisito: TENANT_KEY_PEPPER no ambiente, ou acesso ao secret
`tenant-key-pepper` no Secret Manager do projeto (lido automaticamente).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from google.cloud import firestore  # noqa: E402

from shared.tenancy import (  # noqa: E402
    COLLECTION_TENANTS,
    DEFAULT_TENANT_ID,
    generate_tenant_key,
    hash_tenant_key,
)


def _ensure_pepper(project_id: str) -> None:
    if os.environ.get("TENANT_KEY_PEPPER", "").strip():
        return
    try:
        from shared.pubsub_client import get_secret
        os.environ["TENANT_KEY_PEPPER"] = get_secret("tenant-key-pepper", project_id)
    except Exception as exc:
        print(
            f"❌ TENANT_KEY_PEPPER não está no ambiente e não consegui lê-lo do "
            f"Secret Manager ({exc}).\n"
            f"   Rode: export TENANT_KEY_PEPPER=$(gcloud secrets versions access "
            f"latest --secret=tenant-key-pepper)",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant_id", help="ID do tenant (slug, ex: 'acme')")
    parser.add_argument("--name", default=None, help="Nome de exibição")
    parser.add_argument("--monthly-budget-brl", type=float, default=None,
                        help="Teto de gasto mensal em BRL (omitir = sem teto)")
    parser.add_argument("--project", default=os.environ.get("GCP_PROJECT_ID", "vazfy-417019"))
    parser.add_argument("--rotate-key", action="store_true",
                        help="Gera uma chave nova para um tenant já existente")
    parser.add_argument("--suspend", action="store_true",
                        help="Marca status=suspended — bloqueia sem apagar nada")
    parser.add_argument("--activate", action="store_true", help="Marca status=active")
    args = parser.parse_args()

    if args.tenant_id == DEFAULT_TENANT_ID:
        print(f"❌ '{DEFAULT_TENANT_ID}' é o tenant implícito e não usa este fluxo.")
        sys.exit(1)

    db = firestore.Client(project=args.project)
    ref = db.collection(COLLECTION_TENANTS).document(args.tenant_id)
    snap = ref.get()

    if args.suspend or args.activate:
        if not snap.exists:
            print(f"❌ Tenant '{args.tenant_id}' não existe.")
            sys.exit(1)
        new_status = "suspended" if args.suspend else "active"
        ref.set({"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}, merge=True)
        print(f"✅ Tenant '{args.tenant_id}' → status={new_status}")
        return

    if snap.exists and not args.rotate_key:
        print(f"❌ Tenant '{args.tenant_id}' já existe. Use --rotate-key para gerar chave nova.")
        sys.exit(1)

    _ensure_pepper(args.project)

    raw_key   = generate_tenant_key()
    key_hash  = hash_tenant_key(args.tenant_id, raw_key)
    now       = datetime.now(timezone.utc).isoformat()
    existing  = snap.to_dict() if snap.exists else {}

    doc = {
        "name":       args.name or existing.get("name") or args.tenant_id,
        "status":     existing.get("status", "active"),
        "key_hash":   key_hash,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    ref.set(doc, merge=True)

    if args.monthly_budget_brl is not None:
        # Mesmo doc que a pipeline já usa para cost_limit/exchange_rate —
        # orçamento mensal é config de custo, não identidade.
        db.collection("pipeline_config").document(args.tenant_id).set(
            {"monthly_budget_brl": args.monthly_budget_brl}, merge=True
        )

    action = "Chave girada" if args.rotate_key else "Tenant criado"
    print(f"✅ {action}: {args.tenant_id} ({doc['name']})")
    print(f"   Orçamento mensal: {args.monthly_budget_brl if args.monthly_budget_brl is not None else 'sem teto'} BRL")
    print()
    print("   Chave (mostrada só agora, não fica salva em lugar nenhum):")
    print(f"   {raw_key}")
    print()
    print("   Uso: header X-Tenant-ID + X-Tenant-Key nas chamadas ao cmo-agent e ao Next.js.")


if __name__ == "__main__":
    main()

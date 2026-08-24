"""
agents/pipeline/shared/tenancy.py
==================================
Identidade de tenant verificada — o que faltava para o `tenant_id` que já
circula pela pipeline (Firestore em `tenants/{id}/...`, `TENANT_ID` env var,
header `X-Tenant-ID`) significar alguma coisa.

Hoje, `tenant_id` é aceito de qualquer chamador sem checagem nenhuma: qualquer
requisição autenticada pelo segredo único do CSM pode se declarar dono de
qualquer tenant só passando o header. Não é um problema explorável enquanto só
existe um tenant ("default"), mas deixa de ser inofensivo no dia em que um
segundo tenant existir — e é exatamente esse dia que este módulo prepara, sem
mexer em nada do que já funciona hoje.

Regra:
  - tenant_id ausente ou "default" → tenant implícito único, SEM chave exigida.
    É o comportamento atual, preservado byte a byte.
  - qualquer outro tenant_id → precisa de uma chave válida (X-Tenant-Key),
    verificada por HMAC contra o hash salvo em `tenants/{id}.key_hash`.
    Sem isso, ou com tenant status != "active", a requisição é rejeitada.

Este módulo cobre IDENTIDADE. Orçamento mensal (quanto o tenant já gastou em
HeyGen/ElevenLabs este mês) é responsabilidade de cost_tracker.py — as duas
coisas são independentes: um tenant pode estar autenticado e ainda assim
bloqueado por orçamento.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Optional

from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)

COLLECTION_TENANTS = "tenants"
DEFAULT_TENANT_ID = "default"

# Pepper do servidor para o HMAC da chave de tenant — nunca a chave em si.
# Mesma família do CSM_AUTH_SECRET (apps/web/src/lib/csmAuth.ts): um segredo
# guardado só no backend, comparado por HMAC, nunca reversível.
_PEPPER_ENV = "TENANT_KEY_PEPPER"


class TenantAuthError(Exception):
    """Tenant não encontrado, chave inválida, ou tenant suspenso."""


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    name: str
    status: str

    @property
    def is_default(self) -> bool:
        return self.tenant_id == DEFAULT_TENANT_ID


def _pepper() -> str:
    value = os.environ.get(_PEPPER_ENV, "").strip()
    if not value:
        # Falha alto em vez de silenciosamente aceitar qualquer chave — um
        # pepper vazio tornaria hash_tenant_key determinístico e adivinhável.
        raise RuntimeError(
            f"{_PEPPER_ENV} não configurado. Necessário para verificar chaves "
            "de tenant que não sejam o tenant default."
        )
    return value


def hash_tenant_key(tenant_id: str, raw_key: str) -> str:
    """
    HMAC-SHA256 da chave, salgado pelo tenant_id — o mesmo texto de chave gera
    hashes diferentes por tenant, então vazar o hash de um tenant não ajuda a
    forjar a chave de outro.
    """
    msg = f"{tenant_id}:{raw_key}".encode("utf-8")
    return hmac.new(_pepper().encode("utf-8"), msg, hashlib.sha256).hexdigest()


def generate_tenant_key() -> str:
    """Chave aleatória para um novo tenant — mostrada UMA vez no bootstrap."""
    return secrets.token_urlsafe(32)


async def resolve_tenant(
    db: AsyncClient,
    tenant_id: Optional[str],
    tenant_key: Optional[str],
) -> TenantContext:
    """
    Resolve e verifica a identidade do tenant para uma requisição.

    Raises:
        TenantAuthError: tenant_id != default sem chave válida, tenant
            desconhecido, ou tenant com status != "active".
    """
    tid = (tenant_id or "").strip() or DEFAULT_TENANT_ID

    if tid == DEFAULT_TENANT_ID:
        # Comportamento atual, sem exigir nada novo: é o único operador de
        # hoje, e forçar uma chave aqui quebraria toda chamada existente.
        return TenantContext(tenant_id=DEFAULT_TENANT_ID, name="éozoré", status="active")

    doc = await db.collection(COLLECTION_TENANTS).document(tid).get()
    if not doc.exists:
        raise TenantAuthError(f"Tenant '{tid}' não existe")

    data = doc.to_dict() or {}
    if data.get("status") != "active":
        raise TenantAuthError(f"Tenant '{tid}' não está ativo (status={data.get('status')})")

    stored_hash = data.get("key_hash", "")
    if not tenant_key or not stored_hash:
        raise TenantAuthError(f"Tenant '{tid}' exige X-Tenant-Key")

    presented_hash = hash_tenant_key(tid, tenant_key)
    # Comparação em tempo constante — hmac.compare_digest, não `==`, para não
    # vazar por timing quantos bytes do hash bateram.
    if not hmac.compare_digest(presented_hash, stored_hash):
        raise TenantAuthError(f"Chave inválida para tenant '{tid}'")

    return TenantContext(
        tenant_id=tid,
        name=data.get("name", tid),
        status=data["status"],
    )

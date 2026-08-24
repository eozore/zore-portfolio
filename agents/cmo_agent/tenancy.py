# -*- coding: utf-8 -*-
"""
agents/cmo_agent/tenancy.py
============================
Identidade de tenant verificada para o serviço FastAPI do CMO Agent.

Espelha `agents/pipeline/shared/tenancy.py` — mesmo schema Firestore
(`tenants/{id}`, mesmo HMAC salgado por tenant), mesma regra:

  - tenant_id ausente ou "default" → tenant único implícito (o operador de
    hoje), SEM chave exigida. Comportamento atual, preservado.
  - qualquer outro tenant_id → precisa de X-Tenant-Key válida, verificada
    contra `tenants/{id}.key_hash`.

Por que existe uma cópia em vez de importar o módulo da pipeline: os dois
serviços têm build contexts de Docker separados (`agents/cmo_agent/` e
`agents/pipeline/`) — este serviço não tem acesso aos arquivos do outro no
momento do build. Os dois apontam para o MESMO Firestore, então um único
registro `tenants/{id}` serve de identidade para ambos; só o código de
verificação é duplicado, não o dado.

Diferença do módulo da pipeline: aqui o cliente Firestore (`db`, de
firebase_admin) é SÍNCRONO, então a leitura roda em thread separada
(`asyncio.to_thread`) para não bloquear o event loop do FastAPI.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("cmo_agent.tenancy")

COLLECTION_TENANTS = "tenants"
DEFAULT_TENANT_ID = "default"
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
        raise RuntimeError(
            f"{_PEPPER_ENV} não configurado. Necessário para verificar chaves "
            "de tenant que não sejam o tenant default."
        )
    return value


def hash_tenant_key(tenant_id: str, raw_key: str) -> str:
    """HMAC-SHA256 salgado pelo tenant_id. Idêntico ao da pipeline —
    o hash gerado aqui e lá para o mesmo par (tenant_id, chave) é o mesmo,
    porque ambos leem o mesmo TENANT_KEY_PEPPER do Secret Manager."""
    msg = f"{tenant_id}:{raw_key}".encode("utf-8")
    return hmac.new(_pepper().encode("utf-8"), msg, hashlib.sha256).hexdigest()


def generate_tenant_key() -> str:
    return secrets.token_urlsafe(32)


def resolve_tenant_sync(db, tenant_id: Optional[str], tenant_key: Optional[str]) -> TenantContext:
    """
    Versão síncrona de resolve_tenant — chame via `asyncio.to_thread` a partir
    de código async (é o que o middleware em agent.py faz).

    Raises:
        TenantAuthError: tenant_id != default sem chave válida, tenant
            desconhecido, ou tenant com status != "active".
    """
    tid = (tenant_id or "").strip() or DEFAULT_TENANT_ID

    if tid == DEFAULT_TENANT_ID:
        return TenantContext(tenant_id=DEFAULT_TENANT_ID, name="éozoré", status="active")

    # Sem Firestore não há como verificar a chave. FALHA FECHADO: recusar é a
    # única resposta segura — deixar passar transformaria uma indisponibilidade
    # do banco num bypass de autenticação, e um AttributeError aqui virava um
    # 500 opaco que não distinguia "tenant barrado" de "serviço quebrado".
    if db is None:
        raise TenantAuthError(
            "Verificação de tenant indisponível (Firestore não inicializado)"
        )

    doc = db.collection(COLLECTION_TENANTS).document(tid).get()
    if not doc.exists:
        raise TenantAuthError(f"Tenant '{tid}' não existe")

    data = doc.to_dict() or {}
    if data.get("status") != "active":
        raise TenantAuthError(f"Tenant '{tid}' não está ativo (status={data.get('status')})")

    stored_hash = data.get("key_hash", "")
    if not tenant_key or not stored_hash:
        raise TenantAuthError(f"Tenant '{tid}' exige X-Tenant-Key")

    if not hmac.compare_digest(hash_tenant_key(tid, tenant_key), stored_hash):
        raise TenantAuthError(f"Chave inválida para tenant '{tid}'")

    return TenantContext(tenant_id=tid, name=data.get("name", tid), status=data["status"])

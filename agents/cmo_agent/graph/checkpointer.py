# -*- coding: utf-8 -*-
"""
checkpointer.py — Persistência do estado do grafo em Firestore.

O LangGraph traz savers para memória, SQLite e Postgres. Nenhum serve aqui: o
CSM roda em Cloud Run (instância recicla a qualquer momento, memória some) e
guarda tudo em Firestore. Um saver de memória perderia o pacote inteiro na
primeira reciclagem; subir um Postgres só para isto seria uma peça de infra
nova para manter.

E a pausa que precisa sobreviver é longa: o gate de aprovação espera o dono do
canal ler o artigo e assistir ao vídeo. Isso leva HORAS ou DIAS, o navegador
fecha, a instância é reciclada várias vezes no meio. O checkpoint tem que
estar num lugar durável e compartilhado — que é exatamente o Firestore que já
guarda o resto da sessão.

Layout:
    tenants/{tenant}/graph_threads/{thread_id}
        └── checkpoints/{checkpoint_id}   → estado serializado + metadata
        └── writes/{task_id}__{idx}       → escritas pendentes de um passo
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Iterator, Optional, Sequence

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

logger = logging.getLogger("cmo_agent.graph.checkpointer")


class FirestoreCheckpointSaver(BaseCheckpointSaver):
    """
    Saver durável em Firestore.

    A serialização usa o JsonPlusSerializer do próprio LangGraph, que sabe
    lidar com os tipos que aparecem no estado (datetime, Pydantic, mensagens).
    O payload vai como bytes num campo blob — não como mapa — porque um
    documento Firestore não aceita chaves com ponto nem aninhamento profundo
    arbitrário, e o estado do grafo tem os dois.
    """

    def __init__(self, db, tenant_id: Optional[str] = None) -> None:
        super().__init__()
        self._db = db
        self._tenant_id = tenant_id
        self.serde = JsonPlusSerializer()

    # ── Caminhos ──────────────────────────────────────────────────────────────

    def _thread_ref(self, thread_id: str):
        base = (
            f"tenants/{self._tenant_id}/graph_threads"
            if self._tenant_id else "graph_threads"
        )
        return self._db.collection(base).document(thread_id)

    def _checkpoints(self, thread_id: str):
        return self._thread_ref(thread_id).collection("checkpoints")

    def _writes(self, thread_id: str):
        return self._thread_ref(thread_id).collection("writes")

    @staticmethod
    def _thread_id(config: dict) -> str:
        tid = (config.get("configurable") or {}).get("thread_id")
        if not tid:
            raise ValueError("config.configurable.thread_id é obrigatório")
        return str(tid)

    # ── Leitura ───────────────────────────────────────────────────────────────

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        thread_id = self._thread_id(config)
        cp_id = (config.get("configurable") or {}).get("checkpoint_id")

        if cp_id:
            snap = self._checkpoints(thread_id).document(str(cp_id)).get()
            if not snap.exists:
                return None
            doc = snap.to_dict() or {}
        else:
            # `step` decrescente em vez de checkpoint_id: os ids são UUIDs e
            # não ordenam cronologicamente.
            docs = list(
                self._checkpoints(thread_id)
                .order_by("step", direction="DESCENDING")
                .limit(1)
                .stream()
            )
            if not docs:
                return None
            doc = docs[0].to_dict() or {}

        return self._to_tuple(thread_id, doc)

    def _to_tuple(self, thread_id: str, doc: dict) -> CheckpointTuple:
        checkpoint = self.serde.loads_typed((doc["type"], doc["checkpoint"]))
        metadata   = self.serde.loads_typed((doc["type"], doc["metadata"]))
        cp_id      = doc["checkpoint_id"]

        pending: list[tuple[str, Any]] = []
        for w in self._writes(thread_id).where("checkpoint_id", "==", cp_id).stream():
            wd = w.to_dict() or {}
            pending.append((wd["channel"], self.serde.loads_typed((wd["type"], wd["value"]))))

        parent_config = None
        if doc.get("parent_checkpoint_id"):
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": doc["parent_checkpoint_id"],
                }
            }

        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id}},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=[(w[0], w[0], w[1]) for w in pending] if pending else None,
        )

    def list(
        self,
        config: Optional[dict],
        *,
        filter: Optional[dict] = None,
        before: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        if not config:
            return
        thread_id = self._thread_id(config)
        query = self._checkpoints(thread_id).order_by("step", direction="DESCENDING")
        if limit:
            query = query.limit(limit)
        for snap in query.stream():
            yield self._to_tuple(thread_id, snap.to_dict() or {})

    # ── Escrita ───────────────────────────────────────────────────────────────

    def put(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict:
        thread_id = self._thread_id(config)
        cp_id     = str(checkpoint["id"])
        cp_type, cp_bytes   = self.serde.dumps_typed(checkpoint)
        _,       meta_bytes = self.serde.dumps_typed(metadata)

        self._checkpoints(thread_id).document(cp_id).set({
            "checkpoint_id":        cp_id,
            "parent_checkpoint_id": (config.get("configurable") or {}).get("checkpoint_id"),
            "type":                 cp_type,
            "checkpoint":           cp_bytes,
            "metadata":             meta_bytes,
            # Passo do grafo — é por ele que ordenamos, não pelo id (UUID).
            "step":                 int(metadata.get("step", -1)),
            "ts":                   checkpoint.get("ts"),
        })
        return {"configurable": {"thread_id": thread_id, "checkpoint_id": cp_id}}

    def put_writes(
        self,
        config: dict,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = self._thread_id(config)
        cp_id     = (config.get("configurable") or {}).get("checkpoint_id")
        batch     = self._db.batch()
        for idx, (channel, value) in enumerate(writes):
            vtype, vbytes = self.serde.dumps_typed(value)
            batch.set(
                self._writes(thread_id).document(f"{task_id}__{idx}"),
                {
                    "checkpoint_id": cp_id,
                    "task_id": task_id,
                    "idx": idx,
                    "channel": channel,
                    "type": vtype,
                    "value": vbytes,
                },
            )
        batch.commit()

    def delete_thread(self, thread_id: str) -> None:
        for col in (self._checkpoints(thread_id), self._writes(thread_id)):
            for snap in col.stream():
                snap.reference.delete()
        self._thread_ref(thread_id).delete()

    # ── Interface async ───────────────────────────────────────────────────────
    # O cliente firebase_admin é síncrono; rodar em thread evita travar o event
    # loop do FastAPI durante a escrita do checkpoint.

    async def aget_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        import asyncio
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(
        self,
        config: Optional[dict],
        *,
        filter: Optional[dict] = None,
        before: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        import asyncio
        items = await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )
        for item in items:
            yield item

    async def aput(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict:
        import asyncio
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: dict,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        import asyncio
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        import asyncio
        await asyncio.to_thread(self.delete_thread, thread_id)

"""Firestore em memória, suficiente para exercitar o checkpointer do grafo."""
from __future__ import annotations
from typing import Any, Optional


class _Snap:
    def __init__(self, doc_id: str, data: Optional[dict], ref=None):
        self.id, self._data, self.exists, self.reference = doc_id, data, data is not None, ref
    def to_dict(self): return dict(self._data) if self._data else None


class _Doc:
    def __init__(self, store: dict, path: str):
        self._store, self._path = store, path
    def set(self, data: dict, merge: bool = False):
        cur = self._store.get(self._path, {}) if merge else {}
        cur.update(data); self._store[self._path] = cur
    def update(self, data: dict):
        cur = self._store.setdefault(self._path, {})
        for k, v in data.items():
            if "." in k:
                parts = k.split("."); node = cur
                for p in parts[:-1]: node = node.setdefault(p, {})
                node[parts[-1]] = v
            else: cur[k] = v
    def get(self): return _Snap(self._path.rsplit("/", 1)[-1], self._store.get(self._path), self)
    def delete(self): self._store.pop(self._path, None)
    def collection(self, name: str): return _Col(self._store, f"{self._path}/{name}")


class _Col:
    def __init__(self, store: dict, path: str, filters=None, order=None, lim=None):
        self._store, self._path = store, path
        self._filters, self._order, self._lim = filters or [], order, lim
    def document(self, doc_id: str): return _Doc(self._store, f"{self._path}/{doc_id}")
    def add(self, data: dict):
        import uuid
        self._store[f"{self._path}/{uuid.uuid4().hex[:12]}"] = data
    def where(self, field, op, value):
        return _Col(self._store, self._path, self._filters + [(field, op, value)], self._order, self._lim)
    def order_by(self, field, direction="ASCENDING"):
        return _Col(self._store, self._path, self._filters, (field, direction), self._lim)
    def limit(self, n): return _Col(self._store, self._path, self._filters, self._order, n)
    def stream(self):
        depth = self._path.count("/") + 1
        rows = [(p, d) for p, d in self._store.items()
                if p.startswith(self._path + "/") and p.count("/") == depth]
        for f, op, v in self._filters:
            rows = [(p, d) for p, d in rows if op == "==" and d.get(f) == v]
        if self._order:
            fld, direc = self._order
            rows.sort(key=lambda kv: (kv[1].get(fld) is None, kv[1].get(fld)),
                      reverse=(direc == "DESCENDING"))
        if self._lim: rows = rows[: self._lim]
        return [_Snap(p.rsplit("/", 1)[-1], d, _Doc(self._store, p)) for p, d in rows]


class _Batch:
    def __init__(self, store): self._store, self._ops = store, []
    def set(self, doc: _Doc, data: dict): self._ops.append((doc, data))
    def commit(self):
        for doc, data in self._ops: doc.set(data)
        self._ops.clear()


class FakeFirestore:
    def __init__(self): self.store: dict[str, dict] = {}
    def collection(self, path: str): return _Col(self.store, path)
    def document(self, path: str): return _Doc(self.store, path)
    def batch(self): return _Batch(self.store)

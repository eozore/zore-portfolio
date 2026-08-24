"""Stubs dos SDKs pesados — estes testes exercitam o GRAFO, não os agentes."""
import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

os.environ.setdefault("TENANT_KEY_PEPPER", "pepper-de-teste")
os.environ.setdefault("OTEL_DISABLED", "true")

# google.antigravity só existe no runtime da Vertex.
if "google.antigravity" not in sys.modules:
    m = types.ModuleType("google.antigravity")
    m.Agent = object
    m.LocalAgentConfig = object
    m.ModelTarget = object
    m.VertexEndpoint = object
    sys.modules["google.antigravity"] = m

# tools.py inicializa firebase_admin no import.
if "tools" not in sys.modules:
    from fake_firestore import FakeFirestore
    t = types.ModuleType("tools")
    t.db = FakeFirestore()
    for fn in ("get_ecosystem_memory", "fetch_trending_papers", "get_article_by_slug"):
        setattr(t, fn, lambda *a, **k: None)
    sys.modules["tools"] = t

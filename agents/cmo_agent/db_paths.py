from contextvars import ContextVar
from typing import Optional

tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

def get_tenant_id() -> Optional[str]:
    return tenant_id_var.get()

def set_tenant_id(tenant_id: Optional[str]):
    tenant_id_var.set(tenant_id)

def get_session_id() -> Optional[str]:
    return session_id_var.get()

def set_session_id(session_id: Optional[str]):
    session_id_var.set(session_id)

def get_sessions_path() -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/sessions" if tid else "csm_sessions"

def get_session_doc_path(session_id: str) -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/sessions/{session_id}" if tid else f"csm_sessions/{session_id}"

def get_articles_path() -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/articles" if tid else "articles"

def get_article_doc_path(article_id: str) -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/articles/{article_id}" if tid else f"articles/{article_id}"

def get_config_doc_path(agent_name: str) -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/agent_configurations/{agent_name}" if tid else f"agent_configurations/{agent_name}"

def get_configs_path() -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/agent_configurations" if tid else "agent_configurations"

def get_api_keys_doc_path() -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/api_keys/keys" if tid else "agent_configurations/api_keys"

def get_social_queue_path() -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/social_queue" if tid else "social_queue"

def get_usage_logs_path() -> str:
    tid = get_tenant_id()
    return f"tenants/{tid}/usage_logs" if tid else "usage_logs"

def get_local_project_dir(session_id: str) -> str:
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    projects_dir = os.path.join(base_dir, "projects")
    project_dir = os.path.join(projects_dir, session_id)
    return project_dir

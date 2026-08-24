# -*- coding: utf-8 -*-
"""
observability.py — Tracing OpenTelemetry do time de agentes.

Exporta para o Cloud Trace do mesmo projeto GCP. Cada nó do grafo vira um
span com o tenant, o custo estimado e o resultado — é o que permite responder
"por que este pacote demorou 8 minutos" e "qual agente queimou o token" sem
reler log de Cloud Run linha a linha.

Degrada em silêncio de propósito: se o exporter não estiver disponível
(desenvolvimento local, permissão faltando), o tracer vira no-op e o pipeline
continua. Observabilidade que derruba produção é pior do que observabilidade
nenhuma.
"""

from __future__ import annotations

import functools
import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

logger = logging.getLogger("cmo_agent.observability")

_tracer: Optional[Any] = None
_initialized = False

SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "cmo-agent")


def init_tracing() -> None:
    """Configura o exporter uma vez, na subida do serviço."""
    global _tracer, _initialized
    if _initialized:
        return
    _initialized = True

    if os.environ.get("OTEL_DISABLED", "").lower() == "true":
        logger.info("[otel] Tracing desabilitado por OTEL_DISABLED.")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({
            "service.name": SERVICE_NAME,
            "service.version": os.environ.get("K_REVISION", "local"),
        })
        provider = TracerProvider(resource=resource)

        try:
            from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
            project = os.environ.get("FIREBASE_PROJECT_ID")
            provider.add_span_processor(
                BatchSpanProcessor(CloudTraceSpanExporter(project_id=project))
            )
            logger.info("[otel] Exportando para Cloud Trace (project=%s).", project)
        except Exception as exc:
            # Sem exporter os spans ainda existem em memória e a instrumentação
            # do código continua válida — só não sai do processo.
            logger.warning("[otel] Cloud Trace indisponível (%s). Spans locais.", exc)

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(SERVICE_NAME)
    except Exception as exc:
        logger.warning("[otel] Tracing não inicializado: %s", exc)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """
    Abre um span. Vira no-op quando o tracing não está ativo.

    Atributos com valor None são descartados: o OTel rejeita None e uma
    exceção aqui derrubaria o nó que só queria ser observado.
    """
    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name) as sp:
        for key, value in attributes.items():
            if value is not None:
                sp.set_attribute(key, value)
        try:
            yield sp
        except Exception as exc:
            try:
                from opentelemetry.trace import Status, StatusCode
                sp.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
                sp.record_exception(exc)
            except Exception:
                pass
            raise


def traced(name: Optional[str] = None, **static_attrs: Any) -> Callable:
    """Decorator para instrumentar uma corrotina (um nó do grafo)."""
    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            with span(span_name, **static_attrs):
                return await fn(*args, **kwargs)
        return wrapper
    return decorator


def set_attributes(**attrs: Any) -> None:
    """Anexa atributos ao span corrente (custo, contagens, decisões)."""
    if _tracer is None:
        return
    try:
        from opentelemetry import trace
        sp = trace.get_current_span()
        for key, value in attrs.items():
            if value is not None:
                sp.set_attribute(key, value)
    except Exception:
        pass

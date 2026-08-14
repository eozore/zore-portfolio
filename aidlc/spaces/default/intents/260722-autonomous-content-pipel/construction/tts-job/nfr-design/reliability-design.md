# Reliability Design — Bolt 0+1

---

## Implementação do Retry Pattern

```python
# shared/retry.py — padrão implementado para todos os jobs
async def with_retry(fn, max_retries=3, backoff=[1.0,4.0,16.0], transient_errors=(429,503), ...):
    for attempt in range(max_retries):
        try:
            return await fn()
        except ApiError as e:
            if e.status_code not in transient_errors:
                raise  # erro permanente
            # Atualiza UI antes de dormir
            if firestore and project_id:
                await firestore.update_stage(project_id, stage_id, {"retry_count": attempt+1, "status": "retrying"})
            await asyncio.sleep(backoff[attempt])
    raise last_error
```

## Idempotência — verificação no início de cada job

```python
# Padrão aplicado em TTSJob, AvatarJob
project = await self.firestore.get_project(project_id)
if project["stages"][stage_id]["status"] == "completed":
    logger.info("Já completo, ignorando")
    return
```

## Dead Letter Queue
- Tópico `content-pipeline.dead-letter` recebe mensagens após 5 tentativas de entrega
- Cloud Monitoring alerta quando mensagem cai no dead-letter
- Victor pode inspecionar e re-publicar manualmente se necessário

## Timeout do HeyGen Callback
- NFR-02: alerta após 60 min sem callback, falha após 90 min
- Implementação: Cloud Scheduler job secundário que verifica projetos em `pending_callback` há mais de 60 min e dispara alerta
- Victor pode fazer upload manual do vídeo via side panel se timeout ocorrer

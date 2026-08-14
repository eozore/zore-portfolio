# Security Design — Bolt 0+1

---

## Implementação dos Controles SEC-01 a SEC-08

### SEC-01: Secrets via Secret Manager
```python
# shared/pubsub_client.py
def get_secret(secret_name: str, project_id: str) -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
    # NUNCA logar o retorno
```

### SEC-03: Validação do webhook HeyGen
```python
# heygen_callback/app.py
@app.post("/heygen-callback")
async def heygen_callback(
    payload: HeyGenCallbackPayload,
    x_heygen_token: str | None = Header(default=None, alias="X-HeyGen-Token"),
):
    if x_heygen_token != _callback_token:
        raise HTTPException(status_code=401, detail="Token inválido")
```

### SEC-04: Cloud Run Services sem acesso público
- `--no-allow-unauthenticated` no `cloudbuild-pipeline.yaml`
- `heygen-callback` e `publisher-immediate` acessíveis apenas via chamada autenticada

### SEC-05: IAM mínimo para pipeline-jobs-sa
```
roles/datastore.user          → leitura/escrita Firestore
roles/storage.objectAdmin     → GCS upload/download  
roles/pubsub.publisher        → publicar mensagens
roles/pubsub.subscriber       → consumir mensagens
roles/secretmanager.secretAccessor → ler secrets
roles/run.invoker             → chamar outros Cloud Run Services
```

### Firestore Rules (SEC-02)
```
match /content_projects/{projectId} {
  allow read, write: if false;  // apenas Admin SDK
}
```

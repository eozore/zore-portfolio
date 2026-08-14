# Logical Components — Bolt 0+1

---

## Estrutura de Diretórios — `agents/pipeline/`

```
agents/pipeline/
├── Dockerfile                    ← imagem unificada (U-13)
├── requirements.txt              ← deps Python (U-13)
│
├── shared/                       ← U-07: shared lib
│   ├── __init__.py
│   ├── models.py                 ← dataclasses (ContentProject, Segment, Manifest, etc.)
│   ├── retry.py                  ← with_retry + ApiError
│   ├── cost_tracker.py           ← CostTrackerService
│   ├── firestore_client.py       ← FirestoreClient wrapper
│   └── pubsub_client.py          ← PubSubClient + get_secret
│
├── tts_job/                      ← U-08: TTSJob
│   ├── __init__.py
│   ├── __main__.py               ← entry point (python -m tts_job)
│   └── job.py                    ← TTSJob class
│
├── avatar_job/                   ← U-09: AvatarJob
│   ├── __init__.py
│   ├── __main__.py
│   └── job.py
│
├── heygen_callback/              ← U-10: HeyGenCallbackHandler
│   ├── __init__.py
│   └── app.py                    ← FastAPI app (uvicorn entry)
│
├── infra/                        ← U-02: scripts de provisionamento
│   ├── setup_pubsub.sh
│   └── setup_scheduler.sh
│
└── tests/                        ← testes Nyquist
    ├── test_retry.py
    ├── test_cost_tracker.py
    ├── test_tts_job.py
    ├── test_avatar_job.py
    └── test_heygen_callback.py
```

## Dependências entre Componentes (Bolt 1)

```
shared/models.py
    ← usado por: tts_job, avatar_job, heygen_callback

shared/retry.py
    ← usado por: tts_job, avatar_job

shared/cost_tracker.py
    ← usa: shared/firestore_client.py
    ← usado por: tts_job, avatar_job

shared/firestore_client.py
    ← usa: google.cloud.firestore (ADC)
    ← usado por: tts_job, avatar_job, heygen_callback, cost_tracker

shared/pubsub_client.py
    ← usa: google.cloud.pubsub_v1, google.cloud.secretmanager
    ← usado por: tts_job, avatar_job, heygen_callback
```

## Contratos de Interface (Pub/Sub)

| Tópico | Produtor | Consumidor | Dataclass |
|---|---|---|---|
| `content-pipeline.package-approved` | Next.js API | tts-job | `PackageApprovedMsg` |
| `content-pipeline.tts-completed` | tts-job | avatar-job | `TtsCompletedMsg` |
| `content-pipeline.avatar-completed` | heygen-callback | video-editor-job | `AvatarCompletedMsg` |
| `content-pipeline.video-ready` | video-editor-job | publisher-service | `VideoReadyMsg` |

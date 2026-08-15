# ============================================================
# infra/pipeline/main.tf
# Infraestrutura da content pipeline éozoré.
#
# O Terraform gerencia apenas os recursos criados POR ESTA PIPELINE.
# Recursos existentes (Firestore, cmo-agent Cloud Run, etc.) são ignorados.
#
# Para recursos já criados manualmente (Pub/Sub topics, secrets):
#   terraform import <resource> <id>   <- importa sem recriar
# ============================================================

locals {
  env_vars = {
    GCP_PROJECT_ID = var.project_id
    GCS_BUCKET     = google_storage_bucket.pipeline_media.name
    TENANT_ID      = "default"
  }

  sa_email = google_service_account.pipeline_jobs.email
}

# ── Service Account ────────────────────────────────────────────────────────

resource "google_service_account" "pipeline_jobs" {
  account_id   = "pipeline-jobs-sa"
  display_name = "Content Pipeline Jobs"
  description  = "Service account para os Cloud Run Jobs/Services da content pipeline eozore"
}

resource "google_project_iam_member" "sa_datastore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

resource "google_project_iam_member" "sa_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

resource "google_project_iam_member" "sa_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

resource "google_project_iam_member" "sa_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

resource "google_project_iam_member" "sa_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

resource "google_project_iam_member" "sa_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

# ── GCS Bucket ─────────────────────────────────────────────────────────────

resource "google_storage_bucket" "pipeline_media" {
  name                        = "${var.project_id}-pipeline-media"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "sa_bucket_access" {
  bucket = google_storage_bucket.pipeline_media.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

# ── Pub/Sub Topics ─────────────────────────────────────────────────────────

# Geracao do pacote editorial (roteiro/derivacoes). Fica ANTES da aprovacao:
# e o trabalho que antes rodava dentro do request HTTP do Next.js e morria
# junto com a aba do navegador ou com o timeout de 600s do frontend.
resource "google_pubsub_topic" "package_requested" {
  name = "content-pipeline.package-requested"
}

resource "google_pubsub_topic" "package_approved" {
  name = "content-pipeline.package-approved"
}

resource "google_pubsub_topic" "tts_completed" {
  name = "content-pipeline.tts-completed"
}

resource "google_pubsub_topic" "avatar_completed" {
  name = "content-pipeline.avatar-completed"
}

resource "google_pubsub_topic" "video_ready" {
  name = "content-pipeline.video-ready"
}

resource "google_pubsub_topic" "dead_letter" {
  name = "content-pipeline.dead-letter"
}

# ── Pub/Sub Subscriptions (Push -> pipeline-trigger) ──────────────────────
# As subscriptions de pull foram removidas. O pipeline-trigger service
# recebe push HTTP e aciona os Cloud Run Jobs via Run API.
# As URLs de push so ficam validas apos o primeiro deploy do service.
# Terraform gerencia o service e as subscriptions em conjunto.

resource "google_pubsub_subscription" "package_job_sub" {
  name  = "package-job-sub"
  topic = google_pubsub_topic.package_requested.name

  # A geracao leva de 4 a 8 min; o job e disparado de forma assincrona pelo
  # trigger, entao o ack acontece rapido. 600s e folga para o trigger responder.
  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.pipeline_trigger.uri}/trigger/package"

    oidc_token {
      service_account_email = local.sa_email
    }
  }

  # 5 e o minimo aceito pelo Pub/Sub. O job em si nao retenta (max_retries=0):
  # estas tentativas sao do PUSH ao pipeline-trigger, nao da geracao.
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "tts_job_sub" {
  name  = "tts-job-sub"
  topic = google_pubsub_topic.package_approved.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.pipeline_trigger.uri}/trigger/tts"

    oidc_token {
      service_account_email = local.sa_email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "avatar_job_sub" {
  name  = "avatar-job-sub"
  topic = google_pubsub_topic.tts_completed.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.pipeline_trigger.uri}/trigger/avatar"

    oidc_token {
      service_account_email = local.sa_email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "video_editor_sub" {
  name  = "video-editor-job-sub"
  topic = google_pubsub_topic.avatar_completed.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.pipeline_trigger.uri}/trigger/video-editor"

    oidc_token {
      service_account_email = local.sa_email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
}

resource "google_pubsub_subscription" "publisher_sub" {
  name  = "publisher-service-sub"
  topic = google_pubsub_topic.video_ready.name

  ack_deadline_seconds = 600

  # Sem push_config, esta subscription era PULL e ninguém a consumia: o
  # vídeo final existia no GCS mas nunca era publicado em plataforma
  # nenhuma. Corrigido operacionalmente antes deste arquivo ser atualizado
  # (ver comentário em publisher_immediate/app.py:/pubsub/video-ready) — o
  # push já estava configurado em produção, e este bloco só passa a
  # descrever o que já era real.
  push_config {
    push_endpoint = "${google_cloud_run_v2_service.publisher_immediate.uri}/pubsub/video-ready"

    oidc_token {
      service_account_email = local.sa_email
    }
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }
}

# ── Cloud Run Service: pipeline-trigger ──────────────────────────────────
# Recebe push das Pub/Sub subscriptions e aciona os Cloud Run Jobs via API.
# Deve estar deployado antes de criar as subscriptions push.

resource "google_cloud_run_v2_service" "pipeline_trigger" {
  name     = "pipeline-trigger"
  location = var.region

  template {
    service_account = local.sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image   = var.pipeline_image
      command = ["uvicorn"]
      args    = ["pipeline_trigger.app:app", "--host", "0.0.0.0", "--port", "8090"]

      ports {
        container_port = 8090
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }

      dynamic "env" {
        for_each = local.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PYTHONPATH"
        value = "/app"
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }
    }

    timeout = "30s"
  }

  # Pub/Sub push usa OIDC token — nao precisa de acesso publico anonimo
  ingress = "INGRESS_TRAFFIC_ALL"
}

# SA do pipeline pode acionar jobs (necessario para pipeline-trigger)
resource "google_project_iam_member" "sa_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.pipeline_jobs.email}"
}

# ── Cloud Run Service: heygen-callback ────────────────────────────────────

resource "google_cloud_run_v2_service" "heygen_callback" {
  name     = "heygen-callback"
  location = var.region

  template {
    service_account = local.sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image   = var.pipeline_image
      command = ["uvicorn"]
      args    = ["heygen_callback.app:app", "--host", "0.0.0.0", "--port", "8091"]

      ports {
        container_port = 8091
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }

      dynamic "env" {
        for_each = local.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PYTHONPATH"
        value = "/app"
      }
    }

    timeout = "60s"
  }

  ingress = "INGRESS_TRAFFIC_ALL"
}

# ── Cloud Run Service: publisher-immediate ────────────────────────────────


# NOTA DE DRIFT: este resource está desatualizado em relação ao que
# cloudbuild-pipeline.yaml realmente deploya (memory/cpu/timeout maiores,
# secrets do YouTube, GCS_BUCKET/TENANT_ID/PLAYWRIGHT_CHROMIUM_ARGS). O
# cloudbuild é quem roda em CI hoje; este arquivo não reflete a config viva.
# Fica registrado para uma reconciliação futura — não bloqueia o uso normal.
resource "google_cloud_run_v2_service" "publisher_immediate" {
  name     = "publisher-immediate"
  location = var.region

  template {
    service_account = local.sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image   = var.pipeline_image
      command = ["uvicorn"]
      args    = ["publisher_immediate.app:app", "--host", "0.0.0.0", "--port", "8092"]

      ports {
        container_port = 8092
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }

      dynamic "env" {
        for_each = local.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "PYTHONPATH"
        value = "/app"
      }
    }

    timeout = "300s"
  }

  ingress = "INGRESS_TRAFFIC_ALL"
}

# ── Cloud Run Jobs ─────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "package_job" {
  name     = "package-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0   # o job persiste o erro na sessao; retry e do usuario
      # 1h: scriptwriter + slide_designer (1 chamada LLM por slide) + manifest.
      # O limite antigo era o timeout de 600s do servico frontend.
      timeout = "3600s"

      containers {
        image   = var.pipeline_image
        command = ["python", "-m", "package_job"]

        resources {
          limits = {
            memory = "1Gi"
            cpu    = "1"
          }
        }

        dynamic "env" {
          for_each = local.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name  = "PYTHONPATH"
          value = "/app"
        }

        # URL do cmo-agent, que hospeda os agentes especialistas.
        env {
          name  = "CMO_AGENT_URL"
          value = var.cmo_agent_url
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "tts_job" {
  name     = "tts-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "1800s"

      containers {
        image   = var.pipeline_image
        command = ["python", "-m", "tts_job"]

        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1"
          }
        }

        dynamic "env" {
          for_each = local.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name  = "PYTHONPATH"
          value = "/app"
        }

        env {
          name = "ELEVENLABS_API_KEY"
          value_source {
            secret_key_ref {
              secret  = "elevenlabs-api-key"
              version = "latest"
            }
          }
        }

        env {
          name = "ELEVENLABS_VOICE_ID"
          value_source {
            secret_key_ref {
              secret  = "elevenlabs-voice-id"
              version = "latest"
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "avatar_job" {
  name     = "avatar-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "9000s"

      containers {
        image   = var.pipeline_image
        command = ["python", "-m", "avatar_job"]

        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1"
          }
        }

        dynamic "env" {
          for_each = local.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name  = "PYTHONPATH"
          value = "/app"
        }

        env {
          name  = "HEYGEN_CALLBACK_URL"
          value = var.heygen_callback_url
        }

        env {
          name  = "HEYGEN_AVATAR_ID_HORIZONTAL"
          value = "32e2ad6b3e5a45bf8c61cbf7220912f4"
        }

        env {
          name  = "HEYGEN_AVATAR_ID_VERTICAL"
          value = "d7fdce2942a244649820a0b5c989766f"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "video_editor_job" {
  name     = "video-editor-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "3600s"

      containers {
        image   = var.pipeline_image
        command = ["python", "-m", "video_editor_job"]

        resources {
          limits = {
            memory = "4Gi"
            cpu    = "4"
          }
        }

        dynamic "env" {
          for_each = local.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name  = "PYTHONPATH"
          value = "/app"
        }

        env {
          name  = "PLAYWRIGHT_CHROMIUM_ARGS"
          value = "--disable-dev-shm-usage --no-sandbox --disable-gpu"
        }
      }
    }
  }
}

resource "google_cloud_run_v2_job" "publisher_scheduled" {
  name     = "publisher-scheduled"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "1800s"

      containers {
        image   = var.pipeline_image
        command = ["python", "-m", "publisher_job"]

        resources {
          limits = {
            memory = "512Mi"
            cpu    = "1"
          }
        }

        dynamic "env" {
          for_each = local.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }

        env {
          name  = "PYTHONPATH"
          value = "/app"
        }

        env {
          name = "YOUTUBE_OAUTH_REFRESH_TOKEN"
          value_source {
            secret_key_ref {
              secret  = "youtube-oauth-refresh-token"
              version = "latest"
            }
          }
        }
      }
    }
  }
}

# ── Cloud Scheduler ───────────────────────────────────────────────────────

resource "google_cloud_scheduler_job" "daily_publisher" {
  name      = "content-pipeline-daily-publisher"
  region    = var.region
  schedule  = "0 21 * * *"
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.publisher_immediate.uri}/scheduled"
    body        = base64encode(jsonencode({ trigger = "scheduled" }))

    headers = {
      "Content-Type" = "application/json"
    }

    oidc_token {
      service_account_email = local.sa_email
    }
  }
}

# ── Outputs ────────────────────────────────────────────────────────────────

output "heygen_callback_url" {
  description = "URL do heygen-callback Cloud Run Service"
  value       = google_cloud_run_v2_service.heygen_callback.uri
}

output "pipeline_media_bucket" {
  description = "Nome do bucket GCS de midia"
  value       = google_storage_bucket.pipeline_media.name
}

output "service_account_email" {
  description = "Service account dos jobs"
  value       = google_service_account.pipeline_jobs.email
}

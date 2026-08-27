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

# O token-refresh-job GRAVA versões novas de segredo. `secretAccessor` só lê —
# com ele o job renovaria o token na API do provedor e perderia o valor novo,
# invalidando o antigo sem guardar o substituto. Pior que não renovar.
resource "google_project_iam_member" "sa_secret_version_adder" {
  project = var.project_id
  role    = "roles/secretmanager.secretVersionAdder"
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

# Corte vertical: fora do encadeamento automatico de propósito. Só e publicado
# quando o dono do canal libera o pacote, DEPOIS de assistir ao video do
# YouTube — a peca vertical e derivada desse video (crop 9:16 do avatar ja
# gerado + ilustracao vertical com o mesmo audio), nao produzida do zero.
resource "google_pubsub_topic" "vertical_cut" {
  name = "content-pipeline.vertical-cut"
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

resource "google_pubsub_subscription" "vertical_cut_sub" {
  name  = "vertical-cut-job-sub"
  topic = google_pubsub_topic.vertical_cut.name

  ack_deadline_seconds = 600

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.pipeline_trigger.uri}/trigger/vertical-cut"

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
        cpu_idle = false
      }

      dynamic "env" {
        for_each = local.env_vars
        content {
          name  = env.key
          value = env.value
        }
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

  lifecycle {
    ignore_changes = [client, client_version, template[0].containers[0].image]
  }
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
        cpu_idle = false
      }

      dynamic "env" {
        for_each = local.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

    }

    timeout = "60s"
  }

  ingress = "INGRESS_TRAFFIC_ALL"

  lifecycle {
    ignore_changes = [client, client_version, template[0].containers[0].image]
  }
}

# ── Cloud Run Service: publisher-immediate ────────────────────────────────


# Publica o vídeo assim que a pipeline sinaliza `video-ready`, e serve o
# alvo do Cloud Scheduler diário. Chama YouTube e renderiza imagem social com
# Playwright — daí 2 CPU/2Gi e o timeout de 600s, que são os valores no ar.
#
# YOUTUBE_UPLOAD_PRIVACY=private é um trinco, não um padrão: o vídeo sobe
# privado e a publicação é uma decisão humana posterior.
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
          memory = "2Gi"
          cpu    = "2"
        }
        cpu_idle = false
      }

      dynamic "env" {
        for_each = local.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name  = "YOUTUBE_UPLOAD_PRIVACY"
        value = "private"
      }

      env {
        name  = "PLAYWRIGHT_CHROMIUM_ARGS"
        value = "--disable-dev-shm-usage --no-sandbox --disable-gpu"
      }

      env {
        name = "YOUTUBE_OAUTH_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = "youtube-oauth-client-id"
            version = "latest"
          }
        }
      }

      env {
        name = "YOUTUBE_OAUTH_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = "youtube-oauth-client-secret"
            version = "latest"
          }
        }
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

    timeout = "600s"
  }

  ingress = "INGRESS_TRAFFIC_ALL"

  lifecycle {
    ignore_changes = [client, client_version, template[0].containers[0].image]
  }
}

# ── Cloud Run Jobs ─────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "package_job" {
  name     = "package-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0 # o job persiste o erro na sessao; retry e do usuario
      # 1h: scriptwriter + slide_designer (1 chamada LLM por slide) + manifest.
      # O limite antigo era o timeout de 600s do servico frontend.
      timeout = "3600s"

      containers {
        image   = var.pipeline_image
        command = ["python"]
        args    = ["-m", "package_job"]

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


        # URL do cmo-agent, que hospeda os agentes especialistas.
        env {
          name  = "CMO_AGENT_URL"
          value = var.cmo_agent_url
        }
      }
    }
  }
  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
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
        command = ["python"]
        args    = ["-m", "tts_job"]

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
  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
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
        command = ["python"]
        args    = ["-m", "avatar_job"]

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

        # Motor de renderização do HeyGen v3. É o parâmetro que decide a
        # qualidade da sincronia labial — e o custo: avatar_iii custa
        # US$1/min, avatar_iv e avatar_v custam US$4/min. Trocar aqui não
        # exige rebuild da imagem.
        env {
          name  = "HEYGEN_ENGINE"
          value = var.heygen_engine
        }
      }
    }
  }
  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
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
        command = ["python"]
        args    = ["-m", "video_editor_job"]

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
          name  = "PLAYWRIGHT_CHROMIUM_ARGS"
          value = "--disable-dev-shm-usage --no-sandbox --disable-gpu"
        }
      }
    }
  }
  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
  }
}
# Corte vertical: mesmo perfil do editor (Playwright + FFmpeg), mas sem
# nenhum secret de API — ele nao chama HeyGen nem ElevenLabs, so recorta e
# remonta o que o video horizontal ja produziu.
resource "google_cloud_run_v2_job" "vertical_cut_job" {
  name     = "vertical-cut-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "3600s"

      containers {
        image   = var.pipeline_image
        command = ["python"]
        args    = ["-m", "vertical_cut_job"]

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


        # Enquadramento do crop 9:16 sobre o frame 16:9. 0.5 = centrado, que e
        # onde o HeyGen posiciona o apresentador. Ajustavel por preset de
        # avatar sem alterar codigo.
        env {
          name  = "HEYGEN_AVATAR_CROP_X_RATIO"
          value = "0.5"
        }

        env {
          name  = "PLAYWRIGHT_CHROMIUM_ARGS"
          value = "--disable-dev-shm-usage --no-sandbox --disable-gpu"
        }
      }
    }
  }
  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
  }
}
# Fila agendada: publica o que a social_queue marcou para hoje. Mesmo perfil
# do publisher-immediate (Playwright para renderizar imagem de post), por isso
# 2 CPU/2Gi — 512Mi derrubava o Chromium.
#
# Precisa das TRÊS credenciais do YouTube. Com só o refresh token não há como
# trocar por access token: o refresh exige client_id e client_secret juntos.
resource "google_cloud_run_v2_job" "publisher_scheduled" {
  name     = "publisher-scheduled"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "3600s"

      containers {
        image   = var.pipeline_image
        command = ["python"]
        args    = ["-m", "publisher_job"]

        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2"
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
          name  = "PLAYWRIGHT_CHROMIUM_ARGS"
          value = "--disable-dev-shm-usage --no-sandbox --disable-gpu"
        }

        env {
          name = "YOUTUBE_OAUTH_CLIENT_ID"
          value_source {
            secret_key_ref {
              secret  = "youtube-oauth-client-id"
              version = "latest"
            }
          }
        }

        env {
          name = "YOUTUBE_OAUTH_CLIENT_SECRET"
          value_source {
            secret_key_ref {
              secret  = "youtube-oauth-client-secret"
              version = "latest"
            }
          }
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

  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
  }
}

# Renova os tokens de publicação antes de vencerem. Semanal, e a janela de
# renovação é de 15 dias — folga para falhar algumas semanas seguidas sem que
# nenhum token morra.
#
# Não recebe secret nenhum por env de propósito: ele lê E grava versões pela
# API do Secret Manager. Env é resolvida no início da execução e ficaria
# desatualizada no instante em que o job gravasse a versão nova.
resource "google_cloud_run_v2_job" "token_refresh_job" {
  name     = "token-refresh-job"
  location = var.region

  template {
    template {
      service_account = local.sa_email
      max_retries     = 0
      timeout         = "600s"

      containers {
        image   = var.pipeline_image
        command = ["python"]
        args    = ["-m", "token_refresh_job"]

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
      }
    }
  }

  lifecycle {
    ignore_changes = [client, client_version, template[0].template[0].containers[0].image]
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

# Segunda-feira 09:00 UTC. Dia útil de propósito: se o job alertar que um
# token precisa de consentimento humano, o aviso chega quando há alguém para
# agir sobre ele, e sobra a semana inteira antes do vencimento.
resource "google_cloud_scheduler_job" "weekly_token_refresh" {
  name      = "content-pipeline-weekly-token-refresh"
  region    = var.region
  schedule  = "0 9 * * 1"
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.token_refresh_job.name}:run"

    oauth_token {
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

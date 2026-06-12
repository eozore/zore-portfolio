terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "zore-marketing-platform-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# APIs habilitadas
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Service Accounts
# ---------------------------------------------------------------------------
resource "google_service_account" "sa_agents" {
  account_id   = "sa-agents"
  display_name = "Agents Service Account"
  description  = "Service account for the agents (FastAPI + ADK) Cloud Run service"
}

resource "google_service_account" "sa_frontend" {
  account_id   = "sa-frontend"
  display_name = "Frontend Service Account"
  description  = "Service account for the Next.js frontend Cloud Run service"
}

resource "google_service_account" "sa_postiz" {
  account_id   = "sa-postiz"
  display_name = "Postiz MCP Service Account"
  description  = "Service account for the Postiz MCP server Cloud Run service"
}

resource "google_service_account" "sa_renderer" {
  account_id   = "sa-renderer"
  display_name = "Renderer Service Account"
  description  = "Service account for the Puppeteer renderer Cloud Run service"
}

# ---------------------------------------------------------------------------
# Cloud Storage — Bucket de mídia
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "media" {
  name          = "${var.project_id}-media"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

# ---------------------------------------------------------------------------
# Pub/Sub — Tópicos de eventos
# ---------------------------------------------------------------------------
resource "google_pubsub_topic" "agent_events" {
  name = "agent-events"
}

resource "google_pubsub_topic" "publish_requests" {
  name = "publish-requests"
}

# ---------------------------------------------------------------------------
# Cloud Run — Serviços (placeholder configs, imagens atualizadas no deploy)
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "agents" {
  name     = "agents"
  location = var.region

  template {
    service_account = google_service_account.sa_agents.email

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = "frontend"
  location = var.region

  template {
    service_account = google_service_account.sa_frontend.email

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "postiz" {
  name     = "postiz"
  location = var.region

  template {
    service_account = google_service_account.sa_postiz.email

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }
  }

  # Acesso restrito — sem ingress público
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service" "renderer" {
  name     = "renderer"
  location = var.region

  template {
    service_account = google_service_account.sa_renderer.email

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }

  # Acesso restrito — sem ingress público
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# IAM Bindings — Least Privilege
# ---------------------------------------------------------------------------

# sa-agents: acesso a Firestore, Secret Manager, Pub/Sub, Vertex AI, Cloud Storage, invocar renderer
resource "google_project_iam_member" "agents_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.sa_agents.email}"
}

resource "google_project_iam_member" "agents_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sa_agents.email}"
}

resource "google_project_iam_member" "agents_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.sa_agents.email}"
}

resource "google_project_iam_member" "agents_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sa_agents.email}"
}

resource "google_project_iam_member" "agents_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.sa_agents.email}"
}

resource "google_cloud_run_v2_service_iam_member" "agents_invoke_renderer" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.renderer.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa_agents.email}"
}

resource "google_cloud_run_v2_service_iam_member" "agents_invoke_postiz" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.postiz.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa_agents.email}"
}

# sa-frontend: acesso mínimo (Firestore read via Firebase SDK client-side, não via SA)
resource "google_project_iam_member" "frontend_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_frontend.email}"
}

# sa-renderer: acesso a Cloud Storage para upload de assets
resource "google_project_iam_member" "renderer_storage" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.sa_renderer.email}"
}

resource "google_project_iam_member" "renderer_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sa_renderer.email}"
}

# ---------------------------------------------------------------------------
# Firestore — Banco de dados Native Mode
# ---------------------------------------------------------------------------
resource "google_firestore_database" "main" {
  provider    = google-beta
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Secret Manager — Segredos base (estrutura para tokens OAuth por tenant)
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret" "social_tokens" {
  secret_id = "social-tokens"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    purpose     = "oauth-tokens"
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "postiz_config" {
  secret_id = "postiz-config"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    purpose     = "mcp-config"
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Cloud Scheduler — Trigger semanal do Estrategista
# ---------------------------------------------------------------------------
resource "google_cloud_scheduler_job" "weekly_strategy" {
  name        = "weekly-strategy-trigger"
  description = "Dispara o Estrategista semanalmente para gerar calendário de conteúdo"
  schedule    = var.strategist_schedule
  time_zone   = var.strategist_timezone

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.agents.uri}/scheduler/weekly-strategy"

    oidc_token {
      service_account_email = google_service_account.sa_scheduler.email
      audience              = google_cloud_run_v2_service.agents.uri
    }
  }

  retry_config {
    retry_count          = 2
    min_backoff_duration = "300s"
    max_backoff_duration = "600s"
  }

  depends_on = [google_project_service.apis]
}

# Service account for Cloud Scheduler
resource "google_service_account" "sa_scheduler" {
  account_id   = "sa-scheduler"
  display_name = "Scheduler Service Account"
  description  = "Service account for Cloud Scheduler to invoke agents service"
}

# Allow scheduler SA to invoke the agents Cloud Run service
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoke_agents" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agents.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa_scheduler.email}"
}

output "agents_service_url" {
  description = "URL do serviço Cloud Run de agentes (FastAPI + ADK)"
  value       = google_cloud_run_v2_service.agents.uri
}

output "frontend_service_url" {
  description = "URL do serviço Cloud Run do frontend (Next.js)"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "postiz_service_url" {
  description = "URL do serviço Cloud Run do Postiz MCP (acesso interno)"
  value       = google_cloud_run_v2_service.postiz.uri
}

output "renderer_service_url" {
  description = "URL do serviço Cloud Run do Renderizador Puppeteer (acesso interno)"
  value       = google_cloud_run_v2_service.renderer.uri
}

output "media_bucket_name" {
  description = "Nome do bucket Cloud Storage para assets de mídia"
  value       = google_storage_bucket.media.name
}

output "sa_agents_email" {
  description = "Email da service account do serviço de agentes"
  value       = google_service_account.sa_agents.email
}

output "sa_frontend_email" {
  description = "Email da service account do frontend"
  value       = google_service_account.sa_frontend.email
}

output "sa_postiz_email" {
  description = "Email da service account do Postiz"
  value       = google_service_account.sa_postiz.email
}

output "sa_renderer_email" {
  description = "Email da service account do Renderizador"
  value       = google_service_account.sa_renderer.email
}

output "pubsub_agent_events_topic" {
  description = "Nome do tópico Pub/Sub para eventos dos agentes"
  value       = google_pubsub_topic.agent_events.name
}

output "pubsub_publish_requests_topic" {
  description = "Nome do tópico Pub/Sub para requisições de publicação"
  value       = google_pubsub_topic.publish_requests.name
}

output "firestore_database_name" {
  description = "Nome do banco de dados Firestore (Native mode)"
  value       = google_firestore_database.main.name
}

output "scheduler_job_name" {
  description = "Nome do Cloud Scheduler job para o Estrategista semanal"
  value       = google_cloud_scheduler_job.weekly_strategy.name
}

output "sa_scheduler_email" {
  description = "Email da service account do Cloud Scheduler"
  value       = google_service_account.sa_scheduler.email
}

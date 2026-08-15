variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "vazfy-417019"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "pipeline_image" {
  description = "Container image da pipeline (atualizado a cada deploy)"
  type        = string
  default     = "gcr.io/vazfy-417019/pipeline:latest"
}

variable "cmo_agent_url" {
  description = "URL do Cloud Run Service cmo-agent, que hospeda os agentes especialistas consumidos pelo package-job"
  type        = string
  default     = "https://cmo-agent-4zffe4l4lq-uc.a.run.app"
}

variable "heygen_callback_url" {
  description = "URL pública do Cloud Run Service heygen-callback (preenchida após primeiro deploy)"
  type        = string
  default     = "https://heygen-callback-4zffe4l4lq-uc.a.run.app"
}

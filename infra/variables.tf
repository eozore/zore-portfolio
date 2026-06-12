variable "project_id" {
  description = "ID do projeto GCP"
  type        = string
}

variable "region" {
  description = "Região GCP para deploy dos recursos"
  type        = string
  default     = "us-central1"
}

variable "billing_account" {
  description = "ID da conta de billing do GCP vinculada ao projeto"
  type        = string
}

variable "environment" {
  description = "Ambiente de deploy (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment deve ser dev, staging ou prod."
  }
}

variable "strategist_schedule" {
  description = "Cron schedule para o trigger semanal do Estrategista (formato cron do Cloud Scheduler)"
  type        = string
  default     = "0 9 * * 1" # Toda segunda-feira às 9h
}

variable "strategist_timezone" {
  description = "Timezone para o Cloud Scheduler do Estrategista"
  type        = string
  default     = "America/Sao_Paulo"
}

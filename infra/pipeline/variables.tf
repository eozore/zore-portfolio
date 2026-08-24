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

variable "heygen_engine" {
  description = <<-EOT
    Motor de renderização do HeyGen v3 usado pelo avatar-job.

    Decide a qualidade da sincronia labial e o custo, nesta ordem:
      avatar_iii  US$1/min  — o que o endpoint legado /v2 resolvia
      avatar_iv   US$4/min  — padrão do v3
      avatar_v    US$4/min* — maior fidelidade, animação por referência
                              cruzada. (*preço não publicado pela HeyGen;
                              o avatar-job mede o real pela variação do saldo)

    avatar_v exige que o look declare "avatar_v" em supported_api_engines;
    o job checa antes de gastar e cai para avatar_iv se não suportar.
  EOT
  type    = string
  default = "avatar_v"

  validation {
    condition     = contains(["avatar_iii", "avatar_iv", "avatar_v"], var.heygen_engine)
    error_message = "heygen_engine deve ser avatar_iii, avatar_iv ou avatar_v."
  }
}

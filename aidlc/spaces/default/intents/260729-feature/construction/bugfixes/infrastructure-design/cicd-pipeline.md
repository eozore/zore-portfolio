# CI/CD Pipeline
Deploy: `gcloud builds submit --config=cloudbuild.yaml --project=vazfy-417019 --substitutions=COMMIT_SHA=<tag>`
BUG2: garantir que os 3 serviços modificados sejam rebuild no mesmo cloudbuild.yaml.

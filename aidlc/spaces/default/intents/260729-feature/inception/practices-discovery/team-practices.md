# Team Practices

## Coding Standards
- Python: PEP8, type hints, asyncio para todos os handlers FastAPI
- TypeScript: strict mode, interfaces explícitas para todos os modelos de dados
- Pydantic v2: `model_config = ConfigDict(populate_by_name=True)`, `Field(alias=...)` para compatibilidade JSON
- Nomes de função Python: snake_case. Nomes de classe: PascalCase.
- Todos os agentes Python seguem o padrão: `run_<agente>(params) -> dict`

## Testing
- Sem testes automatizados formais neste projeto (projeto solo)
- Verificação: teste manual via endpoint + log visual

## Deployment
- Deploy via `gcloud builds submit --config=cloudbuild.yaml --project=vazfy-417019`
- Cloud Run: imagens Docker, region us-central1
- Variáveis sensíveis: Secret Manager (não .env em produção)

## Walking Skeleton
- off — projeto já em produção, não é greenfield

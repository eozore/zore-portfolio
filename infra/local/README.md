# Ambiente local

Sobe a plataforma inteira na sua máquina para validar antes de gastar deploy.

```bash
docker compose -f docker-compose.local.yml up --build
docker compose -f docker-compose.local.yml exec cmo-agent python /app/seed.py
```

Abra **http://localhost:3000/admin/studio** — senha `local`.

## O que é real e o que é simulado

| | | Por quê |
|---|---|---|
| Firestore | emulado | não polui o banco de produção com dados de teste |
| **Vertex AI** | **REAL** | não existe emulador — e o conteúdo gerado é justamente o que você quer avaliar. Centavos por ciclo. |
| HeyGen | stub | devolve `samples/spike_lipsync_result.mp4`. Zero crédito. |
| ElevenLabs | stub | devolve `samples/voice_clone_flash_v2_5_test.mp3` com alinhamento sintético de mesma forma da API real. |

O Vertex usa as credenciais do seu `gcloud` — o compose monta `~/.config/gcloud`
somente-leitura. Se `gcloud auth application-default login` estiver vencido, o
agente sobe mas falha na geração.

## O que este ambiente NÃO pega

IAM, Secret Manager, cold start e a rede entre serviços do Cloud Run. Essas
falhas só aparecem no ambiente real — foi assim que o `heygen-callback` com IAM
bloqueou 100% dos webhooks sem nenhum sinal local.

O que ele pega, e que é o que mais custou até aqui: erro de integração entre
etapas, contrato de dado quebrado e regressão visual.

## Reiniciar do zero

```bash
docker compose -f docker-compose.local.yml down -v
```

O `-v` descarta o Firestore emulado. Sem ele, a sessão anterior continua e o
Studio reabre no mesmo ponto — útil para retomar um gate, indesejado quando
você quer testar o fluxo desde o começo.

# Performance Design — Bolt 0+1

> Referências: NFR Requirements + Functional Design de todas as unidades do Bolt 0 e Bolt 1.

---

## Estratégias de Performance por Componente

### TTSJob (U-08)
- **Processamento paralelo de segmentos:** para vídeos com muitos segmentos, usar `asyncio.gather()` para chamar ElevenLabs em paralelo (limitado a 2 chamadas simultâneas para respeitar rate limits)
- **Output format:** `mp3_44100_128` — melhor relação qualidade/tamanho; não usar PCM (plano pago necessário)
- **Upload GCS streaming:** `blob.upload_from_string()` com buffer de memória — evita escrita em disco exceto para arquivo concatenado do pydub

### AvatarJob (U-09)
- **pydub export:** usar `format="mp3", bitrate="128k"` — compatível com HeyGen Assets API
- **Upload HeyGen Assets:** arquivo concatenado típico ~5-15 MB — upload em ~5-30s dependendo da rede
- **Timeout generoso (150 min):** o job termina após criar os Lipsync jobs; o timeout protege contra lentidão no upload

### HeyGenCallback (U-10)
- **Startup no evento startup():** clientes Firestore, Pub/Sub e GCS inicializados no startup do FastAPI, não no primeiro request — elimina cold start de 1-3s no webhook crítico
- **Download assíncrono:** `httpx.AsyncClient` para baixar vídeo HeyGen — não bloqueia o event loop

### Firestore (U-01)
- **Índice `collection_group` em lipsync_jobs:** criado via `firestore.indexes.json` antes do deploy — sem esse índice, query do HeyGenCallback custa ~100ms extra e pode falhar

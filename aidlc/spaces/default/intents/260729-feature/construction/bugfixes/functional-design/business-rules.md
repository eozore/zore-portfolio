# Business Rules

- BR1: tipo_artigo default = "tecnico" (retrocompatibilidade)
- BR2: slide_designer_agent falha silenciosamente — se HTML inválido, manter placeholder original
- BR3: search_web sem TAVILY_API_KEY → retorna string de erro, não crash
- BR4: AvatarCompletedMsg publicado apenas quando 100% dos segmentos de AMBOS targets completarem
- BR5: plots PNG salvos em GCS com ACL pública (allUsers Storage Object Viewer)

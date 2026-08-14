# Domain Entities

## PautaConcebida (TypeScript + Pydantic)
Adiciona: tipo_artigo?: "tecnico" | "conceitual" | "estrategico"

## AvatarCompletedMsg (dataclass)
Muda: horizontal_video_path: str → horizontal_video_paths: list[str]
Muda: vertical_video_path: str → vertical_video_paths: list[str]
Adiciona: segment_ids: list[str]

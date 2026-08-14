# Component Methods

## slide_designer_agent (C-NEW-1)
```python
async def run_slide_designer(
    segment: dict,          # {segment_id, beat, script, anchors, pauta_titulo, serie}
    pauta: dict,            # {titulo, serie, tese, ...}
    target: str = "horizontal",  # "horizontal" | "vertical"
) -> str:
    """Retorna HTML completo do slide para o segmento. String vazia se falhar."""
```

## code_executor (C-MOD-1)
```python
def execute_python_plot(code_str: str, gcs_bucket: str) -> str:
    """Executa matplotlib, salva PNG no GCS, retorna URL pública. None se falhar."""

def post_process_article_plots(content: str, gcs_bucket: str) -> str:
    """Substitui blocos python-plot por ![alt](url_gcs). Assinatura muda: adiciona gcs_bucket."""
```

## tools (C-MOD-2)
```python
def search_web(query: str, max_results: int = 5) -> str:
    """Tavily API. Mesma assinatura e formato de retorno."""
```

## AvatarJob (C-MOD-8)
```python
async def run(self, msg: TtsCompletedMsg) -> None:
    """Loop por segmento individual em vez de concatenar."""

# _concatenate_audio() REMOVIDA

async def _process_single_segment(
    self, seg_path: str, avatar_id: str, target: str, project_id: str, seg_idx: int
) -> dict:
    """Upload + generate para 1 segmento. Retorna {seg_id, video_id}."""
```

## VideoEditorJob (C-MOD-11)
```python
async def _compose_timeline(
    self,
    segments: list[dict],
    segment_video_paths: dict[str, str],  # seg_id → local path
    slides_dir: Path,
    output_path: str,
    target: str,
) -> None:
    """avatar_path removido; segment_video_paths usado por segmento."""
```

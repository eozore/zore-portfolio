# -*- coding: utf-8 -*-
"""
code_executor.py — Executa blocos python-plot e salva os gráficos no GCS.
[...docstring mantido abreviado para clareza...]
"""
import os
import re
import subprocess
import sys
import uuid
import logging
import tempfile

logger = logging.getLogger("cmo_agent.code_executor")

# Bucket padrão — sobrescrito pela variável de ambiente GCS_BUCKET do Cloud Run
_DEFAULT_BUCKET = "vazfy-417019-pipeline-media"


def execute_python_plot(code_str: str, gcs_bucket: str | None = None) -> str | None:
    """
    Executa o bloco de código Python contendo um gráfico matplotlib.
    Salva a imagem no GCS e retorna a URL pública. Retorna None se falhar.

    Args:
        code_str:   Código Python do bloco python-plot.
        gcs_bucket: Nome do bucket GCS onde salvar. Usa GCS_BUCKET env var ou default.

    Returns:
        URL pública https://storage.googleapis.com/<bucket>/plots/<filename>,
        ou None em caso de falha.
    """
    bucket_name = gcs_bucket or os.environ.get("GCS_BUCKET", _DEFAULT_BUCKET)
    filename = f"plot-{uuid.uuid4().hex[:12]}.png"
    tmp_path = os.path.join(tempfile.gettempdir(), filename)

    # Prepara o script: força backend Agg (não interativo), salva em tmp
    header = (
        "import sys\n"
        "import os\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "import numpy as np\n"
    )
    footer = (
        f"\nplt.savefig(r'{tmp_path}', bbox_inches='tight', dpi=150)\n"
        "plt.close('all')\n"
    )
    clean_code = code_str.replace("plt.show()", "# plt.show() desabilitado")
    full_code = header + clean_code + footer

    # Arquivo temporário do script
    script_fd, script_path = tempfile.mkstemp(suffix=".py", prefix="cmo_plot_")
    try:
        with os.fdopen(script_fd, "w", encoding="utf-8") as f:
            f.write(full_code)

        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning(f"[code_executor] Plot execution failed (rc={result.returncode}): {result.stderr[:300]}")
            return None

        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            logger.warning("[code_executor] Plot file not generated or empty.")
            return None

        # Upload para GCS
        try:
            from google.cloud import storage as gcs_storage
            gcs_client = gcs_storage.Client()
            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(f"plots/{filename}")
            blob.upload_from_filename(tmp_path, content_type="image/png")
            blob.make_public()
            public_url = f"https://storage.googleapis.com/{bucket_name}/plots/{filename}"
            logger.info(f"[code_executor] Plot uploaded: {public_url}")
            return public_url
        except Exception as gcs_err:
            logger.warning(f"[code_executor] GCS upload failed: {gcs_err}. Falling back to local path.")
            # Fallback: salva em public/images/plots do workspace local (apenas dev)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            local_plots_dir = os.path.join(base_dir, "apps", "web", "public", "images", "plots")
            os.makedirs(local_plots_dir, exist_ok=True)
            import shutil
            shutil.copy2(tmp_path, os.path.join(local_plots_dir, filename))
            return f"/images/plots/{filename}"

    except subprocess.TimeoutExpired:
        logger.warning("[code_executor] Plot script timed out (>15s).")
        return None
    except Exception as e:
        logger.error(f"[code_executor] Unexpected error: {e}")
        return None
    finally:
        # Limpa arquivos temporários
        for path in (script_path, tmp_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


def post_process_article_plots(content: str, gcs_bucket: str | None = None) -> str:
    """
    Varre o artigo markdown por blocos ```python-plot e os substitui por
    imagens Markdown com URL GCS (ou path local como fallback).

    O bloco de código Python é mantido visível (como ```python) para que o
    leitor possa inspecionar o código, e a imagem é inserida logo abaixo.

    Args:
        content:    Conteúdo Markdown do artigo.
        gcs_bucket: Bucket GCS. Se None, usa variável de ambiente GCS_BUCKET.

    Returns:
        Conteúdo Markdown com blocos python-plot substituídos.
    """
    pattern = r"```python-plot\n([\s\S]*?)```"

    def replacer(match: re.Match) -> str:
        code_body = match.group(1)
        logger.info("[code_executor] Processando bloco python-plot...")
        image_url = execute_python_plot(code_body, gcs_bucket)
        if image_url:
            # Extrai nome descritivo do arquivo como alt text
            alt = os.path.splitext(os.path.basename(image_url))[0]
            logger.info(f"[code_executor] Gráfico gerado: {image_url}")
            # Mantém código como ```python + adiciona imagem abaixo
            return f"```python\n{code_body}```\n\n![{alt}]({image_url})\n"
        else:
            logger.warning("[code_executor] Falha ao gerar imagem. Mantendo como bloco python padrão.")
            return f"```python\n{code_body}```"

    return re.sub(pattern, replacer, content)

# -*- coding: utf-8 -*-
import os
import re
import subprocess
import uuid
import logging

logger = logging.getLogger("cmo_agent.code_executor")

def execute_python_plot(code_str: str, public_plots_dir: str) -> str:
    """
    Executa o bloco de código Python contendo um gráfico do matplotlib.
    Salva a imagem do gráfico na pasta pública do Next.js.
    Retorna o path relativo da imagem gerada, ou None se falhar.
    """
    # Garante que a pasta de destino existe
    os.makedirs(public_plots_dir, exist_ok=True)
    
    filename = f"plot-{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(public_plots_dir, filename)
    
    # Prepara o script com backend Agg (não interativo) para evitar popups locais no mac do usuário
    header = (
        "import sys\n"
        "import os\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
    )
    
    # Código para salvar a figura caso o script original não salve explicitamente
    footer = f"\nplt.savefig(r'{filepath}', bbox_inches='tight', dpi=150)\nplt.close()\n"
    
    # Remove plt.show() do script original pois em Agg causa warning/bloqueio
    clean_code = code_str.replace("plt.show()", "")
    full_code = header + clean_code + footer
    
    temp_filename = f"temp_run_{uuid.uuid4().hex[:8]}.py"
    temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), temp_filename)
    
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(full_code)
        
    try:
        import sys
        # Executa em subprocesso com o mesmo interpretador python rodando o agente
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=12
        )
        if result.returncode != 0:
            logger.error(f"Plot execution failed: {result.stderr}")
            return None
            
        # Verifica se o arquivo de imagem foi gerado com sucesso
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return f"/images/plots/{filename}"
            
        return None
    except Exception as e:
        logger.error(f"Failed running script: {e}")
        return None
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def post_process_article_plots(content: str) -> str:
    """
    Varre o artigo markdown por blocos de código marcados exclusivamente com ```python-plot.
    Executa o código, gera os gráficos em imagem e insere a tag de imagem markdown
    logo abaixo do bloco de código.
    """
    # Procura blocos ```python-plot ... ``` exclusivamente
    pattern = r"```python-plot\n([\s\S]*?)```"
    
    # Diretório público do Next.js na workspace do usuário
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    public_plots_dir = os.path.join(base_dir, "apps", "web", "public", "images", "plots")
    
    def replacer(match):
        code_body = match.group(1)
        
        logger.info("Encontrado bloco de código contendo gráfico (python-plot). Executando código...")
        image_path = execute_python_plot(code_body, public_plots_dir)
        if image_path:
            logger.info(f"Gráfico gerado com sucesso em: {image_path}")
            # Substitui para ```python (mantendo a colorização) e adiciona a tag de imagem renderizada abaixo
            return f"```python\n{code_body}```\n\n![Gráfico Científico Renderizado]({image_path})\n"
        else:
            logger.warn("Falha ao gerar imagem do gráfico. Mantendo bloco de código padrão.")
            return f"```python\n{code_body}```"
            
    processed_content = re.sub(pattern, replacer, content)
    return processed_content

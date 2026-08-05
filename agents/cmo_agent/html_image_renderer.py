# -*- coding: utf-8 -*-
"""
html_image_renderer.py
=======================
Renderiza HTML para PNG usando Playwright (Chromium headless).
Usado para gerar imagens de posts LinkedIn (1200x628) e Instagram (1080x1080)
a partir do imageHtml gerado pelo distribution_agent.

Função principal: render_html_to_png(html: str, width: int, height: int) -> bytes
"""

import asyncio
import logging
import os
import re
import textwrap
from typing import Optional

logger = logging.getLogger("cmo_agent.html_image_renderer")

# ── Playwright async render ────────────────────────────────────────────────────

async def _render_async(html: str, width: int, height: int) -> bytes:
    from playwright.async_api import async_playwright

    # Garante que o HTML tem viewport declarado e box-sizing correto
    wrapped = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={width}, initial-scale=1.0">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{ width: {width}px; height: {height}px; overflow: hidden; }}
</style>
</head>
<body>
{html}
</body>
</html>"""

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
            ]
        )
        page = await browser.new_page(
            viewport={"width": width, "height": height},
        )
        await page.set_content(wrapped, wait_until="networkidle")
        # Aguarda fontes e renderização
        await page.wait_for_timeout(300)
        png_bytes = await page.screenshot(
            full_page=False,
            clip={"x": 0, "y": 0, "width": width, "height": height},
            type="png",
        )
        await browser.close()
        return png_bytes


def render_html_to_png(html: str, width: int = 1200, height: int = 628) -> bytes:
    """
    Renderiza HTML para PNG via Playwright headless.
    Síncrono — cria event loop próprio.

    Args:
        html:   Conteúdo HTML (parcial ou completo). Não precisa de <html><body>.
        width:  Largura do viewport em pixels (LinkedIn: 1200, Instagram: 1080).
        height: Altura do viewport em pixels (LinkedIn: 628, Instagram: 1080).

    Returns:
        bytes PNG da imagem renderizada.

    Raises:
        RuntimeError: Se Playwright não estiver instalado ou Chromium indisponível.
    """
    try:
        return asyncio.run(_render_async(html, width, height))
    except Exception as e:
        logger.error(f"[html_image_renderer] Playwright render failed: {e}")
        raise RuntimeError(f"HTML to PNG render failed: {e}") from e


# ── Fallback: PIL render quando Playwright não está disponível ─────────────────

def _pil_fallback(title: str, body: str, width: int, height: int) -> bytes:
    """
    Gera imagem PNG básica via PIL quando Playwright falha.
    Mantém identidade visual dark premium mínima.
    """
    import io
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), color=(15, 23, 42))   # #0f172a
    draw = ImageDraw.Draw(img)

    # Faixa de acento lateral
    draw.rectangle([(0, 0), (8, height)], fill=(124, 58, 237))    # #7c3aed

    def _font(size: int):
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    font_brand = _font(26)
    font_title = _font(int(height * 0.075))
    font_body  = _font(int(height * 0.038))

    pad = 60
    draw.text((pad, int(height * 0.05)), "éozoré", fill=(124, 58, 237), font=font_brand)

    # Título
    title_clean = re.sub(r"\s+", " ", title).strip()
    wrapped = textwrap.fill(title_clean, width=max(20, width // (font_title.size // 2 + 2)))
    draw.text((pad, int(height * 0.18)), wrapped, fill=(255, 255, 255), font=font_title)

    # Corpo
    if body:
        body_clean = re.sub(r"\s+", " ", body[:300]).strip()
        wrapped_body = textwrap.fill(body_clean, width=max(30, width // (font_body.size // 2 + 2)))
        draw.text((pad, int(height * 0.55)), wrapped_body, fill=(148, 163, 184), font=font_body)

    draw.text((pad, height - int(height * 0.08)), "eozore.com", fill=(99, 102, 241), font=font_body)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Função pública com fallback automático ─────────────────────────────────────

def render_html_image(
    html: str,
    width: int,
    height: int,
    fallback_title: str = "éozoré",
    fallback_body: str = "",
) -> bytes:
    """
    Tenta Playwright; se falhar, usa PIL fallback.
    Sempre retorna bytes PNG válidos.

    Args:
        html:            HTML gerado pelo distribution_agent (imageHtml).
        width:           Largura em pixels.
        height:          Altura em pixels.
        fallback_title:  Título para o fallback PIL se Playwright falhar.
        fallback_body:   Corpo para o fallback PIL.

    Returns:
        bytes PNG.
    """
    try:
        return render_html_to_png(html, width, height)
    except Exception as e:
        logger.warning(f"[html_image_renderer] Playwright failed, using PIL fallback: {e}")
        return _pil_fallback(fallback_title, fallback_body, width, height)

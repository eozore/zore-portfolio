"""
tests/test_reprocesso_publisher.py
===================================
Republicar não pode duplicar o vídeo no canal.

Em 27/08, reprocessar a publicação de um projeto subiu o arquivo de novo em
vez de atualizar o que já estava lá. O canal ficou com TRÊS vídeos do mesmo
tema — o truncado, o corrigido, e o do teste de reprocesso.

O YouTube não permite trocar o ARQUIVO de um vídeo, mas permite trocar tudo em
volta. Então:

  - a EDIÇÃO refez o vídeo  → arquivo novo → upload novo, e aí o id anterior
    tem que ser esquecido;
  - só a descrição ou a capa mudaram → atualiza no lugar, mesmo id.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cliente_do_youtube_sabe_atualizar_no_lugar():
    """
    Sem `update_video_metadata` a única saída é reupload, e reupload em
    correção de descrição sempre gera duplicata.
    """
    from publisher_job.youtube_client import YouTubeClient

    assert hasattr(YouTubeClient, "update_video_metadata")


def test_update_usa_videos_update_e_nao_o_endpoint_de_upload():
    """
    `videos.update` é PUT em /youtube/v3/videos. Bater no /upload/ criaria um
    vídeo novo, que é exatamente o defeito.
    """
    import inspect

    from publisher_job.youtube_client import YouTubeClient

    src = inspect.getsource(YouTubeClient.update_video_metadata)
    assert "requests.put" in src
    assert "/videos?part=snippet" in src
    assert "UPLOAD_API" not in src


def test_publisher_atualiza_em_vez_de_pular_quando_ja_publicado():
    """
    A versão anterior devolvia o post_id e seguia adiante. Descrição e capa
    regeradas nunca chegavam ao vídeo — foi por isso que corrigir a descrição
    de 27/08 exigiu chamar a API à mão.
    """
    import inspect

    from publisher_job.job import PublisherJob

    src = inspect.getsource(PublisherJob)
    assert "update_video_metadata" in src, (
        "o caminho de 'já publicado' precisa atualizar o vídeo, não só pular"
    )


def test_falha_do_update_nao_vira_reupload():
    """
    Se a atualização falhar, o vídeo antigo continua no ar e visível. Subir de
    novo criaria o duplicado que este caminho existe para evitar.
    """
    import inspect

    from publisher_job.job import PublisherJob

    src = inspect.getsource(PublisherJob)
    trecho = src[src.index("update_video_metadata"):]
    # O except em volta do update apenas registra e segue com o post_id antigo.
    assert "logger.warning" in trecho[:900]

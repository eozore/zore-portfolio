# -*- coding: utf-8 -*-
"""
tools.py — Custom tools for the Google Antigravity CMO Agent
Includes:
- get_ecosystem_memory: Fetches recent published articles and social posts.
- fetch_trending_papers: Queries arXiv for recent technical papers.
"""

import firebase_admin
from firebase_admin import firestore
import urllib.request
import urllib.parse
import re
import logging
import os
from datetime import datetime
import db_paths

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin if not already done
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

# Get Firestore instance
#
# `FIRESTORE_DATABASE` existe por causa do emulador. O nome padrão do banco é
# `(default)`, e o cliente 2.2x manda esse nome PERCENT-ENCODED no cabeçalho de
# roteamento (`%28default%29`); o emulador não decodifica e recusa toda escrita
# e toda query com `400 Illegal string`. Leitura de documento único passa, o
# que fazia a falha parecer intermitente.
#
# Não dá para resolver por versão: o cliente que funciona com o emulador é
# anterior ao que o firebase-admin 7.5 exige, e o downgrade arrasta o protobuf
# para trás e quebra o import do google-antigravity.
#
# Um banco com nome sem parênteses não tem o que codificar. Produção continua
# em `(default)` porque a variável não é setada lá.
try:
    _DATABASE = os.environ.get("FIRESTORE_DATABASE", "").strip()
    db = firestore.client(database_id=_DATABASE) if _DATABASE else firestore.client()
except Exception as e:
    logger.warning(f"Failed to initialize Firestore client: {e}")
    db = None

def get_ecosystem_memory() -> str:
    """Recupera a memória histórica do ecossistema éozoré do Firestore.

    Retorna uma lista dos artigos mais recentes publicados no blog e das peças
    de conteúdo social geradas anteriormente na queue de postagem.
    """
    if db is None:
        return "Ecosystem memory is currently unavailable (Firestore client not initialized)."

    try:
        # Fetch articles ordered by publishedAt desc
        articles_ref = db.collection(db_paths.get_articles_path()).order_by('publishedAt', direction=firestore.Query.DESCENDING).limit(4).get()
        recent_articles = []
        for doc in articles_ref:
            d = doc.to_dict()
            recent_articles.append({
                "title": d.get("title", doc.id),
                "slug": d.get("slug", doc.id)
            })

        # Fetch social queue items ordered by scheduled_at desc
        social_ref = db.collection(db_paths.get_social_queue_path()).order_by('scheduled_at', direction=firestore.Query.DESCENDING).limit(8).get()
        recent_social = []
        for doc in social_ref:
            d = doc.to_dict()
            recent_social.append({
                "platform": d.get("platform", "linkedin"),
                "title": d.get("title") or (d.get("copy", "")[:60] if isinstance(d.get("copy"), str) else "")
            })

        if not recent_articles and not recent_social:
            return "Nenhum histórico prévio registrado no banco de dados."

        art_text = "\n".join([f"{i+1}) TÍTULO: \"{a['title']}\" (slug: {a['slug']})" for i, a in enumerate(recent_articles)])
        soc_text = "\n".join([f"{i+1}) [{s['platform'].upper()}] \"{s['title']}\"" for i, s in enumerate(recent_social)])

        return (
            f"=== MEMÓRIA HISTÓRICA DO ECOSSISTEMA ÉOZORÉ ===\n\n"
            f"[ÚLTIMOS ARTIGOS PUBLICADOS]\n{art_text or 'Nenhum'}\n\n"
            f"[ÚLTIMAS PEÇAS SOCIAIS GERADAS]\n{soc_text or 'Nenhum'}\n\n"
            f"INSTRUÇÃO ESPECIAL DE MARKETING: Mantenha a continuidade didática e filosófica com os temas acima, mas NUNCA repita os mesmos ganchos exatos ou analogias superficiais já ensinados prévias."
        )
    except Exception as e:
        logger.error(f"Error fetching ecosystem memory: {e}")
        return f"Falha ao recuperar a memória do ecossistema: {str(e)}"

def get_article_by_slug(slug: str) -> str:
    """Recupera o conteúdo completo de um artigo específico do blog éozoré usando o seu slug.

    Use esta ferramenta quando precisar analisar em detalhes o conteúdo, fórmulas, tom de escrita
    ou ganchos específicos de um artigo anterior para garantir continuidade ou evitar redundâncias.

    Args:
        slug: O slug identificador do artigo (ex: "viabilidade-dos-agentes-ia", "mlops-na-pratica").
    """
    if db is None:
        return "Ecosystem database is currently unavailable."

    try:
        docs = db.collection(db_paths.get_articles_path()).where('slug', '==', slug).limit(1).get()
        if not docs:
            doc_ref = db.collection(db_paths.get_articles_path()).document(slug).get()
            if doc_ref.exists:
                d = doc_ref.to_dict()
                return f"=== CONTEÚDO DO ARTIGO: {d.get('title', slug)} ===\n\n{d.get('content', '')}"
            return f"Artigo com o slug '{slug}' não foi encontrado no banco de dados."
        
        doc = docs[0]
        d = doc.to_dict()
        return f"=== CONTEÚDO DO ARTIGO: {d.get('title', slug)} ===\n\n{d.get('content', '')}"
    except Exception as e:
        logger.error(f"Error fetching article by slug {slug}: {e}")
        return f"Erro ao recuperar artigo com slug '{slug}': {str(e)}"

def fetch_trending_papers(query: str, max_results: int = 2) -> str:
    """Busca artigos científicos recentes no arXiv sobre um tópico técnico específico.

    Args:
        query: O termo de busca (ex: "large language models", "fine-tuning", "RAG").
        max_results: Número máximo de papers a serem retornados (padrão: 2).
    """
    session_id = db_paths.get_session_id()
    
    if session_id and db is not None:
        try:
            session_ref = db.collection(db_paths.get_sessions_path()).document(session_id)
            doc = session_ref.get()
            if doc.exists:
                session_data = doc.to_dict()
                draft = session_data.get("draft", {})
                checkpoint = draft.get("checkpoint", {}) if isinstance(draft, dict) else {}
                if checkpoint and isinstance(checkpoint, dict):
                    research_stage = checkpoint.get("stages", {}).get("research", {})
                    papers = research_stage.get("papers", [])
                    if papers and len(papers) > 0:
                        logger.info(f"[tools] Encontrado checkpoint de papers no Firestore para a sessão {session_id}. Retornando cache.")
                        papers_text = ""
                        for i, p in enumerate(papers):
                            papers_text += f"{i+1}. \"{p.get('title')}\"\n   Link: {p.get('pdfUrl')}\n   Resumo: {p.get('summary')}...\n\n"
                        return f"=== PAPERS RECENTES NO arXiv (CACHE CHECKPOINT) ===\n\n{papers_text}"
        except Exception as e:
            logger.warning(f"Erro ao verificar checkpoint de papers no Firestore: {e}")

    safe_query = urllib.parse.quote(query.replace(' ', '+'))
    url = f"https://export.arxiv.org/api/query?search_query=all:{safe_query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'eozore-cmo-agent/1.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read().decode('utf-8')
            
        entries = xml_data.split('<entry>')[1:]
        parsed_papers = []
        for entry in entries:
            title_match = re.search(r'<title>([\s\S]*?)</title>', entry)
            summary_match = re.search(r'<summary>([\s\S]*?)</summary>', entry)
            published_match = re.search(r'<published>([\s\S]*?)</published>', entry)
            link_match = re.search(r'href="(https://arxiv.org/abs/[^"]+)"', entry)
            
            title = title_match.group(1).replace('\n', ' ').strip() if title_match else ''
            summary = summary_match.group(1).replace('\n', ' ').strip() if summary_match else ''
            published = published_match.group(1)[:10] if published_match else ''
            link = link_match.group(1) if link_match else ''
            
            if title:
                # Clean multiple spaces
                title = re.sub(r'\s+', ' ', title)
                summary = re.sub(r'\s+', ' ', summary)
                parsed_papers.append((title, published, link, summary[:250]))
                
        if not parsed_papers:
            return f"Nenhum paper recente encontrado no arXiv para: '{query}'."

        if session_id and db is not None:
            try:
                papers_list = []
                for t, pub, l, s in parsed_papers:
                    papers_list.append({
                        "title": t,
                        "pdfUrl": l,
                        "summary": s
                    })
                
                session_ref = db.collection(db_paths.get_sessions_path()).document(session_id)
                doc = session_ref.get()
                current_draft = {}
                if doc.exists:
                    current_draft = doc.to_dict().get("draft", {})
                    if not isinstance(current_draft, dict):
                        current_draft = {}
                
                checkpoint = current_draft.get("checkpoint", {})
                if not isinstance(checkpoint, dict):
                    checkpoint = {}
                
                stages = checkpoint.get("stages", {})
                if not isinstance(stages, dict):
                    stages = {}
                
                stages["research"] = {
                    "papers": papers_list,
                    "updatedAt": int(datetime.utcnow().timestamp() * 1000)
                }
                checkpoint["stages"] = stages
                checkpoint["currentStage"] = "writing"
                current_draft["checkpoint"] = checkpoint
                
                session_ref.set({"draft": current_draft}, merge=True)
                logger.info(f"[tools] Checkpoint de papers gravado com sucesso no Firestore para a sessão {session_id}.")
            except Exception as e:
                logger.warning(f"Erro ao salvar checkpoint de papers no Firestore: {e}")
            
        papers_text = ""
        for i, (t, pub, l, s) in enumerate(parsed_papers):
            papers_text += f"{i+1}. \"{t}\"\n   Publicado: {pub} | Link: {l}\n   Resumo: {s}...\n\n"
            
        return f"=== PAPERS RECENTES NO arXiv ({query}) ===\n\n{papers_text}"
    except Exception as e:
        logger.error(f"Error fetching arXiv papers: {e}")
        return f"Falha ao buscar papers no arXiv sobre '{query}': {str(e)}"

def search_web(query: str, max_results: int = 5) -> str:
    """Busca na internet informações e tendências sobre tópicos tecnológicos gerais.

    Usa a Tavily API (https://tavily.com) — projetada para agentes de IA.
    Requer a variável de ambiente TAVILY_API_KEY no Secret Manager do GCP.

    Args:
        query: O termo de busca (ex: "Vertex AI agent architecture", "FastAPI best practices").
        max_results: Número máximo de resultados (padrão: 5).
    """
    import json as _json

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning(
            "[tools] TAVILY_API_KEY não definida. "
            "Adicione a chave no Secret Manager e configure a env var no Cloud Run cmo-agent."
        )
        return (
            f"Busca web indisponível: TAVILY_API_KEY não configurada. "
            f"Crie uma conta em tavily.com, obtenha a API key e adicione ao Secret Manager do projeto."
        )

    url = "https://api.tavily.com/search"
    payload = _json.dumps({
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
        "max_results": min(max_results, 10),
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "eozore-cmo-agent/2.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = _json.loads(response.read().decode("utf-8"))

        results_raw = data.get("results", [])
        if not results_raw:
            return f"Nenhum resultado web encontrado para '{query}'."

        results_text = ""
        for i, item in enumerate(results_raw[:max_results]):
            title   = item.get("title", "").strip()
            url_    = item.get("url", "").strip()
            content = item.get("content", "").strip()
            # Trunca conteúdo para evitar tokens excessivos
            snippet = content[:300] + ("..." if len(content) > 300 else "")
            results_text += f"{i+1}. {title}\n   URL: {url_}\n   Resumo: {snippet}\n\n"

        logger.info(f"[tools] Tavily search OK: {len(results_raw)} resultados para '{query}'")
        return f"=== RESULTADOS DA WEB PARA: '{query}' ===\n\n{results_text}"

    except Exception as e:
        logger.error(f"[tools] Tavily search error: {e}")
        return f"Falha ao realizar busca web por '{query}': {str(e)}"


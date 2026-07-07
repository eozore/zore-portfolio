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
try:
    db = firestore.client()
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

    Args:
        query: O termo de busca (ex: "Vertex AI agent architecture", "FastAPI best practices").
        max_results: Número máximo de resultados (padrão: 5).
    """
    safe_query = urllib.parse.quote(query)
    url = f"https://html.duckduckgo.com/html/?q={safe_query}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            
        results = []
        blocks = re.findall(r'<div class="result__body">([\s\S]*?)</div>\s*</div>', html)
        for block in blocks[:max_results]:
            title_match = re.search(r'<a class="result__url"[^>]*>([\s\S]*?)</a>', block)
            snippet_match = re.search(r'<a class="result__snippet"[^>]*>([\s\S]*?)</a>', block)
            
            title = re.sub(r'<[^>]*>', '', title_match.group(1)).strip() if title_match else ''
            snippet = re.sub(r'<[^>]*>', '', snippet_match.group(1)).strip() if snippet_match else ''
            
            title = re.sub(r'\s+', ' ', title)
            snippet = re.sub(r'\s+', ' ', snippet)
            if title:
                results.append((title, snippet))
                
        if not results:
            return f"Nenhum resultado web encontrado para '{query}'."
            
        results_text = ""
        for i, (title, snippet) in enumerate(results):
            results_text += f"{i+1}. {title}\n   Resumo: {snippet}\n\n"
        return f"=== RESULTADOS DA WEB PARA: '{query}' ===\n\n{results_text}"
    except Exception as e:
        logger.error(f"Error fetching web search: {e}")
        return f"Falha ao realizar busca web por '{query}': {str(e)}"


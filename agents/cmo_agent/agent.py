# -*- coding: utf-8 -*-
"""
agent.py — FastAPI microservice orchestrating the CMO and its specialized subagents
"""

import os
import sys
import asyncio
import logging
import base64
import json
import subprocess
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Load .env file manually if it exists
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

# Bypass SSL verification locally to prevent certificate failures in urllib/requests (especially on macOS)
import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    logging.info("SSL verification bypass enabled for local environment.")
except AttributeError:
    pass

# Add the current folder to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from google.antigravity import Agent, LocalAgentConfig
from prompts import SYSTEM_INSTRUCTION
from tools import get_ecosystem_memory, fetch_trending_papers, get_article_by_slug, db
import db_paths
from fastapi import Header
import time

# Subagents imports
from research_agent import run_research, RESEARCH_INSTRUCTION
from writing_agent import stream_writing, WRITING_INSTRUCTION, stream_youtube_script, YOUTUBE_SCRIPT_INSTRUCTION
from distribution_agent import run_distribution, DISTRIBUTION_INSTRUCTION
from critic_agent import run_critic, CRITIC_INSTRUCTION
from speak_extractor_agent import extract_spoken_text
from model_config import get_model_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cmo_agent")

app = FastAPI(title="éozoré CMO Agent Service (Multi-Agent)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background Worker Tasks Registers
GENERATION_QUEUES = {}
ACTIVE_GENERATIONS = {}

# ── Pydantic Request/Response Models ──────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    text: str

class InterviewRequest(BaseModel):
    messages: List[ChatMessage]
    sessionId: str
    category: Optional[str] = "ml"

class GenerateRequest(BaseModel):
    topic: str
    context: Optional[str] = None
    format: str
    category: str
    language: str
    sessionId: Optional[str] = None

class RepurposeRequest(BaseModel):
    title: str
    slug: Optional[str] = None
    content: str
    category: str
    youtubeScript: Optional[str] = None
    language: Optional[str] = "pt-BR"

class YouTubeRequest(BaseModel):
    title: str
    content: str
    category: str
    language: Optional[str] = "pt-BR"
    sessionId: Optional[str] = None

class PubSubMessage(BaseModel):
    data: str
    messageId: Optional[str] = None
    publishTime: Optional[str] = None

class PubSubRequest(BaseModel):
    message: PubSubMessage
    subscription: Optional[str] = None

# ── Firestore Dynamic Configs ──────────────────────────────────────────────────

def get_dynamic_agent_config(agent_name: str, fallback_prompt: str) -> str:
    """
    Recupera as instruções do sistema (prompts) diretamente do Firestore para permitir
    mudanças em tempo real sem deploy. Se não estiver configurado ou ocorrer falha,
    utiliza o fallback local codificado no código.
    """
    if db is None:
        logger.warning(f"Firestore not initialized. Using local fallback for {agent_name}")
        return fallback_prompt
        
    try:
        doc = db.document(db_paths.get_config_doc_path(agent_name)).get()
        if doc.exists:
            data = doc.to_dict()
            system_instruction = data.get("system_instruction")
            if system_instruction:
                logger.info(f"Loaded dynamic prompt for {agent_name} from Firestore")
                return system_instruction
        logger.info(f"Dynamic config for {agent_name} not found in Firestore. Using local fallback.")
    except Exception as e:
        logger.error(f"Error loading dynamic prompt for {agent_name} from Firestore: {e}. Using local fallback.")
        
    return fallback_prompt

def log_studio_execution(session_id: str, action: str, data: dict):
    """
    Grava os logs de teste e execução do estúdio localmente para facilitar auditorias rápidas
    """
    log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio_execution.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [Session: {session_id}] [Action: {action}]\n"
    
    if action == "interview":
        messages = data.get("messages", [])
        if messages:
            last_msg = messages[-1]
            log_line += f"  User Message: {last_msg.get('text')}\n"
        response_text = data.get("response", "")
        log_line += f"  CMO AI Response: {response_text[:300]}...\n"
    elif action == "generate_start":
        log_line += f"  Topic: {data.get('topic')}\n"
        log_line += f"  Context: {data.get('context')}\n"
    elif action == "critic_done":
        log_line += f"  Critic Notes: {data.get('critic_notes', '')[:400]}...\n"
    elif action == "research_done":
        log_line += f"  Research Notes: {data.get('research_notes', '')[:400]}...\n"
    elif action == "generate_error":
        log_line += f"  ERROR: {data.get('error')}\n"
    elif action == "repurpose":
        log_line += f"  Article Title: {data.get('title')}\n"
        log_line += f"  Repurposed Keys: {list(data.get('repurposed_data', {}).keys())}\n"
        
    log_line += "-" * 80 + "\n"
    
    try:
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        logger.warning(f"Failed to write to local studio execution log: {e}")

def update_generation_checkpoint(stage: str, progress_percent: int = None, status_text: str = None, error_msg: str = None):
    session_id = db_paths.get_session_id()
    if not session_id:
        return
    
    # 1. Update Firestore
    if db is not None:
        try:
            session_ref = db.collection(db_paths.get_sessions_path()).document(session_id)
            doc = session_ref.get()
            current_draft = {}
            if doc.exists:
                current_draft = doc.to_dict().get("draft", {}) or {}
                if not isinstance(current_draft, dict):
                    current_draft = {}
            
            checkpoint = current_draft.get("checkpoint", {}) or {}
            if not isinstance(checkpoint, dict):
                checkpoint = {}
                
            checkpoint["currentStage"] = stage
            if progress_percent is not None:
                checkpoint["progressPercent"] = progress_percent
            if status_text is not None:
                checkpoint["statusText"] = status_text
            if error_msg is not None:
                checkpoint["error"] = error_msg
                
            current_draft["checkpoint"] = checkpoint
            session_ref.set({"draft": current_draft}, merge=True)
            logger.info(f"[checkpoint] Firestore stage updated: {stage} ({progress_percent or 0}%)")
        except Exception as e:
            logger.warning(f"Failed to update Firestore checkpoint: {e}")
            
    # 2. Update Local Project state
    try:
        project_dir = db_paths.get_local_project_dir(session_id)
        os.makedirs(project_dir, exist_ok=True)
        state_file = os.path.join(project_dir, "project_state.json")
        
        state_data = {}
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                try:
                    state_data = json.load(f)
                except Exception:
                    pass
                    
        checkpoint_data = state_data.get("checkpoint", {}) or {}
        if not isinstance(checkpoint_data, dict):
            checkpoint_data = {}
            
        checkpoint_data["currentStage"] = stage
        if progress_percent is not None:
            checkpoint_data["progressPercent"] = progress_percent
        if status_text is not None:
            checkpoint_data["statusText"] = status_text
        if error_msg is not None:
            checkpoint_data["error"] = error_msg
            
        state_data["checkpoint"] = checkpoint_data
        state_data["updatedAt"] = datetime.utcnow().isoformat()
        
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[checkpoint] Local project state updated: {state_file}")
    except Exception as e:
        logger.warning(f"Failed to update local project state file: {e}")

def log_python_usage(stage: str, model_name: str, prompt_text: str, response_text: str, latency_ms: int):
    if db is None:
        return
        
    # Estimativa de tokens baseada em caracteres (1 token ~= 3.5 caracteres)
    input_tokens = max(1, len(prompt_text) // 3)
    output_tokens = max(1, len(response_text) // 3)
    
    cost_input = (input_tokens * 0.075) / 1000000.0
    cost_output = (output_tokens * 0.30) / 1000000.0
    estimated_cost_usd = cost_input + cost_output
    
    try:
        logs_ref = db.collection(db_paths.get_usage_logs_path())
        logs_ref.add({
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "stage": stage,
            "model": model_name,
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "estimatedCostUsd": estimated_cost_usd,
            "latencyMs": latency_ms
        })
        logger.info(f"[usage] Logged cost of ${estimated_cost_usd:.6f} for stage {stage} in path {db_paths.get_usage_logs_path()}")
    except Exception as e:
        logger.warning(f"Failed to log usage metrics to Firestore: {e}")

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "sdk": "google-antigravity", "multi_agent": True}

@app.post("/interview")
async def interview_endpoint(req: InterviewRequest, x_tenant_id: Optional[str] = Header(None)):
    db_paths.set_tenant_id(x_tenant_id)
    db_paths.set_session_id(req.sessionId)
    session_id = req.sessionId
    messages = req.messages
    is_first_turn = len(messages) == 0

    save_dir = os.path.join("/tmp", "cmo_sessions")
    os.makedirs(save_dir, exist_ok=True)

    # 1. Check Firestore mapping for an existing Python AGY conversation ID
    python_conv_id = None
    if db is not None:
        try:
            session_ref = db.collection(db_paths.get_sessions_path()).document(session_id)
            doc = session_ref.get()
            if doc.exists:
                python_conv_id = doc.to_dict().get("pythonConversationId")
        except Exception as e:
            logger.warning(f"Failed to fetch session doc from Firestore: {e}")

    # 2. Check if the local trajectory directory exists on this container instance
    local_session_exists = False
    if python_conv_id:
        local_path = os.path.join(save_dir, python_conv_id)
        if os.path.exists(local_path):
            local_session_exists = True

    # Use the existing conversation_id if present locally, otherwise start a new one
    active_conv_id = python_conv_id if local_session_exists else None
    logger.info(f"Session {session_id} - python_conv_id: {python_conv_id}, local_exists: {local_session_exists} -> using active_conv_id: {active_conv_id}")

    models_config = get_model_config()

    config = LocalAgentConfig(
        system_instructions=SYSTEM_INSTRUCTION,
        tools=[get_ecosystem_memory, fetch_trending_papers, get_article_by_slug],
        conversation_id=active_conv_id,
        save_dir=save_dir,
        models=models_config,
    )

    try:
        async with Agent(config=config) as agent:
            # Save the mapping if a new conversation ID was generated by the harness
            generated_conv_id = agent.conversation_id
            if generated_conv_id and generated_conv_id != python_conv_id and db is not None:
                try:
                    logger.info(f"Saving new pythonConversationId {generated_conv_id} mapping for session {session_id}")
                    db.collection(db_paths.get_sessions_path()).document(session_id).set(
                        {"pythonConversationId": generated_conv_id},
                        merge=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to update pythonConversationId in Firestore: {e}")

            if is_first_turn:
                prompt = "Olá! Vamos começar nossa reunião de pauta da semana. Qual tema você tem em mente?"
            else:
                last_user_msg = messages[-1].text if messages[-1].role == "user" else ""
                
                # Check if the local trajectory has steps. If not (e.g. stateless reload),
                # we feed the entire conversation log as context so the model knows the state.
                has_history = len(agent.conversation.history) > 0
                if not has_history:
                    logger.info(f"Trajectory for session {session_id} not found in container. Reseeding with request history.")
                    if len(messages) == 1:
                        prompt = last_user_msg
                    else:
                        dialogue_transcript = "\n\n".join([
                            f"{'CEO (Victor)' if m.role == 'user' else 'CMO AI'}: {m.text}"
                            for m in messages[:-1]
                        ])
                        prompt = (
                            f"TRANSCRIÇÃO DO DIÁLOGO ATÉ AGORA:\n\n{dialogue_transcript}\n\n"
                            f"Victor (CEO) diz: {last_user_msg}\n\n"
                            "Responda como o CMO AI de forma informal, direta, focada e ágil."
                        )
                else:
                    prompt = last_user_msg

            logger.info(f"Sending prompt to Antigravity Agent: {prompt[:100]}...")
            response = await agent.chat(prompt)
            response_text = await response.text()
            logger.info(f"Antigravity Agent response completed: {len(response_text)} characters.")
            
            # Local studio log mapping
            log_studio_execution(session_id, "interview", {
                "messages": [m.dict() for m in messages], 
                "response": response_text
            })
            
            log_python_usage("cmo_interview", "gemini-1.5-flash", prompt, response_text, 1000)
            
            return {"text": response_text}

    except Exception as e:
        logger.exception("Error running Antigravity Agent")
        raise HTTPException(status_code=500, detail=str(e))

async def run_article_generation_pipeline(req: GenerateRequest, x_tenant_id: str):
    session_id = req.sessionId
    db_paths.set_tenant_id(x_tenant_id)
    db_paths.set_session_id(session_id)

    # BUG FIX #1: Do NOT capture the queue once — read it dynamically from the
    # global registry at every put() so that a client reconnect (which replaces
    # the queue in GENERATION_QUEUES) still receives all future events.
    def get_queue():
        return GENERATION_QUEUES.get(session_id)
    
    try:
        log_studio_execution("generate", "generate_start", {"topic": req.topic, "context": req.context})
        update_generation_checkpoint("researching", 10, "Analisando referências e estruturando pauta...")

        # 1. Carrega prompts dinâmicos do Firestore
        dynamic_critic_prompt = get_dynamic_agent_config("critic_agent", CRITIC_INSTRUCTION)
        dynamic_research_prompt = get_dynamic_agent_config("research_agent", RESEARCH_INSTRUCTION)
        dynamic_writing_prompt = get_dynamic_agent_config("writing_agent", WRITING_INSTRUCTION)

        # Fase 1: Análise Crítica
        update_generation_checkpoint("researching", 20, "Alinhando consistência teórica com o Critic Agent...")
        start_time = time.time()
        critic_notes = await run_critic(req.topic, req.context or "", dynamic_critic_prompt)
        log_studio_execution("generate", "critic_done", {"critic_notes": critic_notes})
        log_python_usage("article_critic", "gemini-1.5-flash", req.topic, critic_notes, int((time.time() - start_time) * 1000))

        # Fase 2: Pesquisa Avançada
        update_generation_checkpoint("researching", 40, "Buscando referências científicas no arXiv...")
        start_time = time.time()
        research_notes = await run_research(req.topic, req.context or "", critic_notes, dynamic_research_prompt)
        log_studio_execution("generate", "research_done", {"research_notes": research_notes})
        log_python_usage("article_research", "gemini-1.5-flash", req.topic, research_notes, int((time.time() - start_time) * 1000))
        
        # Fase 3: Redação do Artigo
        update_generation_checkpoint("writing", 60, "Escrevendo rascunho com o Writer Agent...")
        context_with_critic = (req.context or "") + f"\n\n{critic_notes}"
        
        start_writing_time = time.time()
        response, agent = await stream_writing(
            req.topic, 
            context_with_critic, 
            research_notes, 
            dynamic_writing_prompt
        )
        
        full_text = ""
        try:
            async for token in response:
                full_text += token
                q = get_queue()
                if q:
                    await q.put({"type": "content", "chunk": token})
        finally:
            if agent is not None:
                await agent.__aexit__(None, None, None)
            
        log_python_usage("article_generation", "gemini-1.5-flash", req.topic, full_text, int((time.time() - start_writing_time) * 1000))
        update_generation_checkpoint("coding", 85, "Executando sandbox e gerando gráficos...")

        # Fase 4: Execução do Ambiente de Código
        from code_executor import post_process_article_plots
        processed_text = post_process_article_plots(full_text)
        if processed_text != full_text:
            logger.info("Código executado e gráficos gerados com sucesso!")
            full_text = processed_text
            
        # BUG FIX #2: Always clean thoughts and META blocks, then ALWAYS send a
        # final `replace` event with the fully-cleaned content so the editor
        # never shows raw META or <think> blocks, regardless of plot execution.
        import re
        cleaned_text = re.sub(r"<think>[\s\S]*?<\/think>", "", full_text).strip()
        # Use multiline flag to match META anywhere (not just at the very end)
        cleaned_text = re.sub(r"\n?META:\s*\{[^}]+\}[\s]*", "", cleaned_text, flags=re.MULTILINE).strip()

        # Parse META block values to save title/slug
        meta_match = re.search(r"META:\s*(\{[^}]+\})", full_text)
        title = req.topic
        slug = req.topic.lower().replace(" ", "-")
        read_time = 10
        if meta_match:
            try:
                # Remove trailing commas
                cleaned_meta = re.sub(r",\s*([}\]])", r"\1", meta_match.group(1))
                meta = json.loads(cleaned_meta)
                title = meta.get("title") or title
                slug = meta.get("slug") or slug
                read_time = meta.get("readTime") or read_time
            except Exception:
                pass

        # Always send a final replace event with fully-cleaned content
        q = get_queue()
        if q:
            await q.put({"type": "replace", "content": cleaned_text})
            await q.put({"type": "meta", "title": title, "slug": slug, "readTime": read_time})

        # Write all final project assets to local workspace directory
        project_dir = db_paths.get_local_project_dir(session_id)
        os.makedirs(project_dir, exist_ok=True)
        article_file = os.path.join(project_dir, "article.md")
        with open(article_file, "w", encoding="utf-8") as f:
            f.write(cleaned_text)
        logger.info(f"Article file saved locally to {article_file}")

        # Settle final draft state in Firestore
        if db is not None:
            try:
                session_ref = db.collection(db_paths.get_sessions_path()).document(session_id)
                session_ref.set({
                    "draft": {
                        "generatedContent": cleaned_text,
                        "suggestedTitle": title,
                        "suggestedSlug": slug,
                        "estimatedReadTime": read_time,
                        "checkpoint": {
                            "currentStage": "done",
                            "progressPercent": 100,
                            "statusText": "Artigo completo pronto para publicação!"
                        }
                    }
                }, merge=True)
            except Exception as fe:
                logger.warning(f"Failed to save final draft state to Firestore: {fe}")

        update_generation_checkpoint("done", 100, "Geração de conteúdo concluída!")
        q = get_queue()
        if q:
            await q.put("[DONE]")
            
    except Exception as e:
        logger.exception("Error during background generate task")
        log_studio_execution("generate", "generate_error", {"error": str(e)})
        update_generation_checkpoint("error", 100, f"Erro: {str(e)}", error_msg=str(e))
        q = get_queue()
        if q:
            await q.put({"type": "error", "message": str(e)})
            await q.put("[DONE]")
    finally:
        ACTIVE_GENERATIONS.pop(session_id, None)

async def run_youtube_generation_pipeline(req: YouTubeRequest, x_tenant_id: str, session_id: str):
    db_paths.set_tenant_id(x_tenant_id)
    db_paths.set_session_id(session_id)

    # BUG FIX #1 (YouTube variant): Dynamic queue lookup so reconnecting clients
    # on a new SSE connection can still receive all future events from this task.
    def get_queue():
        return GENERATION_QUEUES.get(f"yt_{session_id}")
    
    try:
        log_studio_execution("youtube", "youtube_start", {"title": req.title})
        update_generation_checkpoint("writing_script", 30, "Gerando roteiro detalhado do YouTube...")
        
        dynamic_youtube_prompt = get_dynamic_agent_config("youtube_script", YOUTUBE_SCRIPT_INSTRUCTION)
        
        start_time = time.time()
        response, agent = await stream_youtube_script(
            req.title,
            req.category,
            req.content,
            req.language or "pt-BR",
            system_instruction=dynamic_youtube_prompt
        )
        
        full_text = ""
        try:
            async for token in response:
                full_text += token
                q = get_queue()
                if q:
                    await q.put({"type": "content", "chunk": token})
        finally:
            if agent is not None:
                await agent.__aexit__(None, None, None)
                
        log_python_usage("youtube_script", "gemini-1.5-flash", req.title, full_text, int((time.time() - start_time) * 1000))
        
        # BUG FIX #2 (YouTube): Clean thoughts and META then always send replace
        import re
        cleaned_script = re.sub(r"<think>[\s\S]*?<\/think>", "", full_text).strip()
        cleaned_script = re.sub(r"\n?META:\s*\{[^}]+\}[\s]*", "", cleaned_script, flags=re.MULTILINE).strip()

        # Always send final replace with clean content
        q = get_queue()
        if q:
            await q.put({"type": "replace", "content": cleaned_script})
        
        # Write to local project directory
        project_dir = db_paths.get_local_project_dir(session_id)
        os.makedirs(project_dir, exist_ok=True)
        script_file = os.path.join(project_dir, "youtube_script.md")
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(cleaned_script)
        logger.info(f"YouTube script saved locally to {script_file}")
        
        # Update draft in Firestore
        if db is not None:
            try:
                session_ref = db.collection(db_paths.get_sessions_path()).document(session_id)
                session_ref.set({
                    "draft": {
                        "youtubeScript": cleaned_script,
                    }
                }, merge=True)
            except Exception as fe:
                logger.warning(f"Failed to update youtubeScript draft in Firestore: {fe}")
                
        update_generation_checkpoint("done", 100, "Roteiro do YouTube gerado com sucesso!")
        q = get_queue()
        if q:
            await q.put("[DONE]")
            
    except Exception as e:
        logger.exception("Error during background youtube task")
        log_studio_execution("youtube", "youtube_error", {"error": str(e)})
        update_generation_checkpoint("error", 100, f"Erro: {str(e)}", error_msg=str(e))
        q = get_queue()
        if q:
            await q.put({"type": "error", "message": str(e)})
            await q.put("[DONE]")
    finally:
        ACTIVE_GENERATIONS.pop(f"yt_{session_id}", None)

@app.post("/generate")
async def generate_endpoint(req: GenerateRequest, x_tenant_id: Optional[str] = Header(None)):
    """
    Roteia para o Critic Agent, Research Agent, e então para o Writing Agent em background.
    Mantém SSE de streaming conectável. Se desconectar, o processamento de background continua.
    """
    db_paths.set_tenant_id(x_tenant_id)
    session_id = req.sessionId or "default_session"
    db_paths.set_session_id(session_id)
    
    # Initialize queue
    GENERATION_QUEUES[session_id] = asyncio.Queue()
    
    # Spawn background execution if not already running
    if session_id not in ACTIVE_GENERATIONS:
        task = asyncio.create_task(run_article_generation_pipeline(req, x_tenant_id))
        ACTIVE_GENERATIONS[session_id] = task
        
    async def event_generator():
        queue = GENERATION_QUEUES.get(session_id)
        if not queue:
            yield "data: [DONE]\n\n"
            return
            
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                if event == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Check if task finished
                task = ACTIVE_GENERATIONS.get(session_id)
                if not task or task.done():
                    # Check if queue is empty
                    if queue.empty():
                        yield "data: [DONE]\n\n"
                        break
                        
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/youtube")
async def youtube_endpoint(req: YouTubeRequest, x_tenant_id: Optional[str] = Header(None)):
    """
    Roteia para o YouTube Agent em background para gerar o roteiro e alimentar o streaming queue.
    """
    db_paths.set_tenant_id(x_tenant_id)
    # BUG FIX #3: Use sessionId from the request body (set by the frontend) instead of
    # relying on the module-level db_paths variable which is shared across concurrent requests.
    session_id = req.sessionId or db_paths.get_session_id() or f"yt_sess_{int(time.time())}"
    
    # Initialize queue
    GENERATION_QUEUES[f"yt_{session_id}"] = asyncio.Queue()
    
    if f"yt_{session_id}" not in ACTIVE_GENERATIONS:
        task = asyncio.create_task(run_youtube_generation_pipeline(req, x_tenant_id, session_id))
        ACTIVE_GENERATIONS[f"yt_{session_id}"] = task
        
    async def event_generator():
        queue = GENERATION_QUEUES.get(f"yt_{session_id}")
        if not queue:
            yield "data: [DONE]\n\n"
            return
            
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                if event == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                task = ACTIVE_GENERATIONS.get(f"yt_{session_id}")
                if not task or task.done():
                    if queue.empty():
                        yield "data: [DONE]\n\n"
                        break
                        
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/repurpose")
async def repurpose_endpoint(req: RepurposeRequest, x_tenant_id: Optional[str] = Header(None)):
    """
    Roteia para o Distribution Agent para obter derivações estruturadas das redes sociais
    baseadas no artigo e no roteiro do YouTube aprovados. Retorna resposta síncrona estruturada.
    """
    try:
        db_paths.set_tenant_id(x_tenant_id)
        logger.info(f"Triggering distribution agent synchronously for: {req.title}")
        slug = req.slug or "artigo"
        language = req.language or "pt-BR"
        dynamic_distribution_prompt = get_dynamic_agent_config("distribution_agent", DISTRIBUTION_INSTRUCTION)
        start_time = time.time()
        data = await run_distribution(
            req.title, 
            slug, 
            req.content, 
            req.category, 
            language, 
            system_instruction=dynamic_distribution_prompt,
            youtube_script=req.youtubeScript
        )
        log_python_usage("social_repurpose", "gemini-1.5-flash", req.title, json.dumps(data), int((time.time() - start_time) * 1000))
        return data
    except Exception as e:
        logger.exception("Failed to run distribution agent")
        raise HTTPException(status_code=500, detail=str(e))

# ── Pub/Sub Queue Flow and Background Worker ──────────────────────────────────

def save_repurposed_to_firestore(article_title: str, article_slug: str, data: dict):
    if db is None:
        logger.error("Firestore not initialized, cannot save social queue items.")
        return
        
    now = datetime.utcnow()
    batch = db.batch()
    
    # Helper to calculate dates
    def get_iso(days_add: int, hour: int) -> str:
        d = now + timedelta(days=days_add)
        return d.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat() + "Z"
        
    # 1. LinkedIn
    for i, item in enumerate(data.get("linkedinPosts", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"li_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "linkedin",
            "format": "image",
            "title": item.get("hook", ""),
            "copy": item.get("copy", ""),
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso((i % 5) + 1, 9 + i)
        })
        
    # 2. YouTube
    for i, item in enumerate(data.get("youtubeScripts", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"yt_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "youtube",
            "format": "video",
            "title": item.get("title", ""),
            "copy": item.get("script", ""),
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso(3, 18 + i)
        })
        
    # 3. Reels
    for i, item in enumerate(data.get("reelsScripts", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"re_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "instagram",
            "format": "reel",
            "title": item.get("title", ""),
            "hook3s": item.get("hook3s", ""),
            "visualCue": item.get("visualCue", ""),
            "copy": item.get("script", ""),
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso((i % 5) + 1, 12 + i)
        })
        
    # 4. Carousels
    for i, item in enumerate(data.get("carousels", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"ca_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "instagram",
            "format": "carousel",
            "title": item.get("title", ""),
            "copy": item.get("caption", ""),
            "slides": item.get("slides", []),
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso((i % 5) + 1, 14 + i)
        })
        
    # 5. Stories
    for i, item in enumerate(data.get("storiesIdeas", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"st_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "instagram",
            "format": "story",
            "title": item.get("interactiveElement") or item.get("angle", ""),
            "copy": f"{item.get('day', '')}: {item.get('copy', '')}",
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso((i % 5) + 1, 8 + (i % 12))
        })
 
    # 6. YouTube Shorts
    for i, item in enumerate(data.get("youtubeShorts", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"yts_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "youtube",
            "format": "shorts",
            "title": item.get("title", ""),
            "hook3s": item.get("hook3s", ""),
            "copy": item.get("script", ""),
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso((i % 5) + 1, 15 + i)
        })
 
    # 7. Image Posts (Texto + Imagem)
    for i, item in enumerate(data.get("imagePosts", [])):
        doc_ref = db.collection(db_paths.get_social_queue_path()).document(f"img_{item.get('id', i)}")
        batch.set(doc_ref, {
            "platform": "instagram",
            "format": "post_imagem",
            "title": item.get("title", ""),
            "imageDescription": item.get("imageDescription", ""),
            "copy": item.get("copy", ""),
            "status": "em_revisao",
            "articleSlug": article_slug,
            "articleTitle": article_title,
            "scheduled_at": get_iso((i % 5) + 1, 11 + i)
        })
        
    batch.commit()
    logger.info(f"Saved repurposed social campaigns to social_queue Firestore collection (LinkedIn, YouTube, Reels, Carousels, Stories, Shorts, ImagePosts)")

async def async_repurpose_and_save(title: str, slug: str, content: str, category: str, language: str, tenant_id: Optional[str] = None):
    try:
        db_paths.set_tenant_id(tenant_id)
        logger.info(f"Background task starting social repurposing for: {slug}")
        dynamic_distribution_prompt = get_dynamic_agent_config("distribution_agent", DISTRIBUTION_INSTRUCTION)
        start_time = time.time()
        repurposed_data = await run_distribution(
            title, 
            slug, 
            content, 
            category, 
            language, 
            system_instruction=dynamic_distribution_prompt
        )
        log_python_usage("social_repurpose", "gemini-1.5-flash", title, json.dumps(repurposed_data), int((time.time() - start_time) * 1000))
        save_repurposed_to_firestore(title, slug, repurposed_data)
        logger.info(f"Background task completed successfully for: {slug}")
    except Exception as e:
        logger.exception(f"Background task failed for: {slug}")

@app.post("/pubsub/subscription")
async def pubsub_subscription(req: PubSubRequest, background_tasks: BackgroundTasks, x_tenant_id: Optional[str] = Header(None)):
    """
    Consome mensagens assíncronas do Pub/Sub. Decodifica o envelope Pub/Sub,
    extrai os metadados do artigo, executa o agente de distribuição em segundo plano,
    e persiste todas as derivações no Firestore.
    """
    db_paths.set_tenant_id(x_tenant_id)
    try:
        decoded_data = base64.b64decode(req.message.data).decode('utf-8')
        payload = json.loads(decoded_data)
    except Exception as e:
        logger.exception("Failed to decode Pub/Sub message data")
        raise HTTPException(status_code=400, detail=f"Invalid base64 or JSON envelope: {str(e)}")

    title = payload.get("title")
    slug = payload.get("slug")
    content = payload.get("content")
    category = payload.get("category")
    language = payload.get("language", "pt-BR")

    if not title or not content:
        raise HTTPException(status_code=400, detail="title and content fields are required in message data payload")

    # Enqueue heavy task to background executor
    background_tasks.add_task(async_repurpose_and_save, title, slug, content, category, language, x_tenant_id)
    logger.info(f"Enqueued background repurposing for article '{title}' via Pub/Sub subscription")

    return {"status": "processing", "message": "Derivation campaign processing enqueued"}

# Video rendering status registry
VIDEO_JOBS = {}

class RenderMotionRequest(BaseModel):
    itemId: str
    scenes: str
    format: Optional[str] = "vertical"
    sessionId: Optional[str] = None

class MergeVideoRequest(BaseModel):
    avatarVideoUrl: str
    motionVideoUrl: Optional[str] = None
    sessionId: Optional[str] = None
    itemId: Optional[str] = None
    format: Optional[str] = "vertical"
    script: Optional[str] = None

class RetryMergeRequest(BaseModel):
    avatarVideoUrl: str
    motionVideoUrl: str
    sessionId: Optional[str] = None
    itemId: Optional[str] = None
    format: Optional[str] = "vertical"
    script: Optional[str] = None

class GenerateImagePostRequest(BaseModel):
    title: str
    imageDescription: str
    copy: str
    sessionId: Optional[str] = None
    itemId: Optional[str] = None

IS_CLOUD = "K_SERVICE" in os.environ or os.environ.get("FIREBASE_PROJECT_ID") is not None

def upload_to_storage_if_cloud(local_file_path: str, destination_blob_name: str) -> Optional[str]:
    """
    Se estiver rodando em nuvem, faz o upload do arquivo para o bucket do Google Cloud Storage
    e retorna a URL pública HTTP. Caso contrário (local), retorna None.
    """
    if not IS_CLOUD:
        return None
    try:
        from firebase_admin import storage
        project_id = os.environ.get("FIREBASE_PROJECT_ID") or "vazfy-417019"
        bucket_name = f"{project_id}-assets"
        bucket = storage.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        logger.info(f"[storage] Fazendo upload de {local_file_path} para gs://{bucket_name}/{destination_blob_name}...")
        blob.upload_from_filename(local_file_path)
        public_url = f"https://storage.googleapis.com/{bucket_name}/{destination_blob_name}"
        logger.info(f"[storage] Upload concluído! URL Pública: {public_url}")
        return public_url
    except Exception as e:
        logger.exception("[storage] Falha no upload para Cloud Storage")
        return None

def get_public_video_dir(session_id: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    public_dir = os.path.join(base_dir, "apps", "web", "public", "videos", session_id)
    return public_dir

def async_render_motion_graphics(job_id: str, scenes_md: str, format_type: str, session_id: str, tenant_id: str):
    db_paths.set_tenant_id(tenant_id)
    db_paths.set_session_id(session_id)
    VIDEO_JOBS[job_id] = {"status": "processing", "progress": 10}
    
    try:
        from video_editor import parse_markdown_to_scenes, generate_scene_slide
        scenes = parse_markdown_to_scenes(scenes_md)
        if not scenes:
            raise Exception("No scenes found in script markdown.")
            
        project_dir = db_paths.get_local_project_dir(session_id)
        os.makedirs(project_dir, exist_ok=True)
        
        # 1. Generate PNG slides
        slide_paths = []
        for idx, scene in enumerate(scenes):
            VIDEO_JOBS[job_id]["progress"] = int(10 + (idx / len(scenes)) * 40)
            slide_path = generate_scene_slide(scene, idx, project_dir, format=format_type)
            slide_paths.append(slide_path)
            
        # 2. Concat demuxer script
        concat_file = os.path.join(project_dir, "input.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for idx, slide in enumerate(slide_paths):
                f.write(f"file '{slide}'\n")
                f.write(f"duration 4.0\n")  # Static 4s fallback duration for preview
            if slide_paths:
                f.write(f"file '{slide_paths[-1]}'\n")
                
        # 3. Render MP4 green screen overlay
        motion_path = os.path.join(project_dir, "motion_greenscreen.mp4")
        cmd_motion = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-vsync", "vfr", "-pix_fmt", "yuv420p", "-c:v", "libx264", motion_path
        ]
        VIDEO_JOBS[job_id]["progress"] = 70
        
        proc = subprocess.run(cmd_motion, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise Exception(f"FFmpeg motion compile failed: {proc.stderr.decode('utf-8')}")
            
        # 4. Copy to Next.js public path (local) or upload to Storage (cloud)
        import shutil
        cloud_url = upload_to_storage_if_cloud(motion_path, f"{session_id}/motion_{job_id}.mp4")
        if cloud_url:
            motion_url = cloud_url
        else:
            public_dir = get_public_video_dir(session_id)
            os.makedirs(public_dir, exist_ok=True)
            public_motion = os.path.join(public_dir, "motion.mp4")
            shutil.copy2(motion_path, public_motion)
            motion_url = f"/videos/{session_id}/motion.mp4"
            
        VIDEO_JOBS[job_id] = {
            "status": "completed",
            "progress": 100,
            "motionUrl": motion_url
        }
        logger.info(f"Background motion graphics render completed: {motion_url}")
    except Exception as e:
        logger.exception("Background motion graphics render failed")
        VIDEO_JOBS[job_id] = {"status": "failed", "progress": 100, "error": str(e)}

def async_merge_video_fusion(job_id: str, avatar_url: str, session_id: str, format_type: str, tenant_id: str, script: Optional[str] = None, motion_url: Optional[str] = None):
    db_paths.set_tenant_id(tenant_id)
    db_paths.set_session_id(session_id)
    VIDEO_JOBS[job_id] = {"status": "processing", "progress": 5, "avatarVideoUrl": avatar_url, "motionVideoUrl": motion_url}
    
    try:
        import asyncio as _asyncio
        import shutil
        
        project_dir = db_paths.get_local_project_dir(session_id)
        video_dir = os.path.join(project_dir, "videos")
        os.makedirs(video_dir, exist_ok=True)
        
        avatar_local = os.path.join(video_dir, "avatar.mp4")
        
        # 1. Download Avatar Video
        VIDEO_JOBS[job_id]["progress"] = 15
        if avatar_url.startswith("http"):
            logger.info(f"Downloading avatar from {avatar_url}...")
            subprocess.run(["curl", "-L", "-k", "-o", avatar_local, avatar_url], check=True)
        else:
            logger.info("Using simulated local fallback avatar video...")
            test_url = "https://www.w3schools.com/html/mov_bbb.mp4"
            subprocess.run(["curl", "-L", "-k", "-o", avatar_local, test_url], check=True)
            
        # 2. Load Scenes from script
        script_file = os.path.join(project_dir, f"{job_id}_script.md")
        if script:
            script_text = script
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(script_text)
        else:
            script_file_orig = os.path.join(project_dir, "youtube_script.md")
            if os.path.exists(script_file_orig):
                with open(script_file_orig, "r", encoding="utf-8") as f:
                    script_text = f.read()
            else:
                script_text = ""
                if db is not None:
                    doc = db.collection(db_paths.get_sessions_path()).document(session_id).get()
                    if doc.exists:
                        script_text = doc.to_dict().get("draft", {}).get("youtubeScript", "")
                if not script_text:
                    raise Exception("Missing youtube_script.md file or draft context.")
                with open(script_file, "w", encoding="utf-8") as f:
                    f.write(script_text)
                
        from video_editor import parse_markdown_to_scenes, build_merged_video
        scenes = parse_markdown_to_scenes(script_text)
        if not scenes:
            raise Exception("No scenes found in script.")
            
        # 3. Call video editor fusion
        VIDEO_JOBS[job_id]["progress"] = 50
        final_merged = build_merged_video(avatar_local, scenes, project_dir, format=format_type)
        
        # 4. Copy to Next.js public directory (local) or upload to Storage (cloud)
        cloud_url = upload_to_storage_if_cloud(final_merged, f"{session_id}/final_{job_id}.mp4")
        if cloud_url:
            merged_video_url = cloud_url
        else:
            public_dir = get_public_video_dir(session_id)
            os.makedirs(public_dir, exist_ok=True)
            public_final = os.path.join(public_dir, "final.mp4")
            shutil.copy2(final_merged, public_final)
            merged_video_url = f"/videos/{session_id}/final.mp4"
        
        VIDEO_JOBS[job_id] = {
            "status": "completed",
            "progress": 100,
            "mergedVideoUrl": merged_video_url,
            "avatarVideoUrl": avatar_url,
            "motionVideoUrl": motion_url
        }
        logger.info(f"Background video fusion merge completed: {merged_video_url}")
    except Exception as e:
        logger.exception("Background video merge failed")
        VIDEO_JOBS[job_id] = {
            "status": "failed",
            "progress": 100,
            "error": str(e),
            "avatarVideoUrl": avatar_url,
            "motionVideoUrl": motion_url
        }


def async_retry_merge(job_id: str, avatar_url: str, motion_url: str, session_id: str, format_type: str, tenant_id: str, script: Optional[str] = None):
    """Retry de fusão usando vídeos já gerados (sem re-gerar HeyGen ou Motion)."""
    db_paths.set_tenant_id(tenant_id)
    db_paths.set_session_id(session_id)
    VIDEO_JOBS[job_id] = {"status": "processing", "progress": 5, "avatarVideoUrl": avatar_url, "motionVideoUrl": motion_url}
    
    try:
        import shutil
        
        project_dir = db_paths.get_local_project_dir(session_id)
        video_dir = os.path.join(project_dir, "videos")
        os.makedirs(video_dir, exist_ok=True)
        
        avatar_local = os.path.join(video_dir, "avatar.mp4")
        
        # 1. Re-use or re-download avatar (cheap — already have URL)
        if not os.path.exists(avatar_local):
            VIDEO_JOBS[job_id]["progress"] = 20
            if avatar_url.startswith("http"):
                logger.info(f"[retry-merge] Re-downloading avatar from {avatar_url}...")
                subprocess.run(["curl", "-L", "-k", "-o", avatar_local, avatar_url], check=True)
            else:
                raise Exception("avatar_local not found and URL not available for retry")
        else:
            logger.info(f"[retry-merge] Using cached avatar at {avatar_local}")
            VIDEO_JOBS[job_id]["progress"] = 25
            
        # 2. Load scenes
        script_text = script or ""
        if not script_text:
            script_file_orig = os.path.join(project_dir, "youtube_script.md")
            if os.path.exists(script_file_orig):
                with open(script_file_orig, "r", encoding="utf-8") as f:
                    script_text = f.read()
            if not script_text and db is not None:
                doc = db.collection(db_paths.get_sessions_path()).document(session_id).get()
                if doc.exists:
                    script_text = doc.to_dict().get("draft", {}).get("youtubeScript", "")
        
        from video_editor import parse_markdown_to_scenes, build_merged_video
        scenes = parse_markdown_to_scenes(script_text)
        if not scenes:
            raise Exception("No scenes found in script for retry-merge.")
            
        VIDEO_JOBS[job_id]["progress"] = 50
        final_merged = build_merged_video(avatar_local, scenes, project_dir, format=format_type)
        
        # 4. Copy to Next.js public directory (local) or upload to Storage (cloud)
        cloud_url = upload_to_storage_if_cloud(final_merged, f"{session_id}/final_{job_id}.mp4")
        if cloud_url:
            merged_video_url = cloud_url
        else:
            public_dir = get_public_video_dir(session_id)
            os.makedirs(public_dir, exist_ok=True)
            public_final = os.path.join(public_dir, "final.mp4")
            shutil.copy2(final_merged, public_final)
            merged_video_url = f"/videos/{session_id}/final.mp4"
        
        VIDEO_JOBS[job_id] = {
            "status": "completed",
            "progress": 100,
            "mergedVideoUrl": merged_video_url,
            "avatarVideoUrl": avatar_url,
            "motionVideoUrl": motion_url
        }
        logger.info(f"[retry-merge] Merge completed: {merged_video_url}")
    except Exception as e:
        logger.exception("[retry-merge] Merge failed")
        VIDEO_JOBS[job_id] = {
            "status": "failed",
            "progress": 100,
            "error": str(e),
            "avatarVideoUrl": avatar_url,
            "motionVideoUrl": motion_url
        }


def async_generate_image_post(job_id: str, title: str, image_description: str, copy: str, session_id: str, tenant_id: str, item_id: str = ""):
    """Gera uma imagem PNG para post_imagem usando PIL/HTML canvas."""
    import shutil
    
    db_paths.set_tenant_id(tenant_id)
    db_paths.set_session_id(session_id)
    VIDEO_JOBS[job_id] = {"status": "processing", "progress": 10}
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        
        # Canvas 1080x1080 (square post)
        W, H = 1080, 1080
        img = Image.new("RGB", (W, H), color=(10, 10, 20))  # dark background
        draw = ImageDraw.Draw(img)
        
        # Gradient-like background via rectangles
        for y in range(H):
            ratio = y / H
            r = int(10 + ratio * 20)
            g = int(10 + ratio * 5)
            b = int(30 + ratio * 40)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        
        # Accent bar
        draw.rectangle([(0, 0), (8, H)], fill=(124, 58, 237))  # purple accent
        
        # Brand label
        try:
            font_brand = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 64)
            font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        except Exception:
            font_brand = ImageFont.load_default()
            font_title = font_brand
            font_body = font_brand
            font_small = font_brand
        
        # éozoré logo text
        draw.text((60, 50), "éozoré • IA", fill=(124, 58, 237), font=font_brand)
        
        # Title (wrapped)
        wrapped_title = textwrap.fill(title, width=22)
        draw.text((60, 160), wrapped_title, fill=(255, 255, 255), font=font_title)
        
        # Visual description hint
        desc_y = 160 + (wrapped_title.count('\n') + 1) * 76 + 40
        draw.rectangle([(60, desc_y), (W - 60, desc_y + 2)], fill=(124, 58, 237, 100))
        desc_y += 20
        wrapped_desc = textwrap.fill(image_description[:200], width=48)
        draw.text((60, desc_y), wrapped_desc, fill=(148, 163, 184), font=font_small)
        
        # Footer domain
        draw.text((60, H - 80), "eozore.com", fill=(99, 102, 241), font=font_body)
        
        # Save
        project_dir = db_paths.get_local_project_dir(session_id)
        os.makedirs(project_dir, exist_ok=True)
        img_filename = f"image_post_{item_id or job_id}.png"
        img_path = os.path.join(project_dir, img_filename)
        img.save(img_path, "PNG")
        
        # Copy to Next.js public directory (local) or upload to Storage (cloud)
        cloud_url = upload_to_storage_if_cloud(img_path, f"{session_id}/{img_filename}")
        if cloud_url:
            image_url = cloud_url
        else:
            public_dir = get_public_video_dir(session_id)
            os.makedirs(public_dir, exist_ok=True)
            public_img = os.path.join(public_dir, img_filename)
            shutil.copy2(img_path, public_img)
            image_url = f"/videos/{session_id}/{img_filename}"
        
        VIDEO_JOBS[job_id] = {
            "status": "completed",
            "progress": 100,
            "imageUrl": image_url
        }
        logger.info(f"Image post generated: {image_url}")
    except Exception as e:
        logger.exception("Image post generation failed")
        VIDEO_JOBS[job_id] = {"status": "failed", "progress": 100, "error": str(e)}

@app.post("/render-motion")
async def render_motion_endpoint(req: RenderMotionRequest, background_tasks: BackgroundTasks, x_tenant_id: Optional[str] = Header(None)):
    session_id = req.sessionId or "default_session"
    job_id = f"job_motion_{int(time.time())}"
    background_tasks.add_task(
        async_render_motion_graphics,
        job_id,
        req.scenes,
        req.format or "vertical",
        session_id,
        x_tenant_id or ""
    )
    return {"success": True, "jobId": job_id}

@app.get("/render-motion")
async def check_render_motion(jobId: str):
    job = VIDEO_JOBS.get(jobId, {"status": "completed", "progress": 100, "motionUrl": "/videos/default/motion.mp4"})
    return job

@app.post("/merge-video")
async def merge_video_endpoint(req: MergeVideoRequest, background_tasks: BackgroundTasks, x_tenant_id: Optional[str] = Header(None)):
    session_id = req.sessionId or "default_session"
    job_id = f"job_merge_{int(time.time())}"
    background_tasks.add_task(
        async_merge_video_fusion,
        job_id,
        req.avatarVideoUrl,
        session_id,
        req.format or "vertical",
        x_tenant_id or "",
        req.script,
        req.motionVideoUrl
    )
    return {"success": True, "jobId": job_id}

@app.get("/merge-video")
async def check_merge_video(jobId: str):
    job = VIDEO_JOBS.get(jobId, {"status": "completed", "progress": 100, "mergedVideoUrl": "/videos/default/final.mp4"})
    return job

@app.post("/retry-merge")
async def retry_merge_endpoint(req: RetryMergeRequest, background_tasks: BackgroundTasks, x_tenant_id: Optional[str] = Header(None)):
    """Retenta apenas a etapa de fusão FFmpeg sem re-gerar vídeos do HeyGen ou Motion."""
    session_id = req.sessionId or "default_session"
    job_id = f"job_retry_{int(time.time())}"
    background_tasks.add_task(
        async_retry_merge,
        job_id,
        req.avatarVideoUrl,
        req.motionVideoUrl,
        session_id,
        req.format or "vertical",
        x_tenant_id or "",
        req.script
    )
    return {"success": True, "jobId": job_id}

@app.get("/retry-merge")
async def check_retry_merge(jobId: str):
    job = VIDEO_JOBS.get(jobId, {"status": "not_found"})
    return job

@app.post("/generate-image-post")
async def generate_image_post_endpoint(req: GenerateImagePostRequest, background_tasks: BackgroundTasks, x_tenant_id: Optional[str] = Header(None)):
    """Gera imagem PNG para post_imagem sem custo de API de imagem."""
    session_id = req.sessionId or "default_session"
    item_id = req.itemId or ""
    job_id = f"job_img_{item_id}_{int(time.time())}"
    background_tasks.add_task(
        async_generate_image_post,
        job_id,
        req.title,
        req.imageDescription,
        req.copy,
        session_id,
        x_tenant_id or "",
        item_id
    )
    return {"success": True, "jobId": job_id}

@app.get("/generate-image-post")
async def check_generate_image_post(jobId: str):
    job = VIDEO_JOBS.get(jobId, {"status": "not_found"})
    return job

if __name__ == "__main__":
    import uvicorn
    port = 8090
    uvicorn.run("agent:app", host="0.0.0.0", port=port)

class ExtractSpeakRequest(BaseModel):
    script: str

@app.post("/extract-speak")
async def extract_speak_endpoint(req: ExtractSpeakRequest):
    """
    Usa o speak_extractor_agent para limpar e converter o roteiro
    em português fonético para síntese de voz natural e profissional no HeyGen.
    """
    try:
        cleaned_speak = await extract_spoken_text(req.script)
        return {"success": True, "cleanedScript": cleaned_speak}
    except Exception as e:
        logger.exception("Failed to run speak extractor agent")
        # Fallback to simple regex/split clean to avoid failure
        import re
        lines = req.script.split('\n')
        fallback_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('>') or stripped.startswith('#') or stripped in ('---', '***', '==='):
                continue
            fallback_lines.append(stripped)
        fallback = ' '.join(fallback_lines)
        return {"success": False, "cleanedScript": fallback, "error": str(e)}

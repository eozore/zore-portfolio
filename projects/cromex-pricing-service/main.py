# projects/cromex-pricing-service/main.py

import os
import json
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import numpy as np
from google.cloud import storage, firestore

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cromex-pricing-service")

app = FastAPI(
    title="Cromex Pricing Intelligence API",
    description="Microserviço responsável por rodar os cálculos de CM1 e Aderência para Cromex no GCP.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Env config for GCP
BUCKET_NAME = os.getenv("GCP_STORAGE_BUCKET")
IS_LOCAL = os.getenv("IS_LOCAL", "true").lower() == "true"

# Define base directories for local fallback
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOCAL_DATAINPUT = os.path.join(BASE_DIR, 'tool-cromex', 'datainput')
LOCAL_DATAOUTPUT = os.path.join(BASE_DIR, 'tool-cromex', 'dataoutput')

class PricingParams(BaseModel):
    pe_linear: float = 202.0
    pe_baixa: float = 217.0
    pp: float = 184.0
    month_ref: str = "2026-07"

def get_file_content(filename: str) -> str:
    """Helper to resolve paths dynamically."""
    if IS_LOCAL:
        return os.path.join(LOCAL_DATAINPUT, filename)
    else:
        # Download from GCS to local temp storage
        temp_path = f"/tmp/{filename}"
        if not os.path.exists(temp_path):
            logger.info(f"Baixando {filename} do GCS...")
            client = storage.Client()
            bucket = client.bucket(BUCKET_NAME)
            blob = bucket.blob(f"raw/{filename}")
            blob.download_to_filename(temp_path)
        return temp_path

def save_output_file(local_path: str, filename: str):
    """Save processed file to final destination."""
    if IS_LOCAL:
        os.makedirs(LOCAL_DATAOUTPUT, exist_ok=True)
        dest_path = os.path.join(LOCAL_DATAOUTPUT, filename)
        logger.info(f"Salvando localmente em: {dest_path}")
        import shutil
        shutil.copy(local_path, dest_path)
    else:
        logger.info(f"Enviando {filename} para o GCS...")
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        blob = bucket.blob(f"processed/{filename}")
        blob.upload_from_filename(local_path)

def update_firestore_status(task_id: str, status: str, progress: int, log_message: str):
    """Update async execution state in Firestore."""
    logger.info(f"[{status.upper()}] - {log_message}")
    if not IS_LOCAL:
        try:
            db = firestore.Client()
            ref = db.collection("pricing_tasks").document(task_id)
            ref.set({
                "status": status,
                "progress": progress,
                "last_log": log_message,
                "updatedAt": firestore.SERVER_TIMESTAMP
            }, merge=True)
        except Exception as e:
            logger.error(f"Erro ao salvar status no Firestore: {e}")

# --- PIPELINE LOGIC FUNCTIONS ---

def run_cm1_calculation(params: PricingParams, task_id: str = "local"):
    try:
        update_firestore_status(task_id, "processing", 10, "Iniciando cálculo de CM1...")
        
        vendas_file = get_file_content("Cópia de Raw_Base_16-06-26.xlsx")
        aderencia_file = get_file_content("Aderência_Base_MI_Preço Net Fat_Preço Net Sug_jan2024 a Maio26.xlsx")
        
        update_firestore_status(task_id, "processing", 30, "Lendo planilhas Excel...")
        df = pd.read_excel(vendas_file)
        carteira = pd.read_excel(aderencia_file, sheet_name='Base Clientes')
        
        update_firestore_status(task_id, "processing", 50, "Processando cruzamento e agrupando quartis...")
        df_cm1 = pd.merge(df, carteira, left_on=['cd_cliente'], right_on=['Cliente'], how='left')
        df_filtrado = df_cm1[(df_cm1['dt_ano_civil'] >= '2022-01-01') & (df_cm1['vl_CM1'] >= 0)].copy()
        
        # Add quartils
        def get_quartil_series(series):
            try:
                return pd.qcut(series, q=4, labels=['Q_1', 'Q_2', 'Q_3', 'Q_4'], duplicates='drop')
            except ValueError:
                return pd.cut(series, bins=4, labels=['Q_1', 'Q_2', 'Q_3', 'Q_4'], duplicates='drop')

        df_filtrado['quartil'] = df_filtrado.groupby('cd_material')['qt_volume_faturado'].transform(get_quartil_series).astype(str)
        
        update_firestore_status(task_id, "processing", 70, "Identificando último preço praticado...")
        
        # Último preço
        df_sorted = df_filtrado.sort_values('dt_ano_civil', ascending=False)
        ultpreco = df_sorted.groupby(['cd_cliente', 'cd_material', 'quartil']).first().reset_index()
        ultpreco = ultpreco[['cd_cliente', 'cd_material', 'quartil', 'vl_CM1', 'dt_ano_civil']]
        ultpreco = ultpreco.rename(columns={'vl_CM1': 'ultimo_preco'})
        ultpreco['ultimo_preco'] = ultpreco['ultimo_preco'] * 1.05
        
        # Mapeamento do CM1 por volume
        dados_agg = df_filtrado.groupby(['cd_material', 'quartil'])['vl_CM1'].agg(['min', 'max']).reset_index()
        dados_pivot = pd.pivot_table(dados_agg, values=['min', 'max'], index='cd_material', columns='quartil')
        dados_pivot.columns = ["_CM1_vol_".join(col).strip() for col in dados_pivot.columns.values]
        
        # Final merge
        final = df_filtrado.groupby(['cd_cliente', 'cd_material', 'quartil'])['vl_CM1'].agg(['min', 'max']).reset_index()
        final = pd.merge(final, ultpreco, on=['cd_cliente', 'cd_material', 'quartil'], how='left')
        final = pd.merge(final, dados_pivot, on='cd_material', how='left')
        
        # Apply formulas
        def atribuir_valor(row):
            q = row['quartil']
            if q == 'Q_1': return row['max_CM1_vol_Q_1']
            elif q == 'Q_2': return row['max_CM1_vol_Q_2']
            elif q == 'Q_3': return row['max_CM1_vol_Q_3']
            else: return row['max_CM1_vol_Q_4']

        final['CM1_referencia'] = final.apply(atribuir_valor, axis=1)
        
        def CM1final(row):
            if row['ultimo_preco'] / row['CM1_referencia'] > 1 or row['ultimo_preco'] / row['CM1_referencia'] < 0.9:
                return row['ultimo_preco']
            return row['CM1_referencia']
            
        final['CM1_indicado'] = final.apply(CM1final, axis=1)
        
        df_input = final.groupby(['cd_cliente', 'cd_material'])['CM1_indicado'].max().reset_index()
        
        # Save output
        temp_out = f"/tmp/input_julho_2026.xlsx"
        df_input.to_excel(temp_out, index=False)
        save_output_file(temp_out, "input_julho_2026.xlsx")
        
        update_firestore_status(task_id, "completed", 100, "Cálculo de CM1 finalizado com sucesso!")
        
    except Exception as e:
        update_firestore_status(task_id, "error", 100, f"Falha no CM1: {e}")
        logger.error(f"Erro no CM1: {e}", exc_info=True)

# API Endpoints
@app.get("/health")
def health():
    return {"status": "ok", "mode": "local" if IS_LOCAL else "cloud"}

@app.post("/run-cm1")
def run_cm1(params: PricingParams, background_tasks: BackgroundTasks):
    task_id = f"cm1_{int(pd.Timestamp.now().timestamp())}"
    background_tasks.add_task(run_cm1_calculation, params, task_id)
    return {"status": "queued", "task_id": task_id}

@app.post("/run-all")
def run_all(params: PricingParams, background_tasks: BackgroundTasks):
    task_id = f"run_all_{int(pd.Timestamp.now().timestamp())}"
    # In local mode, execute synchronous or queued
    background_tasks.add_task(run_cm1_calculation, params, task_id)
    return {"status": "queued", "task_id": task_id, "message": "Executando pipelines de cálculo."}

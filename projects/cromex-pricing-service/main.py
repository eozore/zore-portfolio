# projects/cromex-pricing-service/main.py

import os
import json
import logging
import shutil
import pandas as pd
import numpy as np
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
BUCKET_NAME = os.getenv("GCP_STORAGE_BUCKET") or os.getenv("CROMEX_BUCKET_NAME") or "zore-portfolio-cromex"
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
        path_upload = os.path.join(LOCAL_DATAINPUT, filename)
        if os.path.exists(path_upload):
            return path_upload
            
        # Local fallback to original names
        if filename == "vendas.xlsx":
            return os.path.join(LOCAL_DATAINPUT, "Cópia de Raw_Base_16-06-26.xlsx")
        elif filename == "aderencia_mi.xlsx":
            return os.path.join(LOCAL_DATAINPUT, "Aderência_Base_MI_Preço Net Fat_Preço Net Sug_jan2024 a Maio26.xlsx")
        elif filename == "aderencia_me.xlsx":
            return os.path.join(LOCAL_DATAINPUT, "Aderência_Base_ME_Preço Net Fat_Preço Net Sug_jan2024 a Maio26.xlsx")
        elif filename == "PE_PP.xlsx":
            return os.path.join(LOCAL_DATAINPUT, "PE_PP.xlsx")
        return path_upload
    else:
        # Download from GCS to local temp storage
        temp_path = f"/tmp/{filename}"
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
                
        logger.info(f"Baixando {filename} do GCS...")
        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        
        blob = bucket.blob(f"raw/{filename}")
        if blob.exists():
            blob.download_to_filename(temp_path)
            return temp_path
            
        # Fallback names in GCS
        fallback_name = filename
        if filename == "vendas.xlsx":
            fallback_name = "Cópia de Raw_Base_16-06-26.xlsx"
        elif filename == "aderencia_mi.xlsx":
            fallback_name = "Aderência_Base_MI_Preço Net Fat_Preço Net Sug_jan2024 a Maio26.xlsx"
        elif filename == "aderencia_me.xlsx":
            fallback_name = "Aderência_Base_ME_Preço Net Fat_Preço Net Sug_jan2024 a Maio26.xlsx"
        elif filename == "PE_PP.xlsx":
            fallback_name = "PE_PP.xlsx"
            
        blob_fallback = bucket.blob(f"raw/{fallback_name}")
        if blob_fallback.exists():
            blob_fallback.download_to_filename(temp_path)
            return temp_path
        else:
            raise FileNotFoundError(f"Arquivo {filename} não encontrado no bucket {BUCKET_NAME} (raw/) e nenhum fallback disponível.")

def save_output_file(local_path: str, filename: str):
    """Save processed file to final destination."""
    if IS_LOCAL:
        os.makedirs(LOCAL_DATAOUTPUT, exist_ok=True)
        dest_path = os.path.join(LOCAL_DATAOUTPUT, filename)
        logger.info(f"Salvando localmente em: {dest_path}")
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
            # Add to log messages array
            ref.set({
                "status": status,
                "progress": progress,
                "last_log": log_message,
                "logs": firestore.ArrayUnion([log_message]),
                "updatedAt": firestore.SERVER_TIMESTAMP
            }, merge=True)
        except Exception as e:
            logger.error(f"Erro ao salvar status no Firestore: {e}")

def calcular_quartis_por_grupo(dataframe, coluna_valor, coluna_grupo):
    def assign_quartis(subdf):
        vals = subdf[coluna_valor]
        if len(vals) == 0:
            subdf['Quartil'] = pd.Series(dtype='category')
            subdf['Valor Quartílico'] = pd.Series(dtype='float64')
            return subdf
            
        quartis = np.percentile(vals, [25, 50, 75])
        bins = [-np.inf, quartis[0], quartis[1], quartis[2], np.inf]
        unique_bins = []
        for b in bins:
            if len(unique_bins) == 0 or b != unique_bins[-1]:
                unique_bins.append(b)

        n_intervals = len(unique_bins) - 1
        labels = [f"Q{i+1}" for i in range(n_intervals)]

        subdf['Quartil'] = pd.cut(vals, bins=unique_bins, labels=labels, include_lowest=True)
        bin_upper = unique_bins[1:]
        subdf['Valor Quartílico'] = pd.cut(vals, bins=unique_bins, labels=bin_upper, include_lowest=True).astype(float)
        return subdf

    return dataframe.groupby(coluna_grupo, group_keys=False).apply(assign_quartis)

# --- PIPELINE TASKS ---

def run_full_pipeline_task(params: PricingParams, task_id: str):
    try:
        update_firestore_status(task_id, "processing", 5, "Iniciando pipeline de precificação Cromex...")
        
        # 1. DOWNLOAD INPUT FILES
        update_firestore_status(task_id, "processing", 10, "Carregando arquivos de entrada...")
        vendas_file = get_file_content("vendas.xlsx")
        aderencia_mi_file = get_file_content("aderencia_mi.xlsx")
        aderencia_me_file = get_file_content("aderencia_me.xlsx")
        pe_pp_file = get_file_content("PE_PP.xlsx")
        
        # 2. RUN CM1 CALCULATION
        update_firestore_status(task_id, "processing", 20, "Iniciando cálculo de CM1...")
        df_vendas = pd.read_excel(vendas_file)
        carteira_mi_raw = pd.read_excel(aderencia_mi_file, sheet_name='Base Clientes')
        
        df_cm1 = pd.merge(df_vendas, carteira_mi_raw, left_on=['cd_cliente'], right_on=['Cliente'], how='left')
        df_filtrado = df_cm1[(df_cm1['dt_ano_civil'] >= '2022-01-01') & (df_cm1['vl_CM1'] >= 0)].copy()
        
        def get_quartil_series(series):
            try:
                return pd.qcut(series, q=4, labels=['Q_1', 'Q_2', 'Q_3', 'Q_4'], duplicates='drop')
            except ValueError:
                return pd.cut(series, bins=4, labels=['Q_1', 'Q_2', 'Q_3', 'Q_4'], duplicates='drop')

        df_filtrado['quartil'] = df_filtrado.groupby('cd_material')['qt_volume_faturado'].transform(get_quartil_series).astype(str)
        
        df_sorted = df_filtrado.sort_values('dt_ano_civil', ascending=False)
        ultpreco = df_sorted.groupby(['cd_cliente', 'cd_material', 'quartil']).first().reset_index()
        ultpreco = ultpreco[['cd_cliente', 'cd_material', 'quartil', 'vl_CM1', 'dt_ano_civil']]
        ultpreco = ultpreco.rename(columns={'vl_CM1': 'ultimo_preco'})
        ultpreco['ultimo_preco'] = ultpreco['ultimo_preco'] * 1.05
        
        dados_agg = df_filtrado.groupby(['cd_material', 'quartil'])['vl_CM1'].agg(['min', 'max']).reset_index()
        dados_pivot = pd.pivot_table(dados_agg, values=['min', 'max'], index='cd_material', columns='quartil')
        dados_pivot.columns = ["_CM1_vol_".join(col).strip() for col in dados_pivot.columns.values]
        
        final_cm1 = df_filtrado.groupby(['cd_cliente', 'cd_material', 'quartil'])['vl_CM1'].agg(['min', 'max']).reset_index()
        final_cm1 = pd.merge(final_cm1, ultpreco, on=['cd_cliente', 'cd_material', 'quartil'], how='left')
        final_cm1 = pd.merge(final_cm1, dados_pivot, on='cd_material', how='left')
        
        def atribuir_valor(row):
            q = row['quartil']
            if q == 'Q_1': return row['max_CM1_vol_Q_1']
            elif q == 'Q_2': return row['max_CM1_vol_Q_2']
            elif q == 'Q_3': return row['max_CM1_vol_Q_3']
            else: return row['max_CM1_vol_Q_4']

        final_cm1['CM1_referencia'] = final_cm1.apply(atribuir_valor, axis=1)
        
        def CM1final(row):
            if row['ultimo_preco'] / row['CM1_referencia'] > 1 or row['ultimo_preco'] / row['CM1_referencia'] < 0.9:
                return row['ultimo_preco']
            return row['CM1_referencia']
            
        final_cm1['CM1_indicado'] = final_cm1.apply(CM1final, axis=1)
        df_input = final_cm1.groupby(['cd_cliente', 'cd_material'])['CM1_indicado'].max().reset_index()
        
        temp_cm1_out = f"/tmp/input_julho_2026.xlsx"
        df_input.to_excel(temp_cm1_out, index=False)
        save_output_file(temp_cm1_out, "input_julho_2026.xlsx")
        
        update_firestore_status(task_id, "processing", 35, "Cálculo de CM1 concluído com sucesso!")

        # 3. PREPARE PE_PP TABLE WITH DYNAMIC PARAMS
        df_pe = pd.read_excel(pe_pp_file)
        df_pe['Data Fat'] = pd.to_datetime(df_pe['Data Fat'])
        df_pe['MesAno'] = df_pe['Data Fat'].dt.to_period('M')
        
        target_period = pd.Period(params.month_ref, freq='M')
        exists = df_pe[df_pe['MesAno'] == target_period]
        if len(exists) > 0:
            idx = exists.index[0]
            df_pe.at[idx, 'PE LINEAR'] = params.pe_linear
            df_pe.at[idx, 'PE BAIXA'] = params.pe_baixa
            df_pe.at[idx, 'PP'] = params.pp
        else:
            new_row = {
                'Data Fat': target_period.to_timestamp(),
                'PE LINEAR': params.pe_linear,
                'PE BAIXA': params.pe_baixa,
                'PP': params.pp,
                'MesAno': target_period
            }
            df_pe = pd.concat([df_pe, pd.DataFrame([new_row])], ignore_index=True)
            
        df_pe_clean = df_pe[['MesAno', 'PE LINEAR', 'PE BAIXA', 'PP']].copy()
        df_pe_clean.columns = ['MesAno', 'PE LINEAR', 'PE BAIXA', 'PP']

        # 4. RUN MI ADHERENCE CALCULATION
        update_firestore_status(task_id, "processing", 40, "Processando Aderência Mercado Interno (MI)...")
        df_mi = pd.read_excel(aderencia_mi_file, skiprows=4)
        carteira_mi = pd.read_excel(aderencia_mi_file, sheet_name='Base Clientes')
        linhaproduto_mi = pd.read_excel(aderencia_mi_file, sheet_name='Linha Produto')[['Familia', 'Linha']].copy()
        vendedores_mi = pd.read_excel(aderencia_mi_file, sheet_name='Base Vendedor&Região').copy()
        
        linhaproduto_mi['Linha'] = linhaproduto_mi['Linha'].astype(str)
        linhaproduto_mi = linhaproduto_mi.drop_duplicates(subset=['Linha'])
        vendedores_mi = vendedores_mi.drop_duplicates(subset=['Carteira'])
        
        tipo_mi = df_mi[['Cliente', 'Tipo']].drop_duplicates(subset=['Cliente']).copy()
        tipo_mi.loc[tipo_mi['Tipo'] == 'revenda', 'Tipo'] = 'Revenda'
        
        df_mi['Linha'] = df_mi['Material'].astype(str).str.slice(0, 2)
        df_mi['CM1 Rep'] = df_mi['CM1 Rep'] * df_mi['Taxa Cambio']
        
        df_mi_select = df_mi[['Data Fat', 'Data Remessa', 'Preço Liq/kg', 'Material', 'Preço sugerido', 'Carteira', 'Cliente', 'CM1 Rep', 'CM1 Real', 'Linha', 'Vol Fat/mês']].copy()
        
        clientes_mi = carteira_mi[['Cliente', 'Descrição CLI', 'Grupo Cliente']].copy()
        clientes_mi.columns = ['Cliente', 'Descrição', 'Grp Cliente']
        clientes_mi = clientes_mi.drop_duplicates(subset=['Cliente'])
        
        df_mi_tot = pd.merge(df_mi_select, clientes_mi, on=['Cliente'], how='left')
        df_mi_tot = pd.merge(df_mi_tot, vendedores_mi, on=['Carteira'], how='left')
        df_mi_tot = pd.merge(df_mi_tot, linhaproduto_mi, on=['Linha'], how='left')
        
        df_mi_tot = df_mi_tot[['Data Fat', 'Preço Liq/kg', 'Material', 'Preço sugerido', 'Carteira', 'Cliente', 'Descrição', 'CM1 Rep', 'CM1 Real', 'Linha', 'Vol Fat/mês', 'Vendedor', 'Região']].copy()
        df_mi_tot['Precokg'] = df_mi_tot['Preço Liq/kg'] * df_mi_tot['Vol Fat/mês']
        df_mi_tot['CM1'] = df_mi_tot['CM1 Rep'] * df_mi_tot['Vol Fat/mês']
        df_mi_tot['MesAno'] = pd.to_datetime(df_mi_tot['Data Fat']).dt.to_period('M')
        
        df_mi_tot = df_mi_tot[(df_mi_tot['Precokg'] > 0) & (df_mi_tot['Vol Fat/mês'] >= 0)]
        df_mi_tot = df_mi_tot.sort_values(['Cliente', 'Material', 'Data Fat'])
        df_mi_tot['TEC'] = df_mi_tot.groupby(['Cliente', 'Material'])['Data Fat'].diff().dt.days
        df_mi_tot['diferenca_preco'] = df_mi_tot.groupby(['Cliente', 'Material'])['Preço Liq/kg'].diff()
        
        df_mi_tot = df_mi_tot.groupby(['MesAno', 'Cliente', 'Material', 'Descrição', 'Carteira', 'Linha', 'Vendedor', 'Região'], as_index=False).agg({
            'Preço sugerido': 'mean',
            'Precokg': 'sum',
            'Vol Fat/mês': 'sum',
            'CM1': 'sum',
            'TEC': 'max',
            'diferenca_preco': 'max'
        })
        
        df_mi_tot['Preço Liq/kg'] = df_mi_tot['Precokg'] / df_mi_tot['Vol Fat/mês']
        df_mi_tot['CM1_rep'] = df_mi_tot['CM1'] / df_mi_tot['Vol Fat/mês']
        df_mi_tot['dif_sugerido'] = df_mi_tot['Preço Liq/kg'] - df_mi_tot['Preço sugerido']
        
        df_mi_tot = calcular_quartis_por_grupo(df_mi_tot, 'Vol Fat/mês', 'Cliente')
        df_mi_tot['Data Fat'] = df_mi_tot['MesAno'].dt.to_timestamp()
        df_mi_tot['Descrição'] = df_mi_tot['Descrição'].apply(lambda x: ' '.join(str(x).split()[:2]))
        
        df_mi_tot = (df_mi_tot.merge(df_pe_clean, on=['MesAno'], how='left')
                              .merge(tipo_mi, on=['Cliente'], how='left')
                              .merge(df_mi[['Cliente', 'Grupo de Cliente']].drop_duplicates(subset=['Cliente']), on=['Cliente'], how='left'))
                              
        df_mi_tot.loc[df_mi_tot['Tipo'] == 'revenda', 'Tipo'] = 'Revenda'
        df_mi_tot.loc[df_mi_tot['Tipo'] == '', 'Tipo'] = 'Direto'
        df_mi_tot.loc[df_mi_tot['Tipo'].isnull(), 'Tipo'] = 'Direto'
        df_mi_tot = df_mi_tot.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        temp_mi_out = f"/tmp/aderencia_mi_processada.xlsx"
        df_mi_tot.to_excel(temp_mi_out, index=False)
        save_output_file(temp_mi_out, "aderencia_mi_processada.xlsx")
        
        update_firestore_status(task_id, "processing", 60, "Processamento de Aderência Mercado Interno (MI) concluído!")

        # 5. RUN ME ADHERENCE CALCULATION
        update_firestore_status(task_id, "processing", 65, "Processando Aderência Mercado Externo (ME)...")
        df_me = pd.read_excel(aderencia_me_file, skiprows=5)
        carteira_me = pd.read_excel(aderencia_me_file, sheet_name='Base Clientes', skiprows=1)
        linhaproduto_me = pd.read_excel(aderencia_me_file, sheet_name='Linha Produto')[['Familia', 'Linha']].copy()
        vendedores_me = pd.read_excel(aderencia_me_file, sheet_name='Base Vendedor&Região').copy()
        
        linhaproduto_me['Linha'] = linhaproduto_me['Linha'].astype(str)
        linhaproduto_me = linhaproduto_me.drop_duplicates(subset=['Linha'])
        vendedores_me = vendedores_me.drop_duplicates(subset=['Carteira'])
        
        tipo_me = df_me[['Cliente', 'Tipo']].drop_duplicates(subset=['Cliente']).copy()
        tipo_me.loc[tipo_me['Tipo'] == 'revenda', 'Tipo'] = 'Revenda'
        
        df_me['Linha'] = df_me['Material'].astype(str).str.slice(0, 2)
        df_me['CM1 Rep'] = df_me['CM1 Rep'] * df_me['Taxa Cambio']
        
        df_me_select = df_me[['Data Fat', 'Data Remessa', 'Preço Liq/kg', 'Material', 'Preço sugerido', 'Carteira', 'Cliente', 'CM1 Rep', 'CM1 Real', 'Linha', 'Vol Fat/mês']].copy()
        df_me_select['Data'] = df_me_select['Data Fat']
        df_me_select['Data Fat'] = np.where(df_me_select['Data Remessa'] < df_me_select['Data Fat'], df_me_select['Data Remessa'], df_me_select['Data Fat'])
        
        clientes_me = carteira_me[['Cliente', 'Nielsen', 'Descrição CLI', 'Grupo Cliente']].copy()
        clientes_me.columns = ['Cliente', 'Nielsen', 'Descrição', 'Grp Cliente']
        clientes_me = clientes_me.drop_duplicates(subset=['Cliente'])
        
        df_me_tot = pd.merge(df_me_select, clientes_me, on=['Cliente'], how='left')
        df_me_tot = pd.merge(df_me_tot, vendedores_me, on=['Carteira'], how='left')
        df_me_tot = pd.merge(df_me_tot, linhaproduto_me, on=['Linha'], how='left')
        
        df_me_tot = df_me_tot[['Data Fat', 'Preço Liq/kg', 'Material', 'Preço sugerido', 'Carteira', 'Cliente', 'Descrição', 'CM1 Rep', 'CM1 Real', 'Linha', 'Vol Fat/mês', 'Nielsen', 'Vendedor', 'Região']].copy()
        df_me_tot['Precokg'] = df_me_tot['Preço Liq/kg'] * df_me_tot['Vol Fat/mês']
        df_me_tot['CM1'] = df_me_tot['CM1 Rep'] * df_me_tot['Vol Fat/mês']
        df_me_tot['MesAno'] = pd.to_datetime(df_me_tot['Data Fat']).dt.to_period('M')
        
        df_me_tot = df_me_tot[(df_me_tot['Precokg'] > 0) & (df_me_tot['Vol Fat/mês'] >= 0)]
        df_me_tot = df_me_tot.sort_values(['Cliente', 'Material', 'Data Fat'])
        df_me_tot['TEC'] = df_me_tot.groupby(['Cliente', 'Material'])['Data Fat'].diff().dt.days
        df_me_tot['diferenca_preco'] = df_me_tot.groupby(['Cliente', 'Material'])['Preço Liq/kg'].diff()
        
        df_me_tot = df_me_tot.groupby(['MesAno', 'Cliente', 'Material', 'Descrição', 'Carteira', 'Linha', 'Nielsen', 'Vendedor', 'Região'], as_index=False).agg({
            'Preço sugerido': 'mean',
            'Precokg': 'sum',
            'Vol Fat/mês': 'sum',
            'CM1': 'sum',
            'TEC': 'max',
            'diferenca_preco': 'max'
        })
        
        df_me_tot['Preço Liq/kg'] = df_me_tot['Precokg'] / df_me_tot['Vol Fat/mês']
        df_me_tot['CM1_rep'] = df_me_tot['CM1'] / df_me_tot['Vol Fat/mês']
        df_me_tot['dif_sugerido'] = df_me_tot['Preço Liq/kg'] - df_me_tot['Preço sugerido']
        
        df_me_tot = calcular_quartis_por_grupo(df_me_tot, 'Vol Fat/mês', 'Cliente')
        df_me_tot['Data Fat'] = df_me_tot['MesAno'].dt.to_timestamp()
        df_me_tot['Descrição'] = df_me_tot['Descrição'].apply(lambda x: ' '.join(str(x).split()[:2]))
        
        df_me_tot = (df_me_tot.merge(df_pe_clean, on=['MesAno'], how='left')
                              .merge(tipo_me, on=['Cliente'], how='left')
                              .merge(df_me[['Cliente', 'Grupo de Cliente']].drop_duplicates(subset=['Cliente']), on=['Cliente'], how='left'))
                              
        df_me_tot.loc[df_me_tot['Tipo'] == 'revenda', 'Tipo'] = 'Revenda'
        df_me_tot.loc[df_me_tot['Tipo'] == '', 'Tipo'] = 'Direto'
        df_me_tot.loc[df_me_tot['Tipo'].isnull(), 'Tipo'] = 'Direto'
        df_me_tot = df_me_tot.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        temp_me_out = f"/tmp/aderencia_me_processada.xlsx"
        df_me_tot.to_excel(temp_me_out, index=False)
        save_output_file(temp_me_out, "aderencia_me_processada.xlsx")
        
        update_firestore_status(task_id, "processing", 85, "Processamento de Aderência Mercado Externo (ME) concluído!")

        # 6. GENERATE DYNAMIC DASHBOARD JSON
        update_firestore_status(task_id, "processing", 90, "Consolidando métricas e gerando painel dinâmico do dashboard...")
        dashboard_data = generate_dashboard_data(df_mi_tot, df_me_tot, df_input)
        
        temp_json_out = f"/tmp/cromex_dashboard.json"
        with open(temp_json_out, "w", encoding="utf-8") as f_json:
            json.dump(dashboard_data, f_json, ensure_ascii=False, indent=2)
            
        save_output_file(temp_json_out, "cromex_dashboard.json")
        
        update_firestore_status(task_id, "completed", 100, "Todo o processamento mensal Cromex finalizado com sucesso!")
        
    except Exception as e:
        update_firestore_status(task_id, "error", 100, f"Falha no processamento: {e}")
        logger.error(f"Erro no pipeline completo: {e}", exc_info=True)

def generate_dashboard_data(df_mi, df_me, df_cm1) -> dict:
    """Consolida as tabelas de MI, ME e CM1 sugerido na estrutura cromex_dashboard.json."""
    dashboard = {
        "MI": build_market_dashboard(df_mi),
        "ME": build_market_dashboard(df_me),
        "CM1": []
    }
    
    # 1. Populate CM1 recommended table (Top 1000 or complete list)
    for _, row in df_cm1.iterrows():
        dashboard["CM1"].append({
            "client_id": int(row["cd_cliente"]),
            "material_id": int(row["cd_material"]),
            "cm1_indicado": float(row["CM1_indicado"])
        })
        
    return dashboard

def build_market_dashboard(df) -> dict:
    """Gera visualizações e KPIs agrupados mensalmente para um mercado específico (MI ou ME)."""
    # Converter MesAno de Period('M') ou strings para YYYY-MM
    df = df.copy()
    df['MesAnoStr'] = df['MesAno'].astype(str)
    
    unique_months = sorted(list(df['MesAnoStr'].unique()))
    
    historical_chart = []
    by_month_data = {}
    
    for m in unique_months:
        sub = df[df['MesAnoStr'] == m]
        if len(sub) == 0:
            continue
            
        total_rows = len(sub)
        vol_total = float(sub['Vol Fat/mês'].sum())
        
        # Calculate rates
        adherent_count = len(sub[sub['dif_sugerido'] >= 0])
        aderencia_pct = round(adherent_count / total_rows * 100, 1) if total_rows > 0 else 0.0
        
        aumento_pct = round(len(sub[sub['diferenca_preco'] > 0]) / total_rows * 100, 1) if total_rows > 0 else 0.0
        reducao_pct = round(len(sub[sub['diferenca_preco'] < 0]) / total_rows * 100, 1) if total_rows > 0 else 0.0
        manutencao_pct = round(len(sub[sub['diferenca_preco'] == 0]) / total_rows * 100, 1) if total_rows > 0 else 0.0
        
        # Recuperação (TEC > 180 dias)
        recup_pct = round(len(sub[sub['TEC'] > 180]) / total_rows * 100, 1) if total_rows > 0 else 0.0
        
        historical_chart.append({
            "month": m,
            "volume": vol_total,
            "aderencia": aderencia_pct
        })
        
        # 1. Regions
        regions_list = []
        reg_groups = sub.groupby('Região')
        for reg_name, reg_sub in reg_groups:
            reg_name_str = str(reg_name) if pd.notna(reg_name) else "Geral"
            r_total = len(reg_sub)
            r_adherent = len(reg_sub[reg_sub['dif_sugerido'] >= 0])
            
            regions_list.append({
                "name": reg_name_str,
                "volume": float(reg_sub['Vol Fat/mês'].sum()),
                "aderencia": float(r_adherent / r_total * 100) if r_total > 0 else 0.0,
                "aumento": float(len(reg_sub[reg_sub['diferenca_preco'] > 0]) / r_total * 100) if r_total > 0 else 0.0,
                "manutencao": float(len(reg_sub[reg_sub['diferenca_preco'] == 0]) / r_total * 100) if r_total > 0 else 0.0,
                "reducao": float(len(reg_sub[reg_sub['diferenca_preco'] < 0]) / r_total * 100) if r_total > 0 else 0.0
            })
            
        # 2. Sellers
        sellers_list = []
        sel_groups = sub.groupby('Vendedor')
        for sel_name, sel_sub in sel_groups:
            sel_name_str = str(sel_name) if pd.notna(sel_name) else "Outros"
            s_total = len(sel_sub)
            s_adherent = len(sel_sub[sel_sub['dif_sugerido'] >= 0])
            
            sellers_list.append({
                "name": sel_name_str,
                "volume": float(sel_sub['Vol Fat/mês'].sum()),
                "aderencia": float(s_adherent / s_total * 100) if s_total > 0 else 0.0
            })
        sellers_list = sorted(sellers_list, key=lambda x: x['volume'], reverse=True)[:25]
        
        # 3. Clients
        clients_list = []
        cli_groups = sub.groupby('Descrição')
        for cli_name, cli_sub in cli_groups:
            cli_name_str = str(cli_name) if pd.notna(cli_name) else "Outros"
            c_total = len(cli_sub)
            c_adherent = len(cli_sub[cli_sub['dif_sugerido'] >= 0])
            
            clients_list.append({
                "name": cli_name_str,
                "volume": float(cli_sub['Vol Fat/mês'].sum()),
                "aderencia": float(c_adherent / c_total * 100) if c_total > 0 else 0.0
            })
        clients_list = sorted(clients_list, key=lambda x: x['volume'], reverse=True)[:50]
        
        # 4. Materials
        materials_list = []
        mat_groups = sub.groupby('Linha')
        for mat_name, mat_sub in mat_groups:
            mat_name_str = str(mat_name) if pd.notna(mat_name) else "Geral"
            m_total = len(mat_sub)
            m_adherent = len(mat_sub[mat_sub['dif_sugerido'] >= 0])
            
            materials_list.append({
                "name": mat_name_str,
                "volume": float(mat_sub['Vol Fat/mês'].sum()),
                "aderencia": float(m_adherent / m_total * 100) if m_total > 0 else 0.0
            })
        materials_list = sorted(materials_list, key=lambda x: x['volume'], reverse=True)[:25]
        
        # 5. Purchase Types (Channels)
        purchase_list = []
        pur_groups = sub.groupby('Tipo')
        for pur_name, pur_sub in pur_groups:
            pur_name_str = str(pur_name) if pd.notna(pur_name) else "Direto"
            p_total = len(pur_sub)
            p_adherent = len(pur_sub[pur_sub['dif_sugerido'] >= 0])
            
            purchase_list.append({
                "name": pur_name_str,
                "volume": float(pur_sub['Vol Fat/mês'].sum()),
                "aderencia": float(p_adherent / p_total * 100) if p_total > 0 else 0.0
            })
            
        by_month_data[m] = {
            "kpis": {
                "itens": total_rows,
                "aderencia": aderencia_pct,
                "aumento": aumento_pct,
                "reducao": reducao_pct,
                "manutencao": manutencao_pct,
                "novo": 0.0,
                "recuperacao": recup_pct,
                "volume_total": vol_total
            },
            "regions": regions_list,
            "sellers": sellers_list,
            "clients": clients_list,
            "materials": materials_list,
            "purchase_types": purchase_list
        }
        
    return {
        "months": unique_months,
        "historical": historical_chart,
        "by_month": by_month_data
    }

# API Endpoints
@app.get("/health")
def health():
    return {"status": "ok", "mode": "local" if IS_LOCAL else "cloud"}

@app.post("/run-cm1")
def run_cm1(params: PricingParams, background_tasks: BackgroundTasks):
    task_id = f"cm1_{int(pd.Timestamp.now().timestamp())}"
    background_tasks.add_task(run_full_pipeline_task, params, task_id)
    return {"status": "queued", "task_id": task_id}

@app.post("/run-all")
def run_all(params: PricingParams, background_tasks: BackgroundTasks):
    task_id = f"run_all_{int(pd.Timestamp.now().timestamp())}"
    background_tasks.add_task(run_full_pipeline_task, params, task_id)
    return {"status": "queued", "task_id": task_id, "message": "Executando pipelines de cálculo completos."}

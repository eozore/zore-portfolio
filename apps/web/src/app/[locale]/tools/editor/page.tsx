'use client';

import React, { useState, useRef } from 'react';

export default function EditorVideoPage() {
  const [htmlFile, setHtmlFile] = useState<File | null>(null);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [duration, setDuration] = useState('5');
  const [resolution, setResolution] = useState('1080p');
  
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState<Array<{ time: string; message: string; type: string }>>([]);
  const [downloadUrls, setDownloadUrls] = useState<{ horizontal: string; vertical: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  
  const logContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const addLog = (msg: string, type: string = 'info') => {
    const time = new Date().toLocaleTimeString();
    setLogs((prev) => [...prev, { time, message: msg, type }]);
    setTimeout(() => {
      if (logContainerRef.current) {
        logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
      }
    }, 50);
  };

  const handleDropHtml = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length > 0) {
      setHtmlFile(e.dataTransfer.files[0]);
    }
  };

  const handleDropVideo = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files.length > 0) {
      setVideoFile(e.dataTransfer.files[0]);
    }
  };

  const connectWebSocket = (projectId: string) => {
    const wsUrl = `ws://localhost:4000/ws/projects/${projectId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      addLog('Conectado ao pipeline de edição via WebSocket.', 'info');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const { event: evtName, data } = msg;

        switch (evtName) {
          case 'STEP_STARTED':
            addLog(`▶ ${data.message}`, 'info');
            break;
          case 'STEP_PROGRESS':
            addLog(data.message, 'info');
            setProgress(data.percent);
            break;
          case 'STEP_COMPLETED':
            addLog(`✓ ${data.message || data.step + ' concluído'}`, 'info');
            break;
          case 'PROJECT_COMPLETED':
            addLog(data.message, 'success');
            // URLs can be absolute (GCS signed) or relative (local API)
            const hUrl = data.outputs.horizontal_url.startsWith('/')
              ? `http://localhost:4000${data.outputs.horizontal_url}`
              : data.outputs.horizontal_url;
            const vUrl = data.outputs.vertical_url.startsWith('/')
              ? `http://localhost:4000${data.outputs.vertical_url}`
              : data.outputs.vertical_url;
            setDownloadUrls({ horizontal: hUrl, vertical: vUrl });
            setProgress(100);
            setIsProcessing(false);
            ws.close();
            break;
          case 'PROJECT_FAILED':
            addLog(`✗ Erro em ${data.step}: ${data.message}`, 'error');
            setErrorMsg(data.message);
            setIsProcessing(false);
            ws.close();
            break;
          case 'HEARTBEAT':
            // keep-alive, no action needed
            break;
          case 'pong':
            break;
          default:
            addLog(`[${evtName}] ${JSON.stringify(data)}`, 'info');
        }
      } catch (err) {
        console.warn('Erro ao decodificar WebSocket message:', event.data);
      }
    };

    ws.onerror = () => {
      addLog('Erro na conexão WebSocket.', 'error');
    };

    ws.onclose = () => {
      wsRef.current = null;
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!htmlFile || !videoFile) {
      alert('Por favor, selecione tanto o arquivo HTML quanto o Vídeo MP4.');
      return;
    }

    setIsProcessing(true);
    setLogs([]);
    setDownloadUrls(null);
    setErrorMsg(null);
    setProgress(0);

    addLog('Enviando arquivos para o motor de processamento (GCP + Gemini)...', 'info');

    const formData = new FormData();
    formData.append('htmlFile', htmlFile);
    formData.append('videoFile', videoFile);

    try {
      const response = await fetch('/api/tools/editor/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(err.error || `Erro na API (${response.status})`);
      }

      const data = await response.json();
      const projectId = data.project_id;

      addLog(`Projeto criado: ${projectId} (${data.total_slides} slides, ${Math.round(data.video_duration_sec)}s)`, 'info');
      addLog('Conectando ao pipeline em tempo real...', 'info');

      // Connect WebSocket for real-time progress
      connectWebSocket(projectId);

    } catch (err: any) {
      addLog(`Erro crítico: ${err.message}`, 'error');
      setErrorMsg(err.message);
      setIsProcessing(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {/* Header */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold uppercase tracking-wider mb-3">
          <i className="fa-solid fa-wand-magic-sparkles" /> IA Generativa & GCP
        </div>
        <h1 className="text-4xl font-extrabold text-text-main tracking-tight">
          Editor de Vídeo YouTube
        </h1>
        <p className="mt-3 text-text-muted text-base max-w-2xl mx-auto">
          Transcreva áudio no Google Cloud, alinhe com Gemini 2.5 e sobreponha slides em vídeos MP4 automaticamente com sincronia milimétrica.
        </p>
      </div>

      {/* Main Glass Card */}
      <div className="glass rounded-card-lg p-8 shadow-glow border border-border">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* 2-Column Drop Zones */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* HTML Drop Zone */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDropHtml}
              onClick={() => document.getElementById('inputHtml')?.click()}
              className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all ${
                htmlFile
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-border hover:border-primary/50 bg-white/40 hover:bg-white/60 text-text-muted'
              }`}
            >
              <input
                id="inputHtml"
                type="file"
                accept=".html"
                className="hidden"
                onChange={(e) => e.target.files && setHtmlFile(e.target.files[0])}
              />
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                <i className="fa-solid fa-file-code text-primary text-xl" />
              </div>
              <p className="font-bold text-sm text-text-main">
                1. Deck de Slides (.HTML)
              </p>
              <p className="text-xs mt-1 truncate max-w-[200px] mx-auto">
                {htmlFile ? htmlFile.name : 'Arraste ou clique para selecionar'}
              </p>
            </div>

            {/* MP4 Drop Zone */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDropVideo}
              onClick={() => document.getElementById('inputVideo')?.click()}
              className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all ${
                videoFile
                  ? 'border-emerald-500 bg-emerald-500/5 text-emerald-600'
                  : 'border-border hover:border-emerald-500/50 bg-white/40 hover:bg-white/60 text-text-muted'
              }`}
            >
              <input
                id="inputVideo"
                type="file"
                accept=".mp4"
                className="hidden"
                onChange={(e) => e.target.files && setVideoFile(e.target.files[0])}
              />
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-3">
                <i className="fa-solid fa-video text-emerald-600 text-xl" />
              </div>
              <p className="font-bold text-sm text-text-main">
                2. Vídeo Apresentador (.MP4)
              </p>
              <p className="text-xs mt-1 truncate max-w-[200px] mx-auto">
                {videoFile ? videoFile.name : 'Arraste ou clique para selecionar'}
              </p>
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isProcessing || !htmlFile || !videoFile}
            className="w-full py-4 rounded-xl font-bold text-white bg-gradient-to-r from-primary to-accent-data hover:opacity-95 shadow-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 text-base"
          >
            {isProcessing ? (
              <>
                <i className="fa-solid fa-circle-notch fa-spin" />
                <span>Processando Pipeline IA (GCP + Gemini)...</span>
              </>
            ) : (
              <>
                <i className="fa-solid fa-play" />
                <span>Iniciar Edição Automática</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Progress Bar */}
      {isProcessing && progress > 0 && (
        <div className="mt-6">
          <div className="flex justify-between text-xs text-text-muted mb-1">
            <span>Progresso</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary to-accent-data rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Terminal Progress Console */}
      {(isProcessing || logs.length > 0) && (
        <div className="mt-8 rounded-2xl bg-slate-950 border border-slate-800 shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800 text-xs font-mono text-slate-400">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-500" />
              <span className="w-3 h-3 rounded-full bg-yellow-500" />
              <span className="w-3 h-3 rounded-full bg-green-500" />
              <span className="ml-2 font-bold text-slate-200">editor-pipeline.log</span>
            </div>
            <span>{isProcessing ? '⚡ Rodando...' : '✅ Finalizado'}</span>
          </div>
          <div
            ref={logContainerRef}
            className="p-4 h-64 overflow-y-auto font-mono text-xs space-y-2 text-slate-300"
          >
            {logs.map((log, idx) => (
              <div key={idx} className="flex gap-2">
                <span className="text-slate-500 shrink-0">[{log.time}]</span>
                <span
                  className={
                    log.type === 'error'
                      ? 'text-red-400 font-bold'
                      : log.type === 'success'
                      ? 'text-emerald-400 font-bold'
                      : 'text-slate-300'
                  }
                >
                  {log.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Download Block */}
      {downloadUrls && (
        <div className="mt-8 glass rounded-card-lg p-6 border border-emerald-500/30 bg-emerald-500/5 text-center">
          <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-600 flex items-center justify-center mx-auto mb-3">
            <i className="fa-solid fa-check text-xl" />
          </div>
          <h3 className="text-xl font-bold text-text-main">
            Vídeos Editados com Sucesso!
          </h3>
          <p className="text-sm text-text-muted mt-1 mb-6 max-w-md mx-auto">
            Áudio transcrito no GCP, alinhado com Gemini 2.5, slides sobrepostos e salvos no Cloud Storage.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href={downloadUrls.horizontal}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-white bg-emerald-600 hover:bg-emerald-700 shadow-lg transition-all"
            >
              <i className="fa-solid fa-download" />
              <span>Horizontal (16:9)</span>
            </a>
            <a
              href={downloadUrls.vertical}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-white bg-indigo-600 hover:bg-indigo-700 shadow-lg transition-all"
            >
              <i className="fa-solid fa-download" />
              <span>Vertical (9:16)</span>
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

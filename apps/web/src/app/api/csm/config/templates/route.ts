import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { dbPaths } from '@/lib/dbPaths';

export const dynamic = 'force-dynamic';

const DEFAULT_TEMPLATES = [
  {
    id: 'code_overlay',
    name: 'Código Fonte (Tech Dark)',
    htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 0;
      background: #00ff00; /* Chroma Key */
      font-family: 'Inter', sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      overflow: hidden;
    }
    .card {
      width: 90%;
      max-width: 360px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      border: 2px solid #e67e22;
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
      animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    @keyframes slideUp {
      from { transform: translateY(50px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .title {
      color: #fff;
      font-size: 1.1rem;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .badge {
      background: linear-gradient(135deg, #e67e22, #f39c12);
      color: #000;
      font-weight: bold;
      font-size: 0.7rem;
      padding: 4px 8px;
      border-radius: 6px;
    }
    .code-block {
      background: #090d16;
      border-radius: 12px;
      padding: 16px;
      font-family: 'Fira Code', monospace;
      font-size: 0.8rem;
      color: #cbd5e1;
      border: 1px solid rgba(255, 255, 255, 0.08);
      overflow-x: auto;
      line-height: 1.5;
    }
    .keyword { color: #f472b6; }
    .function { color: #38bdf8; }
    .string { color: #4ade80; }
    .comment { color: #64748b; font-style: italic; }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">Éozoré • Code Live</div>
      <div class="badge">AULA PRÁTICA</div>
    </div>
    <div class="code-block">
      <span class="comment"># Definindo a rede neural</span><br/>
      <span class="keyword">def</span> <span class="function">forward</span>(self, x):<br/>
      &nbsp;&nbsp;&nbsp;&nbsp;x = self.<span class="function">encoder</span>(x)<br/>
      &nbsp;&nbsp;&nbsp;&nbsp;z = self.<span class="function">latent_space</span>(x)<br/>
      &nbsp;&nbsp;&nbsp;&nbsp;<span class="keyword">return</span> self.<span class="function">decoder</span>(z)
    </div>
  </div>
</body>
</html>`,
  },
  {
    id: 'latex_theory',
    name: 'Teoria Científica (LaTeX Style)',
    htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 0;
      background: #00ff00; /* Chroma Key */
      font-family: 'Inter', sans-serif;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      overflow: hidden;
    }
    .panel {
      width: 90%;
      max-width: 360px;
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
      animation: zoomIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    }
    @keyframes zoomIn {
      from { transform: scale(0.9); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
    .topic {
      color: #e67e22;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }
    .math-container {
      background: #f8fafc;
      border-radius: 16px;
      padding: 20px;
      border: 1px solid #e2e8f0;
      margin: 16px 0;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 1.25rem;
      color: #0f172a;
      font-weight: bold;
    }
    .description {
      font-size: 0.85rem;
      color: #475569;
      line-height: 1.4;
    }
  </style>
</head>
<body>
  <div class="panel">
    <div class="topic">Fundamento Teórico</div>
    <div class="description">Fórmula da perda por Entropia Cruzada:</div>
    <div class="math-container">
      L = - &Sigma; y_i log(p_i)
    </div>
    <div class="description" style="font-size: 0.75rem; color: #64748b;">
      Utilizada para medir a divergência de probabilidade entre previsões do modelo e labels reais.
    </div>
  </div>
</body>
</html>`,
  },
  {
    id: 'blog_code_block',
    name: 'Componente: Código do Blog',
    htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 20px;
      background: #090d16;
      font-family: 'Inter', sans-serif;
    }
    .card {
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      border: 2px solid #e67e22;
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .title {
      color: #fff;
      font-size: 1rem;
      font-weight: 800;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .badge {
      background: linear-gradient(135deg, #e67e22, #f39c12);
      color: #000;
      font-weight: bold;
      font-size: 0.7rem;
      padding: 4px 8px;
      border-radius: 6px;
    }
    .code-block {
      background: #090d16;
      border-radius: 12px;
      padding: 16px;
      font-family: 'Fira Code', monospace;
      font-size: 0.85rem;
      color: #cbd5e1;
      border: 1px solid rgba(255, 255, 255, 0.08);
      overflow-x: auto;
      line-height: 1.6;
    }
    .keyword { color: #f472b6; }
    .function { color: #38bdf8; }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">python</div>
      <div class="badge">COPIAR</div>
    </div>
    <div class="code-block">
      <span class="keyword">import</span> torch<br/>
      loss_fn = torch.nn.<span class="function">CrossEntropyLoss</span>()
    </div>
  </div>
</body>
</html>`,
  },
  {
    id: 'blog_latex_math',
    name: 'Componente: Math LaTeX',
    htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 20px;
      background: #f8fafc;
      font-family: 'Inter', sans-serif;
    }
    .panel {
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(0, 0, 0, 0.08);
      border-radius: 24px;
      padding: 24px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
    }
    .topic {
      color: #e67e22;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }
    .math-container {
      background: #f8fafc;
      border-radius: 16px;
      padding: 20px;
      border: 1px solid #e2e8f0;
      margin: 16px 0;
      display: flex;
      justify-content: center;
      align-items: center;
      font-size: 1.25rem;
      color: #0f172a;
      font-weight: bold;
    }
    .description {
      font-size: 0.85rem;
      color: #475569;
      line-height: 1.4;
    }
  </style>
</head>
<body>
  <div class="panel">
    <div class="topic">Fundamento Teórico</div>
    <div class="math-container">
      L_G = - E_{x ~ p_{data}} [ \\log D(x) ]
    </div>
    <div class="description">
      Equação estrutural correspondente à formulação matemática do modelo.
    </div>
  </div>
</body>
</html>`,
  },
  {
    id: 'blog_callout',
    name: 'Componente: Callout/Destaque',
    htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 20px;
      background: #090d16;
      font-family: 'Inter', sans-serif;
    }
    .callout {
      background: rgba(15, 23, 42, 0.85); 
      backdrop-filter: blur(16px);
      border-left: 4px solid #e67e22; 
      border-radius: 0 20px 20px 0; 
      padding: 20px; 
      color: #cbd5e1; 
      font-size: 0.9rem; 
      line-height: 1.6;
      box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
    }
  </style>
</head>
<body>
  <div class="callout">
    <strong>💡 Dica de MLOps:</strong> Sempre monitore a perda de validação durante o treinamento distribuído para evitar overfitting catastrófico.
  </div>
</body>
</html>`,
  },
  {
    id: 'blog_chart_card',
    name: 'Componente: Gráfico do Blog',
    htmlContent: `<!DOCTYPE html>
<html>
<head>
  <style>
    body {
      margin: 0;
      padding: 20px;
      background: #090d16;
      font-family: 'Inter', sans-serif;
    }
    .card {
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(16px);
      border: 2px solid #e67e22;
      border-radius: 20px;
      padding: 24px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
    }
    .header {
      display: flex;
      justify-content: flex-start;
      align-items: center;
      margin-bottom: 16px;
    }
    .title {
      color: rgba(255, 255, 255, 0.7);
      font-size: 0.8rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .chart-area {
      background: #090d16;
      border-radius: 12px;
      padding: 16px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 200px;
    }
    .placeholder-svg {
      width: 100%;
      height: 180px;
    }
    .caption {
      margin-top: 14px;
      font-size: 0.8rem;
      color: #94a3b8;
      line-height: 1.4;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="title">Comportamento do Modelo</div>
    </div>
    <div class="chart-area">
      <svg class="placeholder-svg" viewBox="0 0 400 200" fill="none" xmlns="http://www.w3.org/2000/svg">
        <line x1="40" y1="20" x2="380" y2="20" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
        <line x1="40" y1="60" x2="380" y2="60" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
        <line x1="40" y1="100" x2="380" y2="100" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
        <line x1="40" y1="140" x2="380" y2="140" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
        <line x1="40" y1="180" x2="380" y2="180" stroke="rgba(255,255,255,0.1)" stroke-width="2" />
        <line x1="40" y1="20" x2="40" y2="180" stroke="rgba(255,255,255,0.1)" stroke-width="2" />
        
        <text x="15" y="185" fill="rgba(255,255,255,0.4)" font-size="9" font-family="monospace">0.0</text>
        <text x="15" y="105" fill="rgba(255,255,255,0.4)" font-size="9" font-family="monospace">0.5</text>
        <text x="15" y="25" fill="rgba(255,255,255,0.4)" font-size="9" font-family="monospace">1.0</text>
        
        <path d="M 40 180 Q 120 180 200 100 T 360 20" stroke="#06b6d4" stroke-width="3" fill="none" />
        <path d="M 40 160 Q 130 140 210 120 T 360 80" stroke="#7c3aed" stroke-width="3" stroke-dasharray="4 4" fill="none" />
        
        <circle cx="200" cy="100" r="4" fill="#06b6d4" />
        <circle cx="360" cy="20" r="4" fill="#06b6d4" />
      </svg>
    </div>
    <div class="caption">
      Gráfico científico de decaimento de erro e convergência do otimizador.
    </div>
  </div>
</body>
</html>`,
  },
];

export async function GET(request: Request): Promise<Response> {
  const csmSession = request.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });
  }

  try {
    const templatesColl = await db.collection(dbPaths.videoTemplates(tenantId)).get();
    const activeTemplates: Record<string, string> = {};

    templatesColl.forEach((doc) => {
      const data = doc.data();
      if (data.htmlContent) {
        activeTemplates[doc.id] = data.htmlContent;
      }
    });

    const responseData = DEFAULT_TEMPLATES.map((tmpl) => ({
      id: tmpl.id,
      name: tmpl.name,
      fallbackHtml: tmpl.htmlContent,
      activeHtml: activeTemplates[tmpl.id] || tmpl.htmlContent,
      isCustomized: !!activeTemplates[tmpl.id],
    }));

    return NextResponse.json({ templates: responseData });
  } catch (err: any) {
    console.error('[csm/templates] GET error:', err);
    return NextResponse.json({ error: err.message || 'Failed to fetch templates' }, { status: 500 });
  }
}

export async function POST(request: Request): Promise<Response> {
  const csmSession = request.headers.get('x-csm-session');
  if (csmSession !== 'authenticated') {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: any;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { templateId, htmlContent } = body;

  const validIds = DEFAULT_TEMPLATES.map((t) => t.id);
  if (!templateId || !validIds.includes(templateId)) {
    return NextResponse.json({ error: 'ID do template inválido ou ausente.' }, { status: 400 });
  }

  const tenantId = request.headers.get('x-tenant-id') || null;
  const db = getFirestoreDb();
  if (!db) {
    return NextResponse.json({ error: 'Firestore unavailable' }, { status: 500 });
  }

  try {
    const docRef = db.doc(dbPaths.videoTemplateDoc(templateId, tenantId));
    
    const fallback = DEFAULT_TEMPLATES.find((t) => t.id === templateId)?.htmlContent;
    
    if (htmlContent === null || htmlContent === undefined || htmlContent === fallback) {
      // If template is reset to factory, delete the document
      await docRef.delete();
      return NextResponse.json({ success: true, message: 'Template restaurado para o padrão.' });
    }

    await docRef.set({
      htmlContent,
      updated_at: new Date().toISOString(),
    }, { merge: true });

    return NextResponse.json({ success: true, message: 'Template de vídeo gravado no Firestore com sucesso.' });
  } catch (err: any) {
    console.error('[csm/templates] POST error:', err);
    return NextResponse.json({ error: err.message || 'Failed to update template' }, { status: 500 });
  }
}

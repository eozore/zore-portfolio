import { NextRequest, NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';
import { SecretManagerServiceClient } from '@google-cloud/secret-manager';
import { dbPaths } from '@/lib/dbPaths';
import { decrypt } from '@/lib/crypto';
import { sanitizeHeyGenScript } from '@/lib/heygenSanitizer';

// Simulates a video processing pipeline when the API key is not present
const SIMULATED_VIDEOS: Record<string, { status: string; progress: number; video_url?: string; error?: string }> = {};

function isGcpProduction(): boolean {
  return !!(process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT || process.env.VERCEL);
}

async function getHeyGenSettings(
  profile: 'horizontal' | 'vertical',
  tenantId: string | null = null
): Promise<{ apiKey: string; avatarId: string; voiceId: string }> {
  const useGcp = isGcpProduction() && !tenantId;
  const projectId = process.env.GOOGLE_CLOUD_PROJECT || process.env.GCP_PROJECT || 'studious-hydra-303815';

  let apiKey = '';
  // Default values
  let avatarId = 'db66746ef7d848cca675c74239857d42'; // default realistic avatar
  let voiceId = '1bd0091de9434efda90327f2269a84f3'; // default portuguese voice

  if (useGcp) {
    try {
      const client = new SecretManagerServiceClient();
      
      const getSecretValue = async (secretName: string): Promise<string> => {
        try {
          const [version] = await client.accessSecretVersion({
            name: `projects/${projectId}/secrets/${secretName}/versions/latest`,
          });
          return version.payload?.data?.toString() || '';
        } catch {
          return '';
        }
      };

      apiKey = await getSecretValue('heygen-api-key');
    } catch (err: any) {
      console.warn('[heygen/keys] GCP Secret Manager access failed, trying local store:', err.message);
    }
  }

  // Local Dev Fallback for API Key
  if (!apiKey) {
    try {
      const db = getFirestoreDb();
      if (db) {
        const doc = await db.doc(dbPaths.apiKeysDoc(tenantId)).get();
        if (doc.exists) {
          const firestoreKeys = doc.data() || {};
          if (firestoreKeys['HEYGEN_API_KEY']) {
            apiKey = await decrypt(firestoreKeys['HEYGEN_API_KEY']);
          }
        }
      }
    } catch (err) {
      console.warn('[heygen/keys] Firestore key read failed:', err);
    }
  }

  if (!apiKey) apiKey = process.env.HEYGEN_API_KEY || '';

  // Fetch avatar profile settings from Firestore configuration
  try {
    const db = getFirestoreDb();
    if (db) {
      const doc = await db.doc(dbPaths.avatarsDoc(tenantId)).get();
      if (doc.exists) {
        const data = doc.data() || {};
        const profileConfig = data[profile];
        if (profileConfig) {
          if (profileConfig.avatarId) avatarId = profileConfig.avatarId;
          if (profileConfig.voiceId) voiceId = profileConfig.voiceId;
        }
      }
    }
  } catch (err) {
    console.warn('[heygen/settings] Failed to fetch custom avatars config, using defaults:', err);
  }

  return { apiKey, avatarId, voiceId };
}

export async function POST(req: NextRequest) {
  try {
    const { script, format, title, id, avatarProfile } = await req.json();

    if (!script) {
      return NextResponse.json({ error: 'Roteiro (script) é obrigatório.' }, { status: 400 });
    }

    const tenantId = req.headers.get('x-tenant-id') || null;
    
    // Determine the profile based on input or format dimensions
    const profile: 'horizontal' | 'vertical' = avatarProfile || 
      (format === 'portrait' || format === 'shorts' || format === 'reel' ? 'vertical' : 'horizontal');
      
    const { apiKey, avatarId, voiceId } = await getHeyGenSettings(profile, tenantId);

    // Apply speech script sanitization using speak_extractor_agent microservice
    let sanitizedScript = '';
    try {
      const cleanRes = await fetch('http://localhost:8090/extract-speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script })
      });
      if (cleanRes.ok) {
        const cleanData = await cleanRes.json();
        sanitizedScript = cleanData.cleanedScript;
        console.log('[heygen/ai-extractor] Cleaned speech script:', sanitizedScript);
      }
    } catch (err: any) {
      console.warn('[heygen/ai-extractor] AI speech extraction failed, falling back to regex sanitizer:', err.message);
    }

    if (!sanitizedScript) {
      sanitizedScript = sanitizeHeyGenScript(script);
    }

    // If no API key is found, simulate the render workflow with a premium aesthetic video loop
    if (!apiKey) {
      const mockVideoId = `mock_hg_${Date.now()}`;
      SIMULATED_VIDEOS[mockVideoId] = {
        status: 'pending',
        progress: 0,
      };

      // Background progressive update simulation
      let progress = 0;
      const interval = setInterval(() => {
        progress += 25;
        if (progress >= 100) {
          SIMULATED_VIDEOS[mockVideoId] = {
            status: 'completed',
            progress: 100,
            // A highly stable public test MP4 video loop to guarantee HTML5 player loading
            video_url: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
          };
          clearInterval(interval);
        } else {
          SIMULATED_VIDEOS[mockVideoId] = {
            status: 'processing',
            progress,
          };
        }
      }, 3000);

      return NextResponse.json({
        success: true,
        videoId: mockVideoId,
        isMock: true,
        message: 'Aviso: API Key do HeyGen não configurada. Executando em modo de simulação.'
      });
    }

    // Call HeyGen V2 Direct Video API (compatible with video_inputs payload)
    const response = await fetch('https://api.heygen.com/v2/video/generate', {
      method: 'POST',
      headers: {
        'X-Api-Key': apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        video_inputs: [
          {
            character: {
              type: 'avatar',
              avatar_id: avatarId,
              avatar_style: 'normal',
            },
            voice: {
              type: 'text',
              input_text: sanitizedScript,
              voice_id: voiceId,
            },
          },
        ],
        dimension: {
          width: format === 'portrait' || format === 'shorts' || format === 'reel' ? 1080 : 1920,
          height: format === 'portrait' || format === 'shorts' || format === 'reel' ? 1920 : 1080,
        },
        caption: false,
      }),
    });

    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json({ error: `HeyGen API Error: ${errText}` }, { status: response.status });
    }

    const resData = await response.json();
    const videoId = resData?.data?.video_id;

    if (!videoId) {
      return NextResponse.json({ error: 'Falha ao recuperar video_id da API do HeyGen.' }, { status: 500 });
    }

    return NextResponse.json({ success: true, videoId, isMock: false });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro interno na rota do HeyGen.' }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const videoId = searchParams.get('videoId');

    if (!videoId) {
      return NextResponse.json({ error: 'videoId é obrigatório.' }, { status: 400 });
    }

    // Check simulated mock video status
    if (videoId.startsWith('mock_hg_')) {
      const mockVideo = SIMULATED_VIDEOS[videoId];
      if (!mockVideo) {
        return NextResponse.json({ error: 'Vídeo simulado não encontrado.' }, { status: 404 });
      }
      return NextResponse.json({
        status: mockVideo.status,
        progress: mockVideo.progress,
        videoUrl: mockVideo.video_url,
      });
    }

    const tenantId = req.headers.get('x-tenant-id') || null;
    // We can pass any profile since we only need the API Key to fetch status of a generated video
    const { apiKey } = await getHeyGenSettings('horizontal', tenantId);
    if (!apiKey) {
      return NextResponse.json({ error: 'HeyGen API key is missing' }, { status: 500 });
    }

    // Call HeyGen Video Status endpoint
    const response = await fetch(`https://api.heygen.com/v3/videos/${videoId}`, {
      method: 'GET',
      headers: {
        'X-Api-Key': apiKey,
      },
    });

    if (!response.ok) {
      const errText = await response.text();
      return NextResponse.json({ error: `HeyGen Status API Error: ${errText}` }, { status: response.status });
    }

    const resData = await response.json();
    const status = resData?.data?.status; // "completed", "processing", "pending", "failed"
    const videoUrl = resData?.data?.video_url;
    
    let error = resData?.data?.error;
    if (!error && resData?.data?.failure_message) {
      error = `${resData.data.failure_code || 'FAILED'}: ${resData.data.failure_message}`;
    }

    return NextResponse.json({
      status: status || 'pending',
      progress: status === 'completed' ? 100 : status === 'failed' ? 0 : 50,
      videoUrl,
      error,
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message || 'Erro ao buscar status do HeyGen.' }, { status: 500 });
  }
}

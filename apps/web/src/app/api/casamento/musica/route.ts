import { NextResponse } from 'next/server';
import { getFirestoreDb } from '@/lib/firebase';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { nome, musica } = body;

    if (!nome || !musica) {
      return NextResponse.json({ error: 'Nome e música são obrigatórios.' }, { status: 400 });
    }

    const db = getFirestoreDb();
    if (!db) {
      return NextResponse.json({ error: 'Banco de dados indisponível.' }, { status: 500 });
    }

    // A collection "musicas" é a mesma que o cliente esperava usar
    await db.collection('musicas').add({
      nome: nome.trim(),
      musica: musica.trim(),
      timestamp: new Date()
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Erro ao adicionar música:', error);
    return NextResponse.json({ error: 'Erro interno ao adicionar música.' }, { status: 500 });
  }
}

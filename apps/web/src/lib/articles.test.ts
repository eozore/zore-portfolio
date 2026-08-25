/**
 * Cobertura do filtro de rascunho em `getArticleBySlug`.
 *
 * Por que existe: o gate do Studio grava o artigo como `draft` e trata isso
 * como "ainda não está no ar". Mas o filtro de status vivia só em
 * `getAllArticles` — o índice do blog escondia o post e a URL direta o servia
 * inteiro, com HTTP 200. Verificado em produção em 24/08: 64KB de artigo
 * rascunho acessível a qualquer um com o endereço.
 *
 * O endereço não é secreto: ele vai em toda peça social agendada, dias antes
 * de o artigo ser promovido. Uma regressão aqui publica sem ninguém aprovar.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';

const consultar = vi.fn();

vi.mock('./firebase', () => ({
  getFirestoreDb: () => ({
    collection: () => ({
      where: function () { return this; },
      limit:  function () { return this; },
      get:    consultar,
    }),
  }),
}));

vi.mock('./dbPaths', () => ({ dbPaths: { articles: () => 'articles' } }));

import { getArticleBySlug } from './articles';

function resultado(status: string | undefined) {
  return {
    empty: false,
    docs: [{ id: 'a1', data: () => ({ slug: 'x', language: 'pt-BR', title: 'T', status }) }],
  };
}

describe('getArticleBySlug', () => {
  beforeEach(() => consultar.mockReset());

  it('devolve artigo publicado', async () => {
    consultar.mockResolvedValue(resultado('published'));
    expect(await getArticleBySlug('x', 'pt-BR')).toMatchObject({ id: 'a1' });
  });

  it('esconde rascunho do site público', async () => {
    consultar.mockResolvedValue(resultado('draft'));
    expect(await getArticleBySlug('x', 'pt-BR')).toBeNull();
  });

  it('esconde documento sem status — na dúvida, não publica', async () => {
    consultar.mockResolvedValue(resultado(undefined));
    expect(await getArticleBySlug('x', 'pt-BR')).toBeNull();
  });

  it('deixa o Studio ver o rascunho quando pede explicitamente', async () => {
    consultar.mockResolvedValue(resultado('draft'));
    expect(await getArticleBySlug('x', 'pt-BR', null, true)).toMatchObject({ id: 'a1' });
  });

  it('devolve null quando não existe', async () => {
    consultar.mockResolvedValue({ empty: true, docs: [] });
    expect(await getArticleBySlug('x', 'pt-BR')).toBeNull();
  });
});

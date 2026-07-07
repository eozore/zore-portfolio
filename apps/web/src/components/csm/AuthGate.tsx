/* ============================================================
   AuthGate — proteção por senha simples para área interna CSM
   Armazena token em sessionStorage após validação via SHA-256
   ============================================================ */
'use client';

import { useState, useEffect } from 'react';
import styles from './AuthGate.module.css';

interface AuthGateProps {
  children: React.ReactNode;
}

const SESSION_KEY = 'csm_auth_token';

async function hashPassword(password: string): Promise<string> {
  const encoded = new TextEncoder().encode(password);
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoded);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export default function AuthGate({ children }: AuthGateProps) {
  const [authenticated, setAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored === 'authenticated') {
      setAuthenticated(true);
    }
    setChecking(false);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const hash = await hashPassword(password);
      const res = await fetch('/api/csm/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hash }),
      });

      if (res.ok) {
        sessionStorage.setItem(SESSION_KEY, 'authenticated');
        setAuthenticated(true);
      } else {
        setError('Senha incorreta. Tente novamente.');
        setPassword('');
      }
    } catch {
      setError('Erro de conexão. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  if (checking) {
    return (
      <div className={styles.splash}>
        <div className={styles.spinner} />
      </div>
    );
  }

  if (authenticated) return <>{children}</>;

  return (
    <div className={styles.wrapper}>
      {/* Decorative blobs */}
      <div className={styles.blobOrange} />
      <div className={styles.blobAmber} />

      <div className={styles.card}>
        {/* Logo */}
        <div className={styles.logo}>
          <span className={styles.logoText}>é</span>
          <span className={styles.logoSub}>ozoré</span>
        </div>

        <h1 className={styles.title}>Content Studio</h1>
        <p className={styles.subtitle}>Área interna de gestão de conteúdo</p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.inputWrapper}>
            <svg className={styles.inputIcon} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <input
              id="csm-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Senha de acesso"
              className={styles.input}
              autoFocus
              autoComplete="current-password"
            />
          </div>

          {error && <p className={styles.error}>{error}</p>}

          <button
            type="submit"
            disabled={loading || !password}
            className={styles.button}
          >
            {loading ? (
              <span className={styles.buttonSpinner} />
            ) : (
              <>
                <span>Acessar Studio</span>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

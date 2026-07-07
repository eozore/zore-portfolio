'use client';

import React from 'react';
import styles from './CaseStudyModal.module.css';

interface CaseStudyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginClick: () => void;
}

export default function CaseStudyModal({ isOpen, onClose, onLoginClick }: CaseStudyModalProps) {
  if (!isOpen) return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <button className={styles.closeButton} onClick={onClose} aria-label="Fechar modal">
          <i className="fa-solid fa-xmark" />
        </button>

        <div className={styles.caseHeader} style={{ justifyContent: 'center', flexDirection: 'column', textAlign: 'center' }}>
          <div className={styles.companyLogo} style={{ marginBottom: '0.5rem' }}>C</div>
          <div className={styles.caseTitle}>
            <h3>Cromex Solução Corporativa</h3>
            <span className={styles.tag}>Acesso Restrito</span>
          </div>
        </div>

        <div className={styles.bodyText}>
          <p>
            Esta plataforma de precificação, cálculo de CM1 e faturamento é confidencial e para uso exclusivo da Cromex.
          </p>
          <p style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
            Se você possui credenciais autorizadas, acesse a área do cliente. Caso deseje automatizar seus processos ou solicitar uma ferramenta sob medida para sua empresa, fale conosco.
          </p>
        </div>

        <div className={styles.buttonGroup}>
          <a 
            id="btn-case-cta"
            href="https://wa.me/5519997661003?text=Olá%20Victor,%20gostaria%20de%20conversar%20sobre%20uma%20plataforma%20de%20dados%20personalizada."
            target="_blank"
            rel="noopener noreferrer"
            className={styles.ctaButton}
          >
            <i className="fa-solid fa-paper-plane" />
            Entrar em Contato
          </a>

          <button 
            id="btn-case-login"
            className={styles.secondaryButton}
            onClick={() => {
              onClose();
              onLoginClick();
            }}
          >
            <i className="fa-solid fa-right-to-bracket" />
            Login como Usuário Cromex
          </button>
        </div>
      </div>
    </div>
  );
}

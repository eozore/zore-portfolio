'use client';

import React from 'react';

export default function LogoutButton() {
  const handleLogout = () => {
    // Clear cookie by setting past expiry date
    document.cookie = 'eozore_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax';
    
    // Reload page to re-trigger middleware logic
    window.location.reload();
  };

  return (
    <button
      id="btn-logout"
      onClick={handleLogout}
      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg border border-border bg-background text-sm font-medium text-text-muted hover:text-text-main hover:bg-secondary transition-all"
    >
      <i className="fa-solid fa-right-from-bracket" />
      Sair / Logout
    </button>
  );
}

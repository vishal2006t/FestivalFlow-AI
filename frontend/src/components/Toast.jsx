import React from 'react';

function Toast({ message, type = 'info', onClose }) {
  if (!message) return null;

  const bgStyle =
    type === 'error'
      ? 'var(--accent-rose)'
      : type === 'success'
      ? 'var(--accent-green)'
      : type === 'warning'
      ? 'var(--accent-amber)'
      : 'var(--accent-blue)';

  return (
    <div
      style={{
        position: 'fixed',
        top: '20px',
        right: '20px',
        zIndex: 9999,
        backgroundColor: bgStyle,
        color: '#ffffff',
        padding: '12px 20px',
        borderRadius: '8px',
        boxShadow: '0 10px 25px rgba(0, 0, 0, 0.3)',
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontSize: '14px',
        fontWeight: '500',
        animation: 'slideIn 0.3s ease-out'
      }}
    >
      <span>{type === 'error' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️'}</span>
      <span>{message}</span>
      {onClose && (
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#ffffff',
            cursor: 'pointer',
            fontSize: '16px',
            marginLeft: '8px',
            opacity: 0.8
          }}
        >
          ✕
        </button>
      )}
    </div>
  );
}

export default Toast;

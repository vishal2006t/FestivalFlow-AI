import React, { useState } from 'react';

/**
 * Redesigned FestivalFlow AI Operations Login Page
 * 
 * Guarantees horizontal and vertical centering across all viewports.
 * Professional, minimal public-transport operations UI with:
 * - Full-height viewport centering (Flexbox + margin: auto)
 * - Clear brand identity & subtitle
 * - Clean role switching (Depot Admin vs Bus Driver)
 * - Empty, unpolluted credentials (no hardcoded accounts or demo autofill)
 * - Password visibility toggle
 * - Inline validation & backend error messaging
 * - Accessible keyboard navigation & loading state prevention of multi-submits
 */
function LoginPage({
  initialRole = 'depot_admin',
  onLoginSuccess,
  onNavigate,
  theme,
  toggleTheme,
  apiBase
}) {
  const [role, setRole] = useState(initialRole === 'driver' ? 'driver' : 'depot_admin');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  const validateForm = () => {
    const errors = {};
    if (!username.trim()) {
      errors.username = 'Please enter your username or ID.';
    }
    if (!password) {
      errors.password = 'Please enter your password.';
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleRoleChange = (newRole) => {
    if (newRole === role) return;
    setRole(newRole);
    setError(null);
    setFieldErrors({});
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;

    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${apiBase}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username.trim(),
          password: password,
          role: role
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Invalid username or password for selected role.');
      }

      const redirectPath = role === 'driver' ? '/driver/dashboard' : '/admin/dashboard';
      onLoginSuccess(data.token, data.user, redirectPath);
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify network connectivity.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ff-login-viewport" data-theme={theme}>
      {/* Subtle Floating Top Controls */}
      <div className="ff-login-top-bar">
        <button
          type="button"
          onClick={() => onNavigate('/')}
          className="ff-top-nav-link"
          title="Return to Home Overview"
        >
          <span className="nav-arrow">←</span>
          <span>Home</span>
        </button>
        <button
          type="button"
          onClick={toggleTheme}
          className="ff-top-theme-btn"
          aria-label={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} mode`}
        >
          {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
        </button>
      </div>

      {/* Main Vertically & Horizontally Centered Card */}
      <div className="ff-login-card" role="main">
        {/* Brand Header */}
        <div className="ff-login-header">
          <div className="ff-brand-badge">
            <span className="ff-brand-icon">FF</span>
            <div className="ff-brand-text">
              <h1 className="ff-brand-title">FestivalFlow AI</h1>
              <span className="ff-brand-tag">TRANSIT COMMAND</span>
            </div>
          </div>
          <p className="ff-login-subtitle">Sign in to your operations dashboard</p>
        </div>

        {/* Role Selector Tabs */}
        <div className="ff-role-selector" role="tablist" aria-label="Operational Role Selection">
          <button
            type="button"
            role="tab"
            aria-selected={role === 'depot_admin'}
            aria-controls="login-form-panel"
            className={`ff-role-tab ${role === 'depot_admin' ? 'active' : ''}`}
            onClick={() => handleRoleChange('depot_admin')}
            disabled={loading}
          >
            <span className="ff-role-tab-icon">🏢</span>
            <span className="ff-role-tab-label">Depot Admin</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={role === 'driver'}
            aria-controls="login-form-panel"
            className={`ff-role-tab ${role === 'driver' ? 'active' : ''}`}
            onClick={() => handleRoleChange('driver')}
            disabled={loading}
          >
            <span className="ff-role-tab-icon">🚌</span>
            <span className="ff-role-tab-label">Bus Driver</span>
          </button>
        </div>

        {/* Inline Authentication Error Banner */}
        {error && (
          <div className="ff-auth-error-banner" role="alert" aria-live="assertive">
            <span className="ff-error-icon">⚠️</span>
            <span className="ff-error-message">{error}</span>
            <button
              type="button"
              className="ff-error-dismiss"
              onClick={() => setError(null)}
              aria-label="Dismiss error"
            >
              ×
            </button>
          </div>
        )}

        {/* Login Form */}
        <form
          id="login-form-panel"
          onSubmit={handleSubmit}
          className="ff-login-form"
          noValidate
        >
          {/* Username Field */}
          <div className={`ff-form-group ${fieldErrors.username ? 'has-error' : ''}`}>
            <label htmlFor="login-username" className="ff-field-label">
              <span>{role === 'depot_admin' ? 'Admin Username' : 'Driver Username'}</span>
              <span className="ff-required-star">*</span>
            </label>
            <div className="ff-input-wrapper">
              <span className="ff-input-icon">👤</span>
              <input
                id="login-username"
                name="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => {
                  setUsername(e.target.value);
                  if (fieldErrors.username) {
                    setFieldErrors((prev) => ({ ...prev, username: '' }));
                  }
                  if (error) setError(null);
                }}
                placeholder={role === 'depot_admin' ? 'e.g. admin_chennai' : 'e.g. driver_ramesh'}
                className="ff-text-input"
                disabled={loading}
                required
                autoFocus
              />
            </div>
            {fieldErrors.username && (
              <span className="ff-field-error-text" role="alert">
                {fieldErrors.username}
              </span>
            )}
          </div>

          {/* Password Field */}
          <div className={`ff-form-group ${fieldErrors.password ? 'has-error' : ''}`}>
            <label htmlFor="login-password" className="ff-field-label">
              <span>Password</span>
              <span className="ff-required-star">*</span>
            </label>
            <div className="ff-input-wrapper">
              <span className="ff-input-icon">🔒</span>
              <input
                id="login-password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (fieldErrors.password) {
                    setFieldErrors((prev) => ({ ...prev, password: '' }));
                  }
                  if (error) setError(null);
                }}
                placeholder="Enter password"
                className="ff-text-input ff-password-input"
                disabled={loading}
                required
              />
              <button
                type="button"
                className="ff-password-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                title={showPassword ? 'Hide password' : 'Show password'}
                tabIndex={0}
                disabled={loading}
              >
                {showPassword ? (
                  <svg
                    className="ff-eye-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg
                    className="ff-eye-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
            {fieldErrors.password && (
              <span className="ff-field-error-text" role="alert">
                {fieldErrors.password}
              </span>
            )}
          </div>

          {/* Role Status Note */}
          <div className="ff-role-status-note">
            <span className="ff-status-indicator-dot"></span>
            <span>
              Signing in as{' '}
              <strong>
                {role === 'depot_admin'
                  ? 'Depot Administrator (Central Operations)'
                  : 'Bus Driver (Field Telematics)'}
              </strong>
            </span>
          </div>

          {/* Prominent Full-Width Sign In Button */}
          <button
            id="ff-login-submit-btn"
            type="submit"
            className={`ff-submit-btn ${loading ? 'loading' : ''}`}
            disabled={loading}
          >
            {loading ? (
              <span className="ff-btn-content">
                <span className="ff-btn-spinner" aria-hidden="true"></span>
                <span>Authenticating...</span>
              </span>
            ) : (
              <span className="ff-btn-content">
                <span>Sign In to {role === 'depot_admin' ? 'Admin Dashboard' : 'Driver Field'}</span>
                <span className="ff-btn-arrow">→</span>
              </span>
            )}
          </button>
        </form>

        {/* Card Footer Security Indicator */}
        <div className="ff-login-card-footer">
          <div className="ff-security-badge">
            <span className="ff-lock-icon">🔒</span>
            <span>Authorized Personnel • Role-Enforced RBAC</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;

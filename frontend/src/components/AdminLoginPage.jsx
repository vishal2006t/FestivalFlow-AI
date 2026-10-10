import React, { useState, useEffect } from 'react';

// Pre-seeded development demo credentials from SQLite database
// In production builds, import.meta.env.DEV is replaced with 'false' and tree-shaken
const DEV_DEMO_ACCOUNTS = import.meta.env.DEV
  ? {
      depot_admin: {
        username: 'admin_chennai',
        password: 'Admin@Depot2026',
        role: 'depot_admin',
        roleLabel: 'Central Depot Admin (12 Scheduled Buses)',
        roleTitle: 'Depot Operations & Strategy'
      },
      driver: {
        username: 'driver_ramesh',
        password: 'Driver@2026',
        role: 'driver',
        roleLabel: 'Bus Driver (Assigned BUS-201 • Festival Express)',
        roleTitle: 'Field Operations & Telematics'
      }
    }
  : null;

function AdminLoginPage({ onLoginSuccess, onNavigate, theme, toggleTheme, apiBase, initialRole = 'depot_admin' }) {
  const [role, setRole] = useState(initialRole); // 'depot_admin' or 'driver'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationErrors, setValidationErrors] = useState({ username: '', password: '' });
  const [activeDemo, setActiveDemo] = useState(
    import.meta.env.DEV && DEV_DEMO_ACCOUNTS ? (DEV_DEMO_ACCOUNTS[initialRole] || DEV_DEMO_ACCOUNTS.depot_admin) : null
  );

  // Keep active demo synced with selected role
  useEffect(() => {
    if (import.meta.env.DEV && DEV_DEMO_ACCOUNTS) {
      setActiveDemo(DEV_DEMO_ACCOUNTS[role] || DEV_DEMO_ACCOUNTS.depot_admin);
    }
  }, [role]);

  // Sync initialRole if prop changes
  useEffect(() => {
    if (initialRole) {
      setRole(initialRole);
    }
  }, [initialRole]);

  const handleRoleChange = (newRole) => {
    setRole(newRole);
    setError(null);
    setValidationErrors({ username: '', password: '' });
  };

  // Pre-fill credentials on explicit click without auto-submitting or navigating
  const handleUseDemoCredentials = () => {
    if (activeDemo) {
      setUsername(activeDemo.username);
      setPassword(activeDemo.password);
      setError(null);
      setValidationErrors({ username: '', password: '' });
    }
  };

  const handleUsernameChange = (e) => {
    setUsername(e.target.value);
    if (validationErrors.username) {
      setValidationErrors((prev) => ({ ...prev, username: '' }));
    }
    if (error) setError(null);
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    if (validationErrors.password) {
      setValidationErrors((prev) => ({ ...prev, password: '' }));
    }
    if (error) setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    // Inline field validation
    const trimmedUsername = username.trim();
    const newValidation = { username: '', password: '' };
    let hasError = false;

    if (!trimmedUsername) {
      newValidation.username = 'User ID is required.';
      hasError = true;
    }

    if (!password) {
      newValidation.password = 'Password is required.';
      hasError = true;
    }

    if (hasError) {
      setValidationErrors(newValidation);
      return;
    }

    setValidationErrors({ username: '', password: '' });
    setLoading(true);

    const targetUrl = `${apiBase}/api/auth/login`;

    let response;
    try {
      response = await fetch(targetUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          username: trimmedUsername,
          password: password,
          role: role
        })
      });
    } catch (networkErr) {
      console.error('Login network error:', networkErr);
      setError(
        `Unable to reach the backend server at ${apiBase}. Please verify that the FestivalFlow AI backend is running on port 8081 and is accessible.`
      );
      setLoading(false);
      return;
    }

    try {
      const data = await response.json();

      if (!response.ok) {
        if (response.status === 401) {
          setError(data.detail || 'Invalid User ID or password.');
        } else if (response.status === 403) {
          setError(data.detail || `Access denied: Selected portal requires ${role === 'depot_admin' ? 'Depot Admin' : 'Driver'} privileges.`);
        } else if (response.status === 429) {
          setError(data.detail || 'Too many failed login attempts. Please wait 60 seconds before trying again.');
        } else if (response.status >= 500) {
          setError('Backend server encountered an error processing your request. Please try again later.');
        } else {
          setError(data.detail || `Authentication failed (HTTP ${response.status}).`);
        }
        return;
      }

      // Verify token and role from backend
      if (!data || !data.token || !data.user) {
        setError('Unexpected authentication response format received from server.');
        return;
      }

      // Route to the appropriate dashboard
      const redirectPath = role === 'driver' ? '/driver/dashboard' : '/admin/dashboard';
      onLoginSuccess(data.token, data.user, redirectPath);
    } catch (parseErr) {
      console.error('Response parse error:', parseErr);
      setError('Unable to parse the authentication response from the server.');
    } finally {
      setLoading(false);
    }
  };

  const isDepot = role === 'depot_admin';

  return (
    <div className={`login-page-container ${isDepot ? 'admin-portal-theme' : 'driver-portal-theme'}`}>
      {/* Independently positioned top navigation */}
      <header className="login-top-bar">
        <button
          type="button"
          onClick={() => onNavigate('/')}
          className="nav-link-btn"
          id="nav-home-btn"
        >
          ← Home
        </button>
        <button
          type="button"
          onClick={toggleTheme}
          className="theme-toggle-btn"
          id="login-theme-toggle-btn"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
        </button>
      </header>

      {/* Main horizontally and vertically centered login card wrapper */}
      <main className="login-content-wrapper">
        <div className="login-card-box">
          {/* Centered card header */}
          <div className="login-card-header">
            <div className="card-brand-header">
              <div className={`logo ${isDepot ? 'admin-logo' : 'driver-logo'}`}>FF</div>
              <h1 className="card-brand-title">FestivalFlow AI</h1>
            </div>

            <div className={`portal-header-tag ${isDepot ? 'admin-tag' : 'driver-tag'}`} id="login-portal-tag">
              <span className="portal-icon-tag" aria-hidden="true">
                {isDepot ? '🏢' : '🚌'}
              </span>
              <span>{isDepot ? 'DEPOT OPERATIONS & STRATEGY' : 'FIELD OPERATIONS & TELEMATICS'}</span>
            </div>

            <h2 className="login-card-title">
              {isDepot ? 'Depot Admin Sign In' : 'Bus Driver Sign In'}
            </h2>

            <p className="login-card-desc">
              {isDepot
                ? 'Sign in to access depot command, schedules & live reallocations'
                : 'Sign in to access assigned trips, staging bays & telematics'}
            </p>
          </div>

          {/* Role Selector Tabs */}
          <div className="role-selector-tabs" role="tablist" aria-label="Operational Role">
            <button
              type="button"
              role="tab"
              aria-selected={isDepot}
              className={`role-tab-btn ${isDepot ? 'active' : ''}`}
              onClick={() => handleRoleChange('depot_admin')}
              id="tab-role-admin"
            >
              <span className="role-tab-icon" aria-hidden="true">🏢</span>
              <div className="role-tab-text">
                <span className="role-title">Depot Operations & Strategy</span>
                <span className="role-desc">Depot Admin Command Portal</span>
              </div>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={!isDepot}
              className={`role-tab-btn ${!isDepot ? 'active' : ''}`}
              onClick={() => handleRoleChange('driver')}
              id="tab-role-driver"
            >
              <span className="role-tab-icon" aria-hidden="true">🚌</span>
              <div className="role-tab-text">
                <span className="role-title">Field Operations & Telematics</span>
                <span className="role-desc">Bus Driver Mobile Dashboard</span>
              </div>
            </button>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="auth-error-banner" role="alert" id="admin-login-error">
              <span className="error-icon" aria-hidden="true">⚠️</span>
              <span className="error-text">{error}</span>
            </div>
          )}

          {/* Demo Login Credentials Section (Development Only) */}
          {import.meta.env.DEV && activeDemo && (
            <div className="demo-credentials-card" id="demo-credentials-section">
              <div className="demo-credentials-header">
                <div className="demo-header-left">
                  <span className="demo-icon" aria-hidden="true">⚡</span>
                  <span className="demo-title">Demo Login Credentials</span>
                </div>
                <span className="demo-badge">DEV MODE ONLY</span>
              </div>
              <div className="demo-credentials-details">
                <div className="demo-field-row">
                  <span className="demo-field-label">User ID:</span>
                  <code className="demo-field-value" id="demo-preview-userid">{activeDemo.username}</code>
                </div>
                <div className="demo-field-row">
                  <span className="demo-field-label">Password:</span>
                  <code className="demo-field-value" id="demo-preview-password">{activeDemo.password}</code>
                </div>
                <div className="demo-field-row">
                  <span className="demo-field-label">Role:</span>
                  <span className="demo-role-text">{activeDemo.roleLabel}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleUseDemoCredentials}
                className="use-demo-btn"
                id="btn-use-demo-creds"
              >
                Use Demo Credentials
              </button>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            <div className="form-group">
              <label htmlFor="admin-username">User ID</label>
              <input
                id="admin-username"
                name="username"
                type="text"
                value={username}
                onChange={handleUsernameChange}
                placeholder={isDepot ? 'e.g. admin_chennai' : 'e.g. driver_ramesh'}
                required
                disabled={loading}
                autoComplete="username"
                className={validationErrors.username ? 'input-error' : ''}
              />
              {validationErrors.username && (
                <span className="inline-error-text" role="alert">
                  {validationErrors.username}
                </span>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="admin-password">Password</label>
              <div className="password-input-wrapper">
                <input
                  id="admin-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={handlePasswordChange}
                  placeholder="Enter your password"
                  required
                  disabled={loading}
                  autoComplete="current-password"
                  className={validationErrors.password ? 'input-error' : ''}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="password-toggle-btn"
                  id="toggle-admin-password-btn"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={0}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              {validationErrors.password && (
                <span className="inline-error-text" role="alert">
                  {validationErrors.password}
                </span>
              )}
            </div>

            <button
              id="admin-submit-btn"
              type="submit"
              disabled={loading}
              className={`submit-auth-btn ${isDepot ? 'admin-btn' : 'driver-btn'}`}
            >
              {loading ? (
                <span className="spinner-wrap">
                  <span className="loading-spinner" aria-hidden="true" />
                  Authenticating...
                </span>
              ) : (
                `Sign In to ${isDepot ? 'Depot Operations' : 'Field Operations'} →`
              )}
            </button>
          </form>

          {/* Secondary Switch Link */}
          <footer className="portal-switch-prompt">
            <span>
              {isDepot ? 'Looking for driver operations?' : 'Looking for depot control?'}
            </span>
            <button
              type="button"
              onClick={() => handleRoleChange(isDepot ? 'driver' : 'depot_admin')}
              className="switch-portal-link"
              id="switch-portal-link-btn"
            >
              {isDepot
                ? 'Switch to Field Operations & Telematics →'
                : 'Switch to Depot Operations & Strategy →'}
            </button>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default AdminLoginPage;

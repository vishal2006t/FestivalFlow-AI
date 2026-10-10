import React, { useState, useEffect } from 'react';
import './App.css';
import LandingPage from './components/LandingPage';
import AdminLoginPage from './components/AdminLoginPage';
import DriverLoginPage from './components/DriverLoginPage';
import DepotAdminDashboard from './components/DepotAdminDashboard';
import BusDriverDashboard from './components/BusDriverDashboard';
import Toast from './components/Toast';

const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/$/, '');
  }
  if (typeof window !== 'undefined' && window.location && window.location.hostname) {
    const protocol = window.location.protocol || 'http:';
    const hostname = window.location.hostname;
    return `${protocol}//${hostname}:8081`;
  }
  return 'http://127.0.0.1:8081';
};

const API_BASE = getApiBaseUrl();

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('ff_token') || null);
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem('ff_user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  const [currentPath, setCurrentPath] = useState(() => window.location.pathname || '/');
  const [theme, setTheme] = useState(() => localStorage.getItem('ff_theme') || 'dark');
  const [toast, setToast] = useState({ message: '', type: 'info' });

  // Listen for browser forward/back buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname || '/');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Sync theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('ff_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => {
      setToast({ message: '', type: 'info' });
    }, 4000);
  };

  const navigate = (newPath) => {
    if (window.location.pathname !== newPath) {
      window.history.pushState({}, '', newPath);
    }
    setCurrentPath(newPath);
  };

  const handleLoginSuccess = (newToken, newUser, redirectPath) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem('ff_token', newToken);
    localStorage.setItem('ff_user', JSON.stringify(newUser));
    showToast(`Welcome, ${newUser.full_name || newUser.username}!`, 'success');
    navigate(redirectPath);
  };

  const handleLogout = async (redirectPath = '/') => {
    if (token) {
      try {
        await fetch(`${API_BASE}/api/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` }
        });
      } catch (err) {
        console.error('Logout error:', err);
      }
    }
    setToken(null);
    setUser(null);
    localStorage.removeItem('ff_token');
    localStorage.removeItem('ff_user');
    showToast('Signed out successfully.', 'info');
    navigate(redirectPath);
  };

  // ==================== Routing & Role Authorization Logic ====================

  const renderRoute = () => {
    const path = currentPath.toLowerCase().replace(/\/$/, '') || '/';

    // 1. Landing Page: '/'
    if (path === '/') {
      return (
        <LandingPage
          onNavigate={navigate}
          theme={theme}
          toggleTheme={toggleTheme}
        />
      );
    }

    // 2. Admin Portal Root: '/admin'
    if (path === '/admin') {
      if (token && user && (user.role === 'depot_admin' || user.role === 'admin')) {
        navigate('/admin/dashboard');
        return null;
      }
      navigate('/admin/login');
      return null;
    }

    // 2.5 General Login Page: '/login'
    if (path === '/login') {
      if (token && user) {
        if (user.role === 'driver') {
          navigate('/driver/dashboard');
        } else {
          navigate('/admin/dashboard');
        }
        return null;
      }
      return (
        <AdminLoginPage
          onLoginSuccess={handleLoginSuccess}
          onNavigate={navigate}
          theme={theme}
          toggleTheme={toggleTheme}
          apiBase={API_BASE}
          initialRole="depot_admin"
        />
      );
    }

    // 3. Admin Login Page: '/admin/login'
    if (path === '/admin/login') {
      if (token && user && (user.role === 'depot_admin' || user.role === 'admin')) {
        navigate('/admin/dashboard');
        return null;
      }
      return (
        <AdminLoginPage
          onLoginSuccess={handleLoginSuccess}
          onNavigate={navigate}
          theme={theme}
          toggleTheme={toggleTheme}
          apiBase={API_BASE}
          initialRole="depot_admin"
        />
      );
    }

    // 4. Admin Dashboard: '/admin/dashboard'
    if (path === '/admin/dashboard') {
      if (!token || !user) {
        navigate('/admin/login');
        return null;
      }
      if (user.role !== 'depot_admin' && user.role !== 'admin') {
        return (
          <div className="unauthorized-container">
            <div className="unauthorized-card">
              <span className="unauth-icon">🚫</span>
              <h2>403 Forbidden: Depot Admin Privileges Required</h2>
              <p>Your logged in account (<strong>{user.username}</strong>) has the <strong>{user.role}</strong> role and cannot access the Depot Command Dashboard.</p>
              <div className="unauth-actions">
                <button onClick={() => navigate('/driver/dashboard')} className="action-btn">
                  Go to Driver Field Dashboard
                </button>
                <button onClick={() => handleLogout('/admin/login')} className="action-btn secondary">
                  Sign In as Depot Admin
                </button>
              </div>
            </div>
          </div>
        );
      }
      return (
        <DepotAdminDashboard
          user={user}
          token={token}
          onLogout={() => handleLogout('/admin/login')}
          theme={theme}
          toggleTheme={toggleTheme}
          apiBase={API_BASE}
          showToast={showToast}
          onNavigate={navigate}
        />
      );
    }

    // 5. Driver Portal Root: '/driver'
    if (path === '/driver') {
      if (token && user && user.role === 'driver') {
        navigate('/driver/dashboard');
        return null;
      }
      navigate('/driver/login');
      return null;
    }

    // 6. Driver Login Page: '/driver/login'
    if (path === '/driver/login') {
      if (token && user && user.role === 'driver') {
        navigate('/driver/dashboard');
        return null;
      }
      return (
        <AdminLoginPage
          onLoginSuccess={handleLoginSuccess}
          onNavigate={navigate}
          theme={theme}
          toggleTheme={toggleTheme}
          apiBase={API_BASE}
          initialRole="driver"
        />
      );
    }

    // 7. Driver Dashboard: '/driver/dashboard'
    if (path === '/driver/dashboard') {
      if (!token || !user) {
        navigate('/driver/login');
        return null;
      }
      if (user.role !== 'driver') {
        return (
          <div className="unauthorized-container">
            <div className="unauthorized-card">
              <span className="unauth-icon">🚫</span>
              <h2>403 Forbidden: Bus Driver Account Required</h2>
              <p>Your logged in account (<strong>{user.username}</strong>) has the <strong>{user.role}</strong> role and cannot access driver assignments.</p>
              <div className="unauth-actions">
                <button onClick={() => navigate('/admin/dashboard')} className="action-btn">
                  Return to Admin Dashboard
                </button>
                <button onClick={() => handleLogout('/driver/login')} className="action-btn secondary">
                  Sign In as Bus Driver
                </button>
              </div>
            </div>
          </div>
        );
      }
      return (
        <BusDriverDashboard
          user={user}
          token={token}
          onLogout={() => handleLogout('/driver/login')}
          theme={theme}
          toggleTheme={toggleTheme}
          apiBase={API_BASE}
          showToast={showToast}
          onNavigate={navigate}
        />
      );
    }

    // 8. Legacy /dashboard fallback redirect
    if (path === '/dashboard') {
      if (token && user) {
        if (user.role === 'driver') {
          navigate('/driver/dashboard');
        } else {
          navigate('/admin/dashboard');
        }
      } else {
        navigate('/');
      }
      return null;
    }

    // 9. Unknown Path Fallback -> Landing Page
    return (
      <div className="notfound-container">
        <div className="unauthorized-card">
          <h2>Page Not Found</h2>
          <p>Route <code>{currentPath}</code> does not exist.</p>
          <button onClick={() => navigate('/')} className="action-btn">
            Return to FestivalFlow AI Home
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="festival-app-root">
      {toast.message && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast({ message: '', type: 'info' })}
        />
      )}
      {renderRoute()}
    </div>
  );
}

export default App;

import React from 'react';

function LandingPage({ onNavigate, theme, toggleTheme }) {
  return (
    <div className="landing-page-container">
      {/* Header Bar */}
      <header className="landing-header">
        <div className="brand-bar">
          <div className="logo">FF</div>
          <div>
            <h1 className="nav-title">FestivalFlow AI</h1>
            <p className="nav-subtitle">Intelligent Festival Crowd Dispersal & Transit Redistribution</p>
          </div>
        </div>
        <div className="nav-actions">
          <button
            onClick={toggleTheme}
            className="theme-toggle-btn"
            title="Toggle Light/Dark Theme"
          >
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <main className="landing-main">
        <section className="landing-hero">
          <div className="hero-badge">
            <span className="pulse-indicator"></span> Operational Transit AI • Fixed-Fleet Redistribution
          </div>
          <h2 className="hero-heading">
            Solve Massive Post-Festival Crowd Surges with Predictive Transit Optimization
          </h2>
          <p className="hero-description">
            40,000 attendees disperse in 2 hours. Main Bus Stand has only 12 scheduled buses while Tech Park North
            has 4 idle buses just 2 km away. FestivalFlow AI predicts passenger queue surges and recommends
            proactive bus redistribution before crowds overwhelm the network.
          </p>

          <div className="scenario-stats-pill">
            <div className="pill-item">
              <span className="pill-num">40,000</span>
              <span className="pill-label">Exiting Attendees</span>
            </div>
            <div className="pill-divider"></div>
            <div className="pill-item">
              <span className="pill-num">17</span>
              <span className="pill-label">Strictly Fixed Fleet</span>
            </div>
            <div className="pill-divider"></div>
            <div className="pill-item">
              <span className="pill-num">2 km</span>
              <span className="pill-label">Staging Distance</span>
            </div>
            <div className="pill-divider"></div>
            <div className="pill-item">
              <span className="pill-num">100%</span>
              <span className="pill-label">Manual Dispatch Gate</span>
            </div>
          </div>
        </section>

        {/* Portals Selection Grid */}
        <section className="portals-section">
          <h3 className="section-title">Select Your Operations Portal</h3>
          <p className="section-subtitle">Dedicated, role-separated command environments for transit authorities and drivers.</p>

          <div className="portal-cards-grid">
            {/* Admin Portal Card */}
            <div className="portal-card admin-card">
              <div className="portal-badge admin-badge">Depot Operations & Strategy</div>
              <div className="portal-icon">🏢</div>
              <h4 className="portal-title">Depot Admin Portal</h4>
              <p className="portal-desc">
                Authorized command dashboard for transit controllers. Monitor real-time passenger predictions,
                manage fixed-fleet reallocation plans, review AI briefings, inspect camera telemetry, and authorize dispatches.
              </p>

              <ul className="portal-features-list">
                <li><span>✓</span> Live Recalculation Engine (Constraint-1)</li>
                <li><span>✓</span> Fixed-Fleet Optimization & Staging Times</li>
                <li><span>✓</span> Advisory Reallocations & Manual Approval Gate</li>
                <li><span>✓</span> Camera Vision AI & Night Safety Monitoring</li>
                <li><span>✓</span> Dynamic Recalculation Engine (Weather, Crowd & Telematics)</li>
              </ul>

              <button
                id="btn-portal-admin"
                onClick={() => onNavigate('/admin/login')}
                className="portal-action-btn admin-btn"
              >
                Access Depot Admin Portal →
              </button>
              <div className="portal-url-hint">Route: <code>/admin/login</code></div>
            </div>

            {/* Driver Portal Card */}
            <div className="portal-card driver-card">
              <div className="portal-badge driver-badge">Field Operations & Telematics</div>
              <div className="portal-icon">🚌</div>
              <h4 className="portal-title">Bus Driver Field Portal</h4>
              <p className="portal-desc">
                Streamlined mobile-first interface for bus operators. View your assigned bus,
                route instructions, staging bays, departure times, and submit instant delay or breakdown reports.
              </p>

              <ul className="portal-features-list">
                <li><span>✓</span> Personal Assigned Bus & Route Details</li>
                <li><span>✓</span> Departure & Staging Time Instructions</li>
                <li><span>✓</span> Permitted Status: Ready, En Route, Arrived, Boarding, Completed</li>
                <li><span>✓</span> Instant Delay, Breakdown & Safety Reporting</li>
                <li><span>✓</span> Direct Dispatch Alerts from Depot Command</li>
              </ul>

              <button
                id="btn-portal-driver"
                onClick={() => onNavigate('/driver/login')}
                className="portal-action-btn driver-btn"
              >
                Access Bus Driver Portal →
              </button>
              <div className="portal-url-hint">Route: <code>/driver/login</code></div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-status-bar">
          <span className="status-dot"></span> Backend Engine: <strong>FastAPI Operational (Port 8081)</strong>
          <span className="dot-sep">•</span>
          <span>Database: <strong>SQLite (Primary) + MongoDB Ready</strong></span>
          <span className="dot-sep">•</span>
          <span>AI Explanations: <strong>OpenRouter Adapter Active</strong></span>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;

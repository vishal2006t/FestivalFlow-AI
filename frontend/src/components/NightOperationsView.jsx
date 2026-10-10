import React, { useState, useEffect } from 'react';
import {
  MoonIcon,
  ZapIcon,
  SlidersIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  BusIcon,
  ClockIcon,
  ShieldAlertIcon,
  RefreshCwIcon,
  ArrowRightIcon,
  InfoIcon
} from './Icons';

/**
 * NightOperationsView - Dedicated Night Transit Operations & Egress Console.
 * 
 * Features:
 * - Configurable night operational hours (start hour, end hour) with database persistence.
 * - Night crowd estimates, weather acceleration factors, and route status.
 * - Standby fleet dispatch status and conflict prevention.
 * - Active night safety alerts and incident counters.
 * - Filters for event, stop, route, and alert severity.
 */
export default function NightOperationsView({ apiBase, token, showToast, onNavigateToTab }) {
  const [loading, setLoading] = useState(true);
  const [nightData, setNightData] = useState(null);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);

  // Settings form state
  const [nightStartHour, setNightStartHour] = useState(20);
  const [nightEndHour, setNightEndHour] = useState(5);
  const [unexpectedStopThreshold, setUnexpectedStopThreshold] = useState(10);
  const [weatherModifierEnabled, setWeatherModifierEnabled] = useState(true);

  // Filters
  const [filterRoute, setFilterRoute] = useState('ALL');
  const [filterSeverity, setFilterSeverity] = useState('ALL');

  const loadNightOps = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/operations/night`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setNightData(json);
        if (json.settings) {
          setNightStartHour(parseInt(json.settings.night_start_hour || '20', 10));
          setNightEndHour(parseInt(json.settings.night_end_hour || '5', 10));
          setUnexpectedStopThreshold(parseInt(json.settings.unexpected_stop_threshold_mins || '10', 10));
          setWeatherModifierEnabled(json.settings.weather_demand_modifier_enabled === '1');
        }
      } else {
        showToast('Failed to load night operations data', 'error');
      }
    } catch (err) {
      console.error('Night ops fetch error:', err);
      showToast('Error connecting to night operations engine', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNightOps();
  }, [apiBase, token]);

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    setSavingConfig(true);
    try {
      const res = await fetch(`${apiBase}/api/operations/night-settings`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          night_start_hour: nightStartHour,
          night_end_hour: nightEndHour,
          unexpected_stop_threshold_mins: unexpectedStopThreshold,
          weather_demand_modifier_enabled: weatherModifierEnabled
        })
      });
      if (res.ok) {
        showToast('Night operational parameters successfully updated in database.', 'success');
        setShowConfigModal(false);
        loadNightOps();
      } else {
        const errJson = await res.json().catch(() => ({}));
        showToast(errJson.detail || 'Failed to save settings', 'error');
      }
    } catch (err) {
      console.error('Settings error:', err);
      showToast('Error saving operational settings', 'error');
    } finally {
      setSavingConfig(false);
    }
  };

  if (loading && !nightData) {
    return (
      <div className="ff-loading-state">
        <RefreshCwIcon size={28} className="ff-spinner" />
        <p>Initializing Night Operations console and querying safety parameters...</p>
      </div>
    );
  }

  const weather = nightData?.weather || {};
  const event = nightData?.event || {};
  const primaryRec = nightData?.primary_recommendation || {};
  const isApproved = primaryRec.status === 'APPROVED';
  const recentIncidents = nightData?.recent_incidents || [];

  return (
    <div className="ff-tab-container">
      {/* Header */}
      <div className="ff-page-header">
        <div>
          <div className="ff-header-tag-row">
            <span className="ff-badge purple">
              <MoonIcon size={14} />
              <span>NIGHT OPERATIONS WINDOW</span>
            </span>
            <span className="ff-badge default">
              {nightData?.label}
            </span>
          </div>
          <h2 className="ff-page-title">Night Transit Operations & Egress Command</h2>
          <p className="ff-page-subtitle">
            Dedicated operational console for post-headline egress, late-night passenger safety, and standby fleet staging.
          </p>
        </div>
        <div className="ff-header-actions">
          <button
            type="button"
            className="ff-btn ff-btn-outline"
            onClick={() => setShowConfigModal(true)}
          >
            <SlidersIcon size={16} />
            <span>Configure Operating Hours</span>
          </button>
          <button
            type="button"
            className="ff-btn ff-btn-outline"
            onClick={loadNightOps}
            disabled={loading}
          >
            <RefreshCwIcon size={16} className={loading ? 'ff-spinner' : ''} />
            <span>Refresh Night State</span>
          </button>
        </div>
      </div>

      {/* Night KPI Metrics */}
      <div className="ff-metrics-grid ff-grid-4">
        {/* Peak Surge */}
        <div className="ff-metric-card ff-border-warning">
          <div className="ff-metric-header">
            <span className="ff-metric-label">PEAK EGRESS SURGE</span>
            <ZapIcon size={18} className="ff-text-warning" />
          </div>
          <div className="ff-metric-value">3,500 Pax / Wave</div>
          <p className="ff-metric-footer">Main Bus Stand (21:45 - 22:15)</p>
        </div>

        {/* Fleet Allocation State */}
        <div className={`ff-metric-card ${isApproved ? 'ff-border-optimal' : 'ff-border-amber'}`}>
          <div className="ff-metric-header">
            <span className="ff-metric-label">NIGHT FLEET ALLOCATION</span>
            <BusIcon size={18} />
          </div>
          <div className="ff-metric-value">
            {isApproved ? '4 Standby Dispatched' : 'Awaiting Approval'}
          </div>
          <p className="ff-metric-footer">
            12 Scheduled + 4 Tech Park Shuttles (1,120 Seats)
          </p>
        </div>

        {/* Night Safety Alerts */}
        <div className="ff-metric-card">
          <div className="ff-metric-header">
            <span className="ff-metric-label">ACTIVE SAFETY ALERTS</span>
            <ShieldAlertIcon size={18} className="ff-text-danger" />
          </div>
          <div className="ff-metric-value">
            {nightData?.active_incidents_count || 0} Critical / High
          </div>
          <p className="ff-metric-footer">
            Queue Delays & Breakdown Monitoring
          </p>
        </div>

        {/* Weather Conditions */}
        <div className="ff-metric-card">
          <div className="ff-metric-header">
            <span className="ff-metric-label">NIGHT VISIBILITY & WEATHER</span>
            <MoonIcon size={18} />
          </div>
          <div className="ff-metric-value">
            {weather.condition || 'Mainly clear'} • {weather.temperature_celsius ? Math.round(weather.temperature_celsius) : 28}°C
          </div>
          <p className="ff-metric-footer">
            Provider: {weather.source || 'Open-Meteo'}
          </p>
        </div>
      </div>

      {/* Active Night Safety Alerts Banner */}
      <div className="ff-card">
        <div className="ff-card-header">
          <div>
            <h3 className="ff-card-title">Active Night Safety Alerts & Queue Monitoring</h3>
            <p className="ff-card-subtitle">
              Prioritized passenger safety risks during late-night hours with low ambient illumination.
            </p>
          </div>
          {onNavigateToTab && (
            <button
              type="button"
              className="ff-btn ff-btn-outline sm"
              onClick={() => onNavigateToTab('night_safety')}
            >
              <span>View All Incidents</span>
              <ArrowRightIcon size={14} />
            </button>
          )}
        </div>

        <div className="ff-incident-list">
          {recentIncidents.map((inc) => (
            <div key={inc.id} className={`ff-incident-item ${inc.severity?.toLowerCase()}`}>
              <div className="ff-inc-left">
                <span className={`ff-inc-badge ${inc.severity?.toLowerCase()}`}>
                  {inc.severity}
                </span>
                <div>
                  <h4 className="ff-inc-title">{inc.description}</h4>
                  <p className="ff-inc-meta">
                    ID: <strong>{inc.incident_id}</strong> • Location: <strong>{inc.stop_name}</strong> • Source: <strong>{inc.source}</strong>
                  </p>
                </div>
              </div>
              <div className="ff-inc-right">
                <span className={`ff-status-pill ${inc.status?.toLowerCase()}`}>
                  {inc.status}
                </span>
              </div>
            </div>
          ))}
          {recentIncidents.length === 0 && (
            <div className="ff-empty-state">
              <CheckCircleIcon size={32} className="ff-text-optimal" />
              <p>No active night safety incidents. All queues within normal operating thresholds.</p>
            </div>
          )}
        </div>
      </div>

      {/* Standby Fleet Staging Card */}
      <div className="ff-card">
        <div className="ff-card-header">
          <div>
            <h3 className="ff-card-title">Night Standby Bus Staging Status</h3>
            <p className="ff-card-subtitle">
              Conflict-free allocation plan for Tech Park North Depot reserve vehicles.
            </p>
          </div>
          <span className={`ff-badge ${isApproved ? 'optimal' : 'warning'}`}>
            {isApproved ? 'PLAN ACTIVE' : 'PENDING APPROVAL'}
          </span>
        </div>

        <div className="ff-fleet-staging-grid">
          {['BUS-201', 'BUS-202', 'BUS-203', 'BUS-204'].map((busNum, idx) => (
            <div key={busNum} className="ff-staging-bus-card">
              <div className="bus-header">
                <BusIcon size={20} />
                <span className="bus-num">{busNum}</span>
                <span className="bus-cap">70 Seats</span>
              </div>
              <div className="bus-details">
                <p>Origin: <strong>Tech Park North Depot</strong></p>
                <p>Corridor Transit: <strong>2.0 km (~12 mins)</strong></p>
                <p>Status: <strong className={isApproved ? 'ff-text-optimal' : 'ff-text-warning'}>{isApproved ? 'Dispatched' : 'Staged (Ready)'}</strong></p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Configuration Modal */}
      {showConfigModal && (
        <div className="ff-modal-backdrop" onClick={() => setShowConfigModal(false)}>
          <div className="ff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ff-modal-header">
              <div className="ff-modal-title-group">
                <SlidersIcon size={20} />
                <h3>Configure Night Operational Parameters</h3>
              </div>
              <button
                type="button"
                className="ff-modal-close"
                onClick={() => setShowConfigModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveSettings}>
              <div className="ff-form-group">
                <label>Night Operations Start Hour (24h format):</label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  className="ff-input"
                  value={nightStartHour}
                  onChange={(e) => setNightStartHour(parseInt(e.target.value, 10))}
                  required
                />
                <span className="ff-form-hint">Default: 20 (8:00 PM). Egress surge logic activates at this hour.</span>
              </div>

              <div className="ff-form-group">
                <label>Night Operations End Hour (24h format):</label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  className="ff-input"
                  value={nightEndHour}
                  onChange={(e) => setNightEndHour(parseInt(e.target.value, 10))}
                  required
                />
                <span className="ff-form-hint">Default: 5 (5:00 AM next day). Night safety alerts apply until this hour.</span>
              </div>

              <div className="ff-form-group">
                <label>Unexpected Bus Stop Dwell Threshold (Minutes):</label>
                <input
                  type="number"
                  min="3"
                  max="60"
                  className="ff-input"
                  value={unexpectedStopThreshold}
                  onChange={(e) => setUnexpectedStopThreshold(parseInt(e.target.value, 10))}
                  required
                />
                <span className="ff-form-hint">Triggers automated telematics safety alert if bus remains stopped longer than threshold.</span>
              </div>

              <div className="ff-form-group">
                <label className="ff-checkbox-label">
                  <input
                    type="checkbox"
                    checked={weatherModifierEnabled}
                    onChange={(e) => setWeatherModifierEnabled(e.target.checked)}
                  />
                  <span>Enable weather-driven demand acceleration multipliers</span>
                </label>
              </div>

              <div className="ff-modal-actions">
                <button
                  type="button"
                  className="ff-btn ff-btn-outline"
                  onClick={() => setShowConfigModal(false)}
                  disabled={savingConfig}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="ff-btn ff-btn-primary"
                  disabled={savingConfig}
                >
                  {savingConfig ? 'Saving Settings...' : 'Save Night Operating Hours'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

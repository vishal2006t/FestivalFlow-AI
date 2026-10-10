import React, { useState, useEffect } from 'react';
import {
  ShieldAlertIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  BusIcon,
  UsersIcon,
  RefreshCwIcon,
  PhoneIcon,
  PlusIcon,
  XIcon,
  CheckIcon
} from './Icons';

/**
 * NightSafetyIncidentsView - Dedicated Night Safety Monitoring & Incident Lifecycle Board.
 * 
 * Features:
 * - Real incident inputs (driver reports, telematics dwell thresholds, operator inputs).
 * - Supported conditions: Breakdowns, unexpected stops, route deviations, crowd surges, assistance requests.
 * - Immutable alert IDs, severity classifications, and audit action histories.
 * - Interactive controls for Acknowledging, Resolving, and Escalating incidents.
 * - Manual operator incident report creation.
 */
export default function NightSafetyIncidentsView({
  apiBase,
  token,
  showToast,
  user,
  onEscalateIncident
}) {
  const [loading, setLoading] = useState(true);
  const [incidents, setIncidents] = useState([]);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [typeFilter, setTypeFilter] = useState('ALL');

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newIncident, setNewIncident] = useState({
    incident_type: 'NIGHT_OVERCROWDING',
    severity: 'HIGH',
    stop_id: 'STOP_MAIN',
    stop_name: 'Main Bus Stand (Festival Arena)',
    bus_number: 'BUS-101',
    description: '',
    supporting_evidence: '',
    assigned_responder: 'Station Supervisor Bay 2'
  });

  // Action state
  const [actionInProgress, setActionInProgress] = useState(null);

  const fetchIncidents = async () => {
    setLoading(true);
    try {
      let url = `${apiBase}/api/incidents?`;
      if (statusFilter !== 'ALL') url += `status=${statusFilter}&`;
      if (severityFilter !== 'ALL') url += `severity=${severityFilter}&`;
      if (typeFilter !== 'ALL') url += `incident_type=${typeFilter}&`;

      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setIncidents(json);
      } else {
        showToast('Failed to load safety incidents', 'error');
      }
    } catch (err) {
      console.error('Fetch incidents error:', err);
      showToast('Error connecting to incident service', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [apiBase, token, statusFilter, severityFilter, typeFilter]);

  const handleUpdateStatus = async (incidentId, newStatus, actionNote) => {
    setActionInProgress(incidentId);
    try {
      const res = await fetch(`${apiBase}/api/incidents/${incidentId}/status`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          status: newStatus,
          action_note: actionNote
        })
      });
      if (res.ok) {
        showToast(`Incident ${incidentId} marked as ${newStatus}.`, 'success');
        fetchIncidents();
      } else {
        showToast('Failed to update incident status', 'error');
      }
    } catch (err) {
      console.error('Status update error:', err);
      showToast('Error updating incident', 'error');
    } finally {
      setActionInProgress(null);
    }
  };

  const handleCreateIncident = async (e) => {
    e.preventDefault();
    if (!newIncident.description.trim()) {
      showToast('Please provide an incident description', 'error');
      return;
    }
    setCreating(true);
    try {
      const res = await fetch(`${apiBase}/api/incidents`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newIncident)
      });
      if (res.ok) {
        showToast('Safety incident logged successfully with audit provenance.', 'success');
        setShowCreateModal(false);
        setNewIncident({
          incident_type: 'NIGHT_OVERCROWDING',
          severity: 'HIGH',
          stop_id: 'STOP_MAIN',
          stop_name: 'Main Bus Stand (Festival Arena)',
          bus_number: 'BUS-101',
          description: '',
          supporting_evidence: '',
          assigned_responder: 'Station Supervisor Bay 2'
        });
        fetchIncidents();
      } else {
        showToast('Failed to log incident', 'error');
      }
    } catch (err) {
      console.error('Create incident error:', err);
      showToast('Error filing incident', 'error');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="ff-tab-container">
      {/* Header */}
      <div className="ff-page-header">
        <div>
          <h2 className="ff-page-title">Night Safety & Incident Monitoring</h2>
          <p className="ff-page-subtitle">
            Real-time operational condition tracking, automated telematics safety rules, and emergency resolution management.
          </p>
        </div>
        <div className="ff-header-actions">
          <button
            type="button"
            className="ff-btn ff-btn-primary"
            onClick={() => setShowCreateModal(true)}
          >
            <span>+ Report Operational Incident</span>
          </button>
          <button
            type="button"
            className="ff-btn ff-btn-outline"
            onClick={fetchIncidents}
            disabled={loading}
          >
            <RefreshCwIcon size={16} className={loading ? 'ff-spinner' : ''} />
            <span>Refresh Alerts</span>
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="ff-toolbar">
        <div className="ff-toolbar-group">
          <span className="ff-toolbar-label">Status:</span>
          {['ALL', 'NEW', 'ACKNOWLEDGED', 'ESCALATED', 'RESOLVED'].map((st) => (
            <button
              key={st}
              type="button"
              className={`ff-pill-btn ${statusFilter === st ? 'active' : ''}`}
              onClick={() => setStatusFilter(st)}
            >
              {st}
            </button>
          ))}
        </div>

        <div className="ff-toolbar-group">
          <span className="ff-toolbar-label">Severity:</span>
          <select
            className="ff-select"
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>

        <div className="ff-toolbar-group">
          <span className="ff-toolbar-label">Condition:</span>
          <select
            className="ff-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="ALL">All Types</option>
            <option value="NIGHT_OVERCROWDING">Night Overcrowding</option>
            <option value="BREAKDOWN">Vehicle Breakdown</option>
            <option value="UNEXPECTED_STOP">Unexpected Stop (&gt;10 min)</option>
            <option value="ROUTE_DEVIATION">Route Deviation</option>
            <option value="DRIVER_ASSISTANCE">Driver Assistance SOS</option>
          </select>
        </div>
      </div>

      {/* Incidents Grid */}
      <div className="ff-incidents-grid">
        {incidents.map((inc) => {
          const isBusy = actionInProgress === inc.incident_id;
          return (
            <div key={inc.id} className={`ff-incident-card ${inc.severity?.toLowerCase()}`}>
              <div className="ff-inc-card-header">
                <div className="ff-inc-id-row">
                  <span className="ff-inc-id">{inc.incident_id}</span>
                  <span className={`ff-badge ${inc.severity?.toLowerCase()}`}>
                    {inc.severity}
                  </span>
                  <span className="ff-badge default">
                    {inc.incident_type?.replace(/_/g, ' ')}
                  </span>
                </div>
                <span className={`ff-status-pill ${inc.status?.toLowerCase()}`}>
                  {inc.status}
                </span>
              </div>

              <div className="ff-inc-card-body">
                <h4 className="ff-inc-card-title">{inc.description}</h4>

                <div className="ff-inc-evidence-box">
                  <span className="evidence-label">SUPPORTING EVIDENCE:</span>
                  <p>{inc.supporting_evidence || 'Direct operator observational report.'}</p>
                </div>

                <div className="ff-inc-meta-grid">
                  <div>
                    <span className="meta-label">Location:</span>
                    <span className="meta-val">{inc.stop_name || 'Arena Perimeter'}</span>
                  </div>
                  <div>
                    <span className="meta-label">Vehicle / Driver:</span>
                    <span className="meta-val">
                      {inc.bus_number || 'N/A'} {inc.driver_name ? `(${inc.driver_name})` : ''}
                    </span>
                  </div>
                  <div>
                    <span className="meta-label">Reported Source:</span>
                    <span className="meta-val">{inc.source} • {inc.source_provenance_label}</span>
                  </div>
                  <div>
                    <span className="meta-label">Assigned Responder:</span>
                    <span className="meta-val">{inc.assigned_responder || 'Depot Dispatch Desk'}</span>
                  </div>
                </div>

                {/* Action History Audit */}
                {inc.action_history && inc.action_history.length > 0 && (
                  <div className="ff-inc-history">
                    <span className="history-label">ACTION AUDIT LOG:</span>
                    <ul>
                      {inc.action_history.map((act, i) => (
                        <li key={i}>
                          <span className="act-time">{act.time?.slice(11, 19)}</span>
                          <span className="act-actor">[{act.actor}]</span>
                          <span className="act-text">{act.action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="ff-inc-card-footer">
                <div className="ff-inc-actions">
                  {inc.status === 'NEW' && (
                    <button
                      type="button"
                      className="ff-btn ff-btn-outline sm"
                      onClick={() => handleUpdateStatus(inc.incident_id, 'ACKNOWLEDGED', 'Incident acknowledged by Depot Admin.')}
                      disabled={isBusy}
                    >
                      <CheckIcon size={14} />
                      <span>Acknowledge Alert</span>
                    </button>
                  )}

                  {inc.status !== 'RESOLVED' && (
                    <button
                      type="button"
                      className="ff-btn ff-btn-outline sm optimal"
                      onClick={() => handleUpdateStatus(inc.incident_id, 'RESOLVED', 'Situation resolved and passenger flow normalized.')}
                      disabled={isBusy}
                    >
                      <CheckCircleIcon size={14} />
                      <span>Resolve Incident</span>
                    </button>
                  )}

                  {inc.status !== 'RESOLVED' && inc.status !== 'ESCALATED' && onEscalateIncident && (
                    <button
                      type="button"
                      className="ff-btn ff-btn-outline sm warning"
                      onClick={() => onEscalateIncident(inc)}
                      disabled={isBusy}
                    >
                      <PhoneIcon size={14} />
                      <span>Escalate to Police</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {incidents.length === 0 && (
          <div className="ff-empty-card">
            <CheckCircleIcon size={36} className="ff-text-optimal" />
            <h3>No Incidents Matching Filter</h3>
            <p>All operational conditions and telematics rules are currently in healthy status.</p>
          </div>
        )}
      </div>

      {/* Manual Report Modal */}
      {showCreateModal && (
        <div className="ff-modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="ff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ff-modal-header">
              <div className="ff-modal-title-group">
                <ShieldAlertIcon size={20} />
                <h3>Report Operational Transit Incident</h3>
              </div>
              <button
                type="button"
                className="ff-modal-close"
                onClick={() => setShowCreateModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateIncident}>
              <div className="ff-form-row">
                <div className="ff-form-group">
                  <label>Incident Type:</label>
                  <select
                    className="ff-select"
                    value={newIncident.incident_type}
                    onChange={(e) => setNewIncident({ ...newIncident, incident_type: e.target.value })}
                  >
                    <option value="NIGHT_OVERCROWDING">Night Overcrowding Surge</option>
                    <option value="BREAKDOWN">Vehicle Mechanical Breakdown</option>
                    <option value="UNEXPECTED_STOP">Unexpected Off-Schedule Dwell Stop</option>
                    <option value="ROUTE_DEVIATION">Corridor Route Deviation</option>
                    <option value="DRIVER_ASSISTANCE">Driver Medical or Security Assistance</option>
                  </select>
                </div>

                <div className="ff-form-group">
                  <label>Severity Level:</label>
                  <select
                    className="ff-select"
                    value={newIncident.severity}
                    onChange={(e) => setNewIncident({ ...newIncident, severity: e.target.value })}
                  >
                    <option value="CRITICAL">Critical (Immediate Hazard)</option>
                    <option value="HIGH">High (Urgent Attention)</option>
                    <option value="MEDIUM">Medium (Operational Delay)</option>
                    <option value="LOW">Low (Informational)</option>
                  </select>
                </div>
              </div>

              <div className="ff-form-row">
                <div className="ff-form-group">
                  <label>Location / Stop:</label>
                  <select
                    className="ff-select"
                    value={newIncident.stop_id}
                    onChange={(e) => {
                      const names = {
                        'STOP_MAIN': 'Main Bus Stand (Festival Arena)',
                        'STOP_STH': 'South Commercial Terminal',
                        'STOP_TPN': 'Tech Hub North Stop'
                      };
                      setNewIncident({
                        ...newIncident,
                        stop_id: e.target.value,
                        stop_name: names[e.target.value] || e.target.value
                      });
                    }}
                  >
                    <option value="STOP_MAIN">Main Bus Stand (Festival Arena)</option>
                    <option value="STOP_STH">South Commercial Terminal</option>
                    <option value="STOP_TPN">Tech Hub North Stop</option>
                  </select>
                </div>

                <div className="ff-form-group">
                  <label>Vehicle / Bus Number:</label>
                  <input
                    type="text"
                    className="ff-input"
                    value={newIncident.bus_number}
                    onChange={(e) => setNewIncident({ ...newIncident, bus_number: e.target.value })}
                    placeholder="e.g. BUS-101"
                  />
                </div>
              </div>

              <div className="ff-form-group">
                <label>Incident Description:</label>
                <textarea
                  className="ff-textarea"
                  rows={3}
                  value={newIncident.description}
                  onChange={(e) => setNewIncident({ ...newIncident, description: e.target.value })}
                  placeholder="Detail the operational anomaly, crowd count, or vehicle condition..."
                  required
                />
              </div>

              <div className="ff-form-group">
                <label>Supporting Evidence (Telematics / CCTV / Driver Report):</label>
                <textarea
                  className="ff-textarea"
                  rows={2}
                  value={newIncident.supporting_evidence}
                  onChange={(e) => setNewIncident({ ...newIncident, supporting_evidence: e.target.value })}
                  placeholder="e.g. Dwell time 14 mins logged by GPS; visual crowd density confirmation..."
                />
              </div>

              <div className="ff-modal-actions">
                <button
                  type="button"
                  className="ff-btn ff-btn-outline"
                  onClick={() => setShowCreateModal(false)}
                  disabled={creating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="ff-btn ff-btn-primary"
                  disabled={creating}
                >
                  {creating ? 'Submitting Report...' : 'File Safety Incident'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

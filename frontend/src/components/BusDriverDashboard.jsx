import React, { useState, useEffect } from 'react';
import {
  BusIcon,
  CheckCircleIcon,
  CheckIcon,
  PlayIcon,
  RefreshCwIcon,
  AlertTriangleIcon,
  LogOutIcon,
  SunIcon,
  MoonIcon,
  ShieldCheckIcon,
  ClockIcon,
  MapPinIcon,
  InfoIcon,
  XIcon
} from './Icons';

/**
 * BusDriverDashboard - Mobile-Friendly Driver Operational Console.
 * 
 * Strict compliance with requirements:
 * - Simple, mobile-friendly interface for authorized bus runs.
 * - Clear Accept, Depart (En Route), Arrived, Boarding, Completed trip actions.
 * - Route information, destination terminal, and scheduled departure.
 * - Incident reporting modal.
 * - No admin-only controls; object-level driver authorization.
 * - Clean SVG icons, no emojis.
 */
function BusDriverDashboard({
  user,
  token,
  onLogout,
  theme,
  toggleTheme,
  apiBase,
  showToast
}) {
  const [schedules, setSchedules] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingReports, setLoadingReports] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState(null);

  // Incident report modal
  const [showReportModal, setShowReportModal] = useState(false);
  const [submittingReport, setSubmittingReport] = useState(false);
  const [reportForm, setReportForm] = useState({
    report_type: 'Delay',
    severity: 'medium',
    title: '',
    description: '',
    stop_id: 'STOP_MAIN',
    bus_id: ''
  });

  useEffect(() => {
    loadDriverSchedules();
    loadDriverNotifications();
    loadDriverReports();
    const interval = setInterval(() => {
      loadDriverNotifications();
      loadDriverReports();
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  const loadDriverReports = async () => {
    try {
      setLoadingReports(true);
      const res = await fetch(`${apiBase}/api/driver/my-reports`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setReports(data);
      }
    } catch (err) {
      console.error('Error fetching driver reports:', err);
    } finally {
      setLoadingReports(false);
    }
  };

  const handleOpenReportModal = (busNum = '', stopName = '') => {
    setReportForm({
      report_type: 'Delay',
      severity: 'medium',
      title: '',
      description: '',
      stop_id: stopName || 'STOP_MAIN',
      bus_id: busNum || (schedules.length > 0 ? schedules[0].bus_number : 'BUS-203')
    });
    setShowReportModal(true);
  };

  const handleSubmitReport = async (e) => {
    e.preventDefault();
    if (!reportForm.title.trim()) {
      showToast('Please provide a report title.', 'error');
      return;
    }
    setSubmittingReport(true);
    try {
      const payload = {
        bus_number: reportForm.bus_id || (schedules.length > 0 ? schedules[0].bus_number : 'BUS-203'),
        report_type: (reportForm.report_type === 'Other' ? 'SAFETY_CONCERN' : reportForm.report_type.replace(' ', '_')).toUpperCase(),
        severity: (reportForm.severity === 'urgent' ? 'CRITICAL' : reportForm.severity).toUpperCase(),
        stop_name: reportForm.stop_id || 'Main Bus Stand',
        description: reportForm.title ? `${reportForm.title}: ${reportForm.description || 'Reported from driver console.'}` : (reportForm.description || 'Driver operational incident report.')
      };

      const res = await fetch(`${apiBase}/api/driver/reports`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to submit report');
      }
      showToast('Incident report logged. Depot Admin notified.', 'success');
      setShowReportModal(false);
      loadDriverReports();
    } catch (err) {
      showToast(err.message || 'Error submitting report', 'error');
    } finally {
      setSubmittingReport(false);
    }
  };

  const loadDriverSchedules = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/api/driver/my-schedules`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) {
        if (res.status === 401) {
          onLogout();
          return;
        }
        throw new Error(`HTTP ${res.status}: Failed to fetch assigned schedules`);
      }
      const data = await res.json();
      setSchedules(data);
    } catch (err) {
      console.error('Error fetching driver schedules:', err);
      setError(err.message || 'Cannot load schedules.');
    } finally {
      setLoading(false);
    }
  };

  const loadDriverNotifications = async () => {
    try {
      const res = await fetch(`${apiBase}/api/driver/my-notifications`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data);
      }
    } catch (err) {
      console.error('Error fetching driver notifications:', err);
    }
  };

  const handleAcknowledgeNotification = async (notifId) => {
    try {
      const res = await fetch(`${apiBase}/api/driver/notifications/${notifId}/read`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!res.ok) {
        throw new Error('Failed to acknowledge notification.');
      }

      if (schedules.length > 0) {
        await handleUpdateStatus(schedules[0].id, 'Ready');
      }

      showToast('Urgent dispatch acknowledged. Marked Ready for operation.', 'success');
      loadDriverNotifications();
      loadDriverSchedules();
    } catch (err) {
      showToast(err.message || 'Failed to acknowledge alert.', 'error');
    }
  };

  const handleUpdateStatus = async (scheduleId, newStatus) => {
    setUpdatingId(scheduleId);
    try {
      const res = await fetch(`${apiBase}/api/driver/schedules/${scheduleId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ status: newStatus })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Failed to update status to ${newStatus}`);
      }

      showToast(`Status updated to "${newStatus}"`, 'success');
      setSchedules((prev) =>
        prev.map((s) => (s.id === scheduleId ? { ...s, status: newStatus } : s))
      );
    } catch (err) {
      console.error('Driver status update error:', err);
      showToast(err.message || 'Could not update status.', 'error');
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="ff-driver-viewport">
      {/* Driver Top Header */}
      <header className="ff-driver-header">
        <div className="driver-header-left">
          <div className="ff-brand-logo-mark small">
            <span>FF</span>
          </div>
          <div>
            <h1 className="driver-app-title">FestivalFlow AI</h1>
            <span className="driver-app-sub">Bus Driver Field Console</span>
          </div>
        </div>

        <div className="driver-header-right">
          <span className="driver-depot-tag">{user.depot_name || 'Central Transit Depot'}</span>
          <button
            type="button"
            className="ff-driver-icon-btn"
            onClick={toggleTheme}
            title="Toggle theme"
          >
            {theme === 'dark' ? <SunIcon size={16} /> : <MoonIcon size={16} />}
          </button>
          <button
            type="button"
            className="ff-driver-logout-btn"
            onClick={onLogout}
            title="Sign Out"
          >
            <LogOutIcon size={15} />
            <span>Sign Out</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="ff-driver-content">
        {/* Welcome Banner */}
        <div className="ff-driver-profile-banner">
          <div className="profile-text-group">
            <h2 className="welcome-name">Driver {user.full_name || user.username}</h2>
            <p className="depot-note">
              Depot: <strong>{user.depot_name || 'Central Transit Depot'}</strong> • Verified Active Shift
            </p>
          </div>
          <div className="profile-actions-group">
            <button
              type="button"
              className="ff-btn ff-btn-rose ff-btn-sm"
              onClick={() => handleOpenReportModal()}
            >
              <AlertTriangleIcon size={14} />
              <span>Report Incident</span>
            </button>
            <button
              type="button"
              className="ff-btn ff-btn-secondary ff-btn-sm"
              onClick={loadDriverSchedules}
              disabled={loading}
            >
              <RefreshCwIcon size={14} className={loading ? 'ff-spin' : ''} />
              <span>Refresh Run</span>
            </button>
          </div>
        </div>

        {error && (
          <div className="ff-callout-banner rose mb-4">
            <div className="banner-icon-col">
              <AlertTriangleIcon size={18} />
            </div>
            <div className="banner-content-col">
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Urgent Dispatch Alerts from Depot */}
        {notifications.filter((n) => !n.is_read).map((notif) => (
          <div key={notif.id} className="ff-callout-banner rose mb-4">
            <div className="banner-icon-col">
              <AlertTriangleIcon size={20} />
            </div>
            <div className="banner-content-col">
              <h4>URGENT DISPATCH ADVISORY</h4>
              <p>{notif.message}</p>
              <div className="mt-2 text-xs font-mono">
                Vehicle: <strong>{notif.bus_id}</strong> • Destination: <strong>{notif.target_stop}</strong>
              </div>
            </div>
            <div className="banner-action-col">
              <button
                type="button"
                className="ff-btn ff-btn-emerald ff-btn-sm"
                onClick={() => handleAcknowledgeNotification(notif.id)}
              >
                <CheckIcon size={14} />
                <span>Acknowledge & Mark Ready</span>
              </button>
            </div>
          </div>
        ))}

        {/* Assigned Schedules */}
        {loading && schedules.length === 0 ? (
          <div className="ff-card-body text-center py-12 text-muted">
            <RefreshCwIcon size={24} className="ff-spin mx-auto mb-3" />
            <p>Loading assigned vehicle run...</p>
          </div>
        ) : schedules.length === 0 ? (
          <div className="ff-empty-card">
            <ClockIcon size={32} className="text-muted mx-auto mb-3" />
            <h3>No Active Bus Run Assigned</h3>
            <p>
              You do not have an active bus run assigned for this shift. Your Depot Admin at{' '}
              <strong>{user.depot_name || 'Central Depot'}</strong> will dispatch assignments as crowd egress demands.
            </p>
            <button
              type="button"
              className="ff-btn ff-btn-primary mt-4"
              onClick={loadDriverSchedules}
              disabled={loading}
            >
              Check for New Assignments
            </button>
          </div>
        ) : (
          <div className="ff-driver-runs-list">
            <div className="ff-section-header-row mb-4">
              <h3>Assigned Operational Run</h3>
              <span className="ff-tag-future">{schedules.length} Run Scheduled</span>
            </div>

            {schedules.map((sched) => {
              const isUpdating = updatingId === sched.id;
              const status = sched.status || 'Scheduled';

              return (
                <div key={sched.id} className="ff-driver-run-card">
                  {/* Card Header */}
                  <div className="run-card-top">
                    <div className="vehicle-info">
                      <span className="ff-bus-tag large">{sched.bus_number}</span>
                      {sched.bus_registration_no && (
                        <span className="reg-tag">{sched.bus_registration_no}</span>
                      )}
                    </div>
                    <span className={`ff-status-pill ${status.toLowerCase().replace(' ', '-')}`}>
                      {status}
                    </span>
                  </div>

                  {/* Route & Corridor Grid */}
                  <div className="run-details-grid">
                    <div className="detail-box">
                      <span className="d-label">Festival Event:</span>
                      <span className="d-val font-semibold">{sched.event_name}</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Crowd Exit Window:</span>
                      <span className="d-val font-mono">{sched.expected_crowd_departure.replace('T', ' ')}</span>
                    </div>

                    <div className="detail-box full-col">
                      <span className="d-label">Transit Corridor:</span>
                      <span className="d-val font-semibold text-navy">{sched.route_details}</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Origin / Staging Stop:</span>
                      <span className="d-val">{sched.source_stop}</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Destination Hub:</span>
                      <span className="d-val text-emerald font-semibold">{sched.destination_stop}</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Scheduled Departure:</span>
                      <span className="d-val font-mono">{sched.departure_time.replace('T', ' ')}</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Target Hub Arrival:</span>
                      <span className="d-val font-mono">{sched.arrival_time ? sched.arrival_time.replace('T', ' ') : 'Before 22:00'}</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Vehicle Capacity:</span>
                      <span className="d-val">{sched.bus_capacity} Passengers</span>
                    </div>

                    <div className="detail-box">
                      <span className="d-label">Operating Depot:</span>
                      <span className="d-val">{sched.depot_name}</span>
                    </div>
                  </div>

                  {sched.notes && (
                    <div className="run-notes-box">
                      <InfoIcon size={14} />
                      <span>{sched.notes}</span>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="run-actions-bar">
                    <span className="actions-title">Update Operational Status:</span>
                    <div className="driver-action-buttons-grid">
                      <button
                        type="button"
                        className={`ff-btn ff-btn-sm ${status === 'Accepted' ? 'ff-btn-primary' : 'ff-btn-secondary'}`}
                        onClick={() => handleUpdateStatus(sched.id, 'Accepted')}
                        disabled={isUpdating || status === 'Accepted'}
                      >
                        Accept Run
                      </button>

                      <button
                        type="button"
                        className={`ff-btn ff-btn-sm ${status === 'En Route' ? 'ff-btn-emerald' : 'ff-btn-secondary'}`}
                        onClick={() => handleUpdateStatus(sched.id, 'En Route')}
                        disabled={isUpdating || status === 'En Route'}
                      >
                        <PlayIcon size={12} />
                        <span>En Route</span>
                      </button>

                      <button
                        type="button"
                        className={`ff-btn ff-btn-sm ${status === 'Arrived' ? 'ff-btn-primary' : 'ff-btn-secondary'}`}
                        onClick={() => handleUpdateStatus(sched.id, 'Arrived')}
                        disabled={isUpdating || status === 'Arrived'}
                      >
                        Arrived
                      </button>

                      <button
                        type="button"
                        className={`ff-btn ff-btn-sm ${status === 'Boarding' ? 'ff-btn-primary' : 'ff-btn-secondary'}`}
                        onClick={() => handleUpdateStatus(sched.id, 'Boarding')}
                        disabled={isUpdating || status === 'Boarding'}
                      >
                        Boarding
                      </button>

                      <button
                        type="button"
                        className={`ff-btn ff-btn-sm ${status === 'Completed' ? 'ff-btn-emerald' : 'ff-btn-secondary'}`}
                        onClick={() => handleUpdateStatus(sched.id, 'Completed')}
                        disabled={isUpdating || status === 'Completed'}
                      >
                        <CheckIcon size={12} />
                        <span>Completed</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Driver Incident Reports History */}
        <div className="ff-table-card mt-6">
          <div className="ff-table-header-bar">
            <div>
              <h3>Logged Incident & Delay Reports</h3>
              <p className="meta-text">Real-time driver reports sent directly to Depot Command</p>
            </div>
            <button
              type="button"
              className="ff-btn ff-btn-secondary ff-btn-sm"
              onClick={() => handleOpenReportModal()}
            >
              + Log New Report
            </button>
          </div>

          <div className="ff-table-container">
            <table className="ff-data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Severity</th>
                  <th>Incident Details</th>
                  <th>Vehicle</th>
                  <th>Status</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {reports.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="text-center py-6 text-muted">
                      No incident reports filed. Operations running smoothly.
                    </td>
                  </tr>
                ) : (
                  reports.map((rep) => (
                    <tr key={rep.id}>
                      <td><span className="ff-id-tag">#{rep.id}</span></td>
                      <td className="font-medium">{rep.report_type}</td>
                      <td>
                        <span className={`ff-status-pill ${rep.severity === 'CRITICAL' ? 'high' : 'normal'}`}>
                          {rep.severity}
                        </span>
                      </td>
                      <td>
                        <strong>{rep.title}</strong>
                        {rep.description && <p className="text-muted text-xs mt-1">{rep.description}</p>}
                      </td>
                      <td><span className="ff-bus-tag">{rep.bus_id || 'N/A'}</span></td>
                      <td>
                        <span className={`ff-status-pill ${rep.status?.toLowerCase() || 'submitted'}`}>
                          {rep.status}
                        </span>
                      </td>
                      <td className="font-mono text-muted text-sm">
                        {new Date(rep.created_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Incident Report Modal */}
      {showReportModal && (
        <div className="ff-modal-backdrop" onClick={() => setShowReportModal(false)}>
          <div className="ff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ff-modal-header">
              <h3 className="ff-modal-title">Report Operational Incident / Delay</h3>
              <button
                type="button"
                className="ff-modal-close"
                onClick={() => setShowReportModal(false)}
                disabled={submittingReport}
              >
                <XIcon size={18} />
              </button>
            </div>
            <form onSubmit={handleSubmitReport} className="ff-modal-body">
              <div className="ff-form-grid">
                <div className="ff-form-group">
                  <label htmlFor="repType">Incident Type:</label>
                  <select
                    id="repType"
                    value={reportForm.report_type}
                    onChange={(e) => setReportForm({ ...reportForm, report_type: e.target.value })}
                    className="ff-select"
                  >
                    <option value="Delay">Route Delay</option>
                    <option value="Breakdown">Vehicle Breakdown / Mechanical</option>
                    <option value="Overcrowding">Platform Overcrowding</option>
                    <option value="Safety Concern">Night Safety Concern</option>
                    <option value="Other">Other Incident</option>
                  </select>
                </div>

                <div className="ff-form-group">
                  <label htmlFor="repSeverity">Severity:</label>
                  <select
                    id="repSeverity"
                    value={reportForm.severity}
                    onChange={(e) => setReportForm({ ...reportForm, severity: e.target.value })}
                    className="ff-select"
                  >
                    <option value="low">Low (Advisory)</option>
                    <option value="medium">Medium (Requires Tracking)</option>
                    <option value="high">High (Action Required)</option>
                    <option value="urgent">Urgent (Immediate Response)</option>
                  </select>
                </div>

                <div className="ff-form-group">
                  <label htmlFor="repBus">Vehicle ID:</label>
                  <input
                    id="repBus"
                    type="text"
                    value={reportForm.bus_id}
                    onChange={(e) => setReportForm({ ...reportForm, bus_id: e.target.value })}
                    placeholder="e.g. BUS-203"
                    className="ff-input"
                  />
                </div>

                <div className="ff-form-group">
                  <label htmlFor="repStop">Location / Stop:</label>
                  <input
                    id="repStop"
                    type="text"
                    value={reportForm.stop_id}
                    onChange={(e) => setReportForm({ ...reportForm, stop_id: e.target.value })}
                    placeholder="e.g. Main Bus Stand"
                    className="ff-input"
                  />
                </div>
              </div>

              <div className="ff-form-group mt-3">
                <label htmlFor="repTitle">Incident Summary: *</label>
                <input
                  id="repTitle"
                  type="text"
                  required
                  value={reportForm.title}
                  onChange={(e) => setReportForm({ ...reportForm, title: e.target.value })}
                  placeholder="e.g. Heavy traffic congestion; +15m platform arrival delay"
                  className="ff-input"
                />
              </div>

              <div className="ff-form-group mt-3">
                <label htmlFor="repDesc">Operational Notes:</label>
                <textarea
                  id="repDesc"
                  rows="3"
                  value={reportForm.description}
                  onChange={(e) => setReportForm({ ...reportForm, description: e.target.value })}
                  placeholder="Additional field context or passenger assistance needed..."
                  className="ff-textarea"
                />
              </div>

              <div className="ff-modal-footer mt-4">
                <button
                  type="button"
                  className="ff-btn ff-btn-secondary"
                  onClick={() => setShowReportModal(false)}
                  disabled={submittingReport}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="ff-btn ff-btn-rose"
                  disabled={submittingReport}
                >
                  {submittingReport ? 'Submitting...' : 'Submit Report to Depot'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default BusDriverDashboard;

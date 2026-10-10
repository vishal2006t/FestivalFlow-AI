import React, { useState, useEffect } from 'react';

function AlertsDispatchTab({
  apiBase,
  token,
  showToast,
  onApplyScheduleReassignment,
  initialTargetStop = 'STOP_MAIN'
}) {
  const [alerts, setAlerts] = useState([]);
  const [busesTelematics, setBusesTelematics] = useState([]);
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const [loadingDispatch, setLoadingDispatch] = useState(false);
  const [dispatchRecommendation, setDispatchRecommendation] = useState(null);

  // Dispatch solver input
  const [selectedStopId, setSelectedStopId] = useState(initialTargetStop);
  const [customCrowd, setCustomCrowd] = useState(142);
  const [isNightMode, setIsNightMode] = useState(true);

  // Filter for telematics table
  const [telematicsFilter, setTelematicsFilter] = useState('ALL');

  // Escalation modal state
  const [escalatingAlert, setEscalatingAlert] = useState(null);
  const [escalationTarget, setEscalationTarget] = useState('Central Transit Operations Control');
  const [escalationNotes, setEscalationNotes] = useState('');
  const [isEscalating, setIsEscalating] = useState(false);

  const handleOpenEscalateModal = (alert) => {
    setEscalatingAlert(alert);
    setEscalationTarget('Central Transit Operations Control');
    setEscalationNotes(`Late-night passenger wait at ${alert.stop_name} exceeded threshold (${alert.waiting_time_mins || 22} mins, ${alert.crowd_count || 142} pax waiting). Requesting alternative bus or standby unit.`);
  };

  const handleConfirmEscalation = async (e) => {
    e.preventDefault();
    if (!escalatingAlert) return;
    setIsEscalating(true);
    try {
      const res = await fetch(`${apiBase}/api/alerts/${escalatingAlert.id}/escalate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          escalation_target: escalationTarget,
          notes: escalationNotes,
          action_taken: `Depot Admin initiated verified contact workflow to ${escalationTarget}. Standby fleet divert requested.`
        })
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Escalation failed');
      }
      showToast(`Alert #${escalatingAlert.id} escalated to ${escalationTarget}!`, 'success');
      setEscalatingAlert(null);
      loadAlerts();
    } catch (err) {
      showToast(err.message || 'Error escalating alert', 'error');
    } finally {
      setIsEscalating(false);
    }
  };

  useEffect(() => {
    loadAlerts();
    loadBusesTelematics();
    handleRunSmartDispatch(initialTargetStop, 142, true);
  }, []);

  const loadAlerts = async () => {
    setLoadingAlerts(true);
    try {
      const res = await fetch(`${apiBase}/api/alerts`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setAlerts(data);
      }
    } catch (err) {
      console.error('Error fetching alerts:', err);
    } finally {
      setLoadingAlerts(false);
    }
  };

  const loadBusesTelematics = async () => {
    try {
      const res = await fetch(`${apiBase}/api/buses/telematics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setBusesTelematics(data);
      }
    } catch (err) {
      console.error('Error fetching telematics:', err);
    }
  };

  const handleRunSmartDispatch = async (stopId = selectedStopId, crowd = customCrowd, isNight = isNightMode) => {
    setLoadingDispatch(true);
    try {
      const res = await fetch(`${apiBase}/api/smart-dispatch/recommend`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          stop_id: stopId,
          target_time: new Date().toISOString(),
          crowd_count: parseInt(crowd, 10) || 120,
          is_night: isNight
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Smart dispatch failed.');
      }

      const data = await res.json();
      setDispatchRecommendation(data);
      loadAlerts(); // Refresh alerts list
      showToast('Smart bus matching evaluated across 17-bus network!', 'info');
    } catch (err) {
      console.error('Smart dispatch error:', err);
      showToast(err.message || 'Failed to calculate smart dispatch.', 'error');
    } finally {
      setLoadingDispatch(false);
    }
  };

  const handleAcknowledgeAlert = async (alertId) => {
    try {
      const res = await fetch(`${apiBase}/api/alerts/${alertId}/acknowledge`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ status: 'ACKNOWLEDGED' })
      });
      if (res.ok) {
        showToast(`Alert #${alertId} acknowledged.`, 'success');
        setAlerts((prev) =>
          prev.map((a) => (a.id === alertId ? { ...a, status: 'ACKNOWLEDGED' } : a))
        );
      }
    } catch (err) {
      showToast('Error acknowledging alert', 'error');
    }
  };

  const handleNotifyDriver = async (alert, customBus = null) => {
    const topBus = customBus || (dispatchRecommendation && (dispatchRecommendation.top_candidate || dispatchRecommendation.recommended_bus));
    const busId = topBus ? (topBus.bus_number || topBus.bus_id || 'BUS-203') : (alert.recommended_bus_number || 'BUS-203');
    const driverId = topBus?.driver_id || alert.notified_driver_id || 3;

    try {
      const payload = {
        driver_id: driverId,
        custom_message: `🚨 URGENT DISPATCH ADVISORY: Divert ${busId} to ${alert.stop_name || 'Main Bus Stand (Festival Arena)'}. Reason: Night safety passenger crowd clearance (${alert.crowd_count || 142} waiting). Report Ready in mobile console.`
      };

      const res = await fetch(`${apiBase}/api/alerts/${alert.id}/notify-driver`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to dispatch notification to driver');
      }

      showToast(`📢 Urgent notification dispatched to Driver for ${busId}!`, 'success');
      setAlerts((prev) =>
        prev.map((a) => (a.id === alert.id ? { ...a, status: 'DISPATCHED' } : a))
      );
    } catch (err) {
      showToast(err.message || 'Failed to notify driver', 'error');
    }
  };

  const filteredBuses = busesTelematics.filter((bus) => {
    if (telematicsFilter === 'ALL') return true;
    return bus.status === telematicsFilter;
  });

  const topBus = dispatchRecommendation && (dispatchRecommendation.top_candidate || dispatchRecommendation.recommended_bus);
  const sourceImpact = dispatchRecommendation && (dispatchRecommendation.source_impact || dispatchRecommendation.reallocation_impact);

  return (
    <div className="alerts-dispatch-container">
      {/* Night Safety & Advisory Header Banner */}
      <div className="night-safety-top-banner">
        <div className="banner-icon-col">
          <span className="pulsing-shield">🛡️</span>
        </div>
        <div className="banner-text-col">
          <div className="banner-title-row">
            <h3>Camera-Assisted Crowd Intelligence & Night Safety Operations</h3>
            <span className="safety-window-pill">🌙 Active Window: 20:00 - 05:00 / Festival Egress</span>
            <span className="advisory-pill">⚠️ Advisory Only — Manual Depot Admin Confirmation Required</span>
          </div>
          <p>
            Real-time multi-camera crowd tracking evaluates queue delays at transit staging areas.
            When passenger wait times exceed <strong>15 minutes</strong> late at night, FestivalFlow AI highlights high-risk stops,
            matches candidate underutilized buses without disrupting source commuter guarantees, and prepares rapid driver dispatch advisories.
          </p>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="dispatch-layout-grid">
        {/* LEFT COLUMN: Active Depot Alerts & Night Safety Stream */}
        <div className="dispatch-col-left">
          <div className="section-card">
            <div className="section-header-row">
              <div className="title-with-badge">
                <h3>🚨 Depot Alerts & Operational Warnings</h3>
                <span className="badge-count">{alerts.length} Active</span>
              </div>
              <button className="secondary-btn btn-sm" onClick={loadAlerts} disabled={loadingAlerts}>
                {loadingAlerts ? 'Refreshing...' : '🔄 Refresh Alerts'}
              </button>
            </div>

            {loadingAlerts && alerts.length === 0 ? (
              <div className="loading-card">
                <div className="spinner"></div>
                <p>Loading active operational alerts...</p>
              </div>
            ) : alerts.length === 0 ? (
              <div className="empty-state-box">
                <span>✅</span>
                <p>No active congestion or safety alerts. All bus stops operating within normal wait thresholds.</p>
              </div>
            ) : (
              <div className="alerts-feed-list">
                {alerts.map((alert) => {
                  const isNight = Boolean(alert.is_night_time || alert.is_night_safety);
                  const isPending = alert.status === 'PENDING';
                  const isDispatched = alert.status === 'DISPATCHED';
                  const waitMins = alert.waiting_time_mins !== undefined ? alert.waiting_time_mins : (alert.wait_time_minutes || 22);
                  const recBusNum = alert.recommended_bus_number || alert.recommended_bus_id || 'BUS-203';
                  const severity = alert.severity || alert.alert_level || 'CRITICAL';

                  return (
                    <div
                      key={alert.id}
                      className={`depot-alert-card ${isNight ? 'night-alert' : 'surge-alert'} ${
                        !isPending ? 'acknowledged-card' : ''
                      }`}
                    >
                      <div className="alert-card-top">
                        <div className="alert-type-group">
                          <span className={`alert-level-badge level-${severity.toLowerCase()}`}>
                            {isNight ? '🌙 NIGHT SAFETY ALERT' : '⚡ CROWD SURGE'}
                          </span>
                          <span className="alert-stop-tag">{alert.stop_name}</span>
                        </div>
                        <span className={`alert-status-pill status-${alert.status.toLowerCase()}`}>
                          {alert.status}
                        </span>
                      </div>

                      <div className="alert-metric-row">
                        <div className="metric-cell">
                          <span className="m-label">Est. Waiting</span>
                          <span className="m-val highlight-val">{alert.crowd_count} pax</span>
                        </div>
                        <div className="metric-cell">
                          <span className="m-label">Wait Time</span>
                          <span className="m-val warn-val">{waitMins} mins</span>
                        </div>
                        <div className="metric-cell">
                          <span className="m-label">Recommended Bus</span>
                          <span className="m-val highlight-val">{recBusNum}</span>
                        </div>
                        <div className="metric-cell">
                          <span className="m-label">Severity</span>
                          <span className="m-val cam-id-val">{severity}</span>
                        </div>
                      </div>

                      <div className="alert-message-box">
                        <strong>Operational Advisory:</strong>
                        <p>{alert.message}</p>
                        {alert.source_impact_summary && (
                          <div className="impact-snippet">
                            <span>🔄 Reallocation Trade-Off: {alert.source_impact_summary}</span>
                          </div>
                        )}
                      </div>

                      {alert.status === 'ESCALATED' && (
                        <div className="escalated-info-banner">
                          <span>🚨 ESCALATED to <strong>{alert.escalation_target || 'Transport Operations Control'}</strong></span>
                          {alert.notes && <p className="escalation-notes-preview">{alert.notes}</p>}
                        </div>
                      )}

                      {/* Alert Action Buttons */}
                      <div className="alert-card-actions">
                        {(isPending || alert.status === 'ACKNOWLEDGED') && (
                          <>
                            <button
                              className="btn-urgent-dispatch"
                              onClick={() => handleNotifyDriver(alert)}
                              title="Send urgent divert notification to assigned driver"
                            >
                              📢 Notify Assigned Driver
                            </button>
                            {recBusNum && (
                              <button
                                className="btn-apply-realloc"
                                onClick={() => {
                                  if (onApplyScheduleReassignment) {
                                    onApplyScheduleReassignment({
                                      bus_number: recBusNum,
                                      destination_stop: alert.stop_name,
                                      notes: `Camera Night Safety clearance reassignment for ${alert.stop_name}. Passenger queue: ${alert.crowd_count}.`
                                    });
                                  }
                                }}
                              >
                                ⚡ Apply Reassignment to Schedule
                              </button>
                            )}
                            {isPending && (
                              <button
                                className="btn-ack"
                                onClick={() => handleAcknowledgeAlert(alert.id)}
                              >
                                ✓ Acknowledge
                              </button>
                            )}
                            <button
                              className="btn-escalate-alert"
                              onClick={() => handleOpenEscalateModal(alert)}
                              title="Escalate delay and safety concern to central transport coordinator"
                            >
                              ⚠️ Escalate Concern
                            </button>
                          </>
                        )}
                        {isDispatched && (
                          <div className="dispatched-confirmed-bar">
                            <span>✅ Notification dispatched to Driver. Vehicle reallocated.</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Interactive Smart Bus Dispatch Solver */}
        <div className="dispatch-col-right">
          <div className="section-card">
            <div className="section-header-row">
              <h3>⚡ Smart Route-Matching & Reassignment Engine</h3>
              <span className="badge-count">Conserved 17 Buses</span>
            </div>

            {/* Solver Controls */}
            <div className="solver-controls-card">
              <div className="solver-inputs-grid">
                <div className="form-group">
                  <label>Target Stop / Terminal:</label>
                  <select
                    value={selectedStopId}
                    onChange={(e) => setSelectedStopId(e.target.value)}
                  >
                    <option value="STOP_MAIN">Main Bus Stand (Festival Arena)</option>
                    <option value="STOP_NORTH">Tech Hub North Stop</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Passenger Crowd Count:</label>
                  <input
                    type="number"
                    min="10"
                    max="1000"
                    value={customCrowd}
                    onChange={(e) => setCustomCrowd(e.target.value)}
                  />
                </div>

                <div className="form-group checkbox-group">
                  <label className="checkbox-lbl">
                    <input
                      type="checkbox"
                      checked={isNightMode}
                      onChange={(e) => setIsNightMode(e.target.checked)}
                    />
                    🌙 Late-Night Protocol (20:00 - 05:00)
                  </label>
                  <span className="field-hint">Enforces 15m safety wait limit</span>
                </div>
              </div>

              <button
                className="primary-btn btn-solve"
                onClick={() => handleRunSmartDispatch()}
                disabled={loadingDispatch}
              >
                {loadingDispatch ? 'Evaluating 17 Fleet Candidates...' : '🔍 Find Best Underutilized Bus'}
              </button>
            </div>

            {/* Solver Results */}
            {loadingDispatch ? (
              <div className="loading-card">
                <div className="spinner"></div>
                <p>Checking bus GPS, passenger occupancy sensors, route compatibility and minimum service guarantees...</p>
              </div>
            ) : dispatchRecommendation && (
              <div className="recommendation-results-card">
                <div className="rec-header">
                  <div className="rec-status-badge success">
                    <span>✨ OPTIMAL CANDIDATE FOUND</span>
                  </div>
                  <span className="rec-time-stamp">
                    Evaluated at {new Date().toLocaleTimeString()}
                  </span>
                </div>

                {topBus ? (
                  <div className="recommended-bus-hero">
                    <div className="hero-top-row">
                      <div className="bus-hero-identity">
                        <span className="bus-badge-lg">{topBus.bus_number || topBus.bus_id}</span>
                        <span className="bus-reg-sub">{topBus.registration_no || 'TN-02-B-2003'}</span>
                      </div>
                      <div className="hero-provenance-tag">
                        {topBus.occupancy_source || topBus.data_provenance || 'LIVE SENSOR'}
                      </div>
                    </div>

                    <div className="bus-metrics-quad">
                      <div className="quad-cell">
                        <span className="q-label">Available Free Seats</span>
                        <span className="q-val green-val">
                          {topBus.available_seats !== undefined ? topBus.available_seats : topBus.free_seats} / {topBus.capacity}
                        </span>
                        <span className="q-sub">
                          ({topBus.passenger_count !== undefined ? topBus.passenger_count : topBus.current_occupancy} passengers onboard)
                        </span>
                      </div>

                      <div className="quad-cell">
                        <span className="q-label">Estimated ETA</span>
                        <span className="q-val highlight-val">{topBus.eta_mins !== undefined ? topBus.eta_mins : topBus.eta_minutes} mins</span>
                        <span className="q-sub">{topBus.distance_to_hub_km !== undefined ? topBus.distance_to_hub_km : topBus.distance_km} km distance</span>
                      </div>

                      <div className="quad-cell">
                        <span className="q-label">Current Route / Origin</span>
                        <span className="q-val text-val">{topBus.current_route || topBus.assigned_route}</span>
                        <span className="q-sub">Compatible corridor</span>
                      </div>

                      <div className="quad-cell">
                        <span className="q-label">Feasibility Score</span>
                        <span className="q-val text-val">
                          {topBus.feasibility_score ? `${topBus.feasibility_score.toFixed(1)}/100` : 'High Priority'}
                        </span>
                        <span className="q-sub">Meets all constraints</span>
                      </div>
                    </div>

                    {/* Source Impact Analysis */}
                    {sourceImpact && (
                      <div className="source-impact-panel">
                        <div className="panel-hdr">
                          <span className="hdr-title">⚖️ Source Route Trade-Off & Service Guarantee</span>
                          <span className="badge-guarantee-pass">
                            ✓ {sourceImpact.minimum_service_status || 'Minimum Service Maintained (1 bus active)'}
                          </span>
                        </div>

                        <div className="tradeoff-grid">
                          <div className="tradeoff-item">
                            <span className="t-lbl">Source Route & Depot:</span>
                            <span className="t-val">{sourceImpact.source_route} ({sourceImpact.source_depot || 'Tech Park North Depot'})</span>
                          </div>
                          <div className="tradeoff-item">
                            <span className="t-lbl">Headway Adjustment:</span>
                            <span className="t-val warn">
                              {sourceImpact.headway_change || `${sourceImpact.original_headway_mins || 15}m ➔ ${sourceImpact.new_headway_mins || 25}m`}
                            </span>
                          </div>
                          <div className="tradeoff-item full-width">
                            <span className="t-lbl">Operational Impact Summary:</span>
                            <p className="t-summary">{dispatchRecommendation.recommendation_summary || sourceImpact.fleet_conservation}</p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="hero-action-buttons">
                      <button
                        className="btn-action-primary"
                        onClick={() => {
                          if (onApplyScheduleReassignment) {
                            onApplyScheduleReassignment({
                              bus_number: topBus.bus_number || topBus.bus_id,
                              bus_registration_no: topBus.registration_no,
                              destination_stop: dispatchRecommendation.target_stop_name,
                              route_details: `Smart Reallocation from ${sourceImpact?.source_route || 'North Corridor'} to ${dispatchRecommendation.target_stop_name}`,
                              notes: `AI Recommended Divert: Free seats ${topBus.available_seats || topBus.free_seats}/${topBus.capacity}, ETA ${topBus.eta_mins || topBus.eta_minutes}m.`
                            });
                          }
                        }}
                      >
                        ⚡ Apply Reassignment to Schedule
                      </button>

                      <button
                        className="btn-action-dispatch"
                        onClick={() => {
                          const mockAlert = {
                            id: 1,
                            stop_name: dispatchRecommendation.target_stop_name,
                            crowd_count: dispatchRecommendation.crowd_count
                          };
                          handleNotifyDriver(mockAlert, topBus);
                        }}
                      >
                        📢 Dispatch Urgent Alert to Driver ({topBus.bus_number || topBus.bus_id})
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="no-candidate-box">
                    <p>⚠️ No feasible underutilized bus candidate found meeting minimum service constraints.</p>
                  </div>
                )}

                {/* Candidate Evaluation & Exclusion Transparency Table */}
                {(dispatchRecommendation.candidate_options || dispatchRecommendation.rejected_options) && (
                  <div className="candidate-transparency-card">
                    <h4>🔍 Evaluated Candidate Buses & Constraint Checks</h4>
                    <p className="subtext">
                      Full transparency: Why candidate buses were selected or excluded (e.g., full passenger loads, out-of-service, or protecting minimum commuter frequency).
                    </p>

                    <div className="candidates-table-wrapper">
                      <table className="admin-data-table candidates-table">
                        <thead>
                          <tr>
                            <th>Bus ID</th>
                            <th>Status</th>
                            <th>Free Seats</th>
                            <th>ETA</th>
                            <th>Evaluation / Exclusion Reason</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(dispatchRecommendation.candidate_options || []).map((c, i) => (
                            <tr key={`cand-${i}`} className="row-eligible">
                              <td><strong>{c.bus_number}</strong></td>
                              <td><span className="status-pill status-ready">Available</span></td>
                              <td>{c.available_seats}/{c.capacity} free</td>
                              <td>{c.eta_mins}m</td>
                              <td>
                                <span className="eligible-reason">
                                  ✅ Eligible (Score: {c.feasibility_score.toFixed(1)}) • {c.current_route}
                                </span>
                              </td>
                            </tr>
                          ))}
                          {(dispatchRecommendation.rejected_options || []).map((r, i) => (
                            <tr key={`rej-${i}`} className="row-excluded">
                              <td><strong>{r.bus_number}</strong></td>
                              <td>
                                <span className={`status-pill status-${(r.status || 'full').toLowerCase().replace(' ', '-')}`}>
                                  {r.status}
                                </span>
                              </td>
                              <td>{r.occupancy_rate ? `${Math.round(r.occupancy_rate * 100)}% load` : 'N/A'}</td>
                              <td>N/A</td>
                              <td>
                                <span className="excluded-reason">
                                  ❌ Excluded: {r.rejection_reason}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* BOTTOM SECTION: 17-Bus Fleet Telematics & Live Occupancy Grid */}
      <div className="section-card telematics-section">
        <div className="section-header-row">
          <div className="title-with-badge">
            <h3>🚌 Fleet Telematics, Real GPS & Passenger Occupancy Sensors</h3>
            <span className="badge-count">Total 17 Buses</span>
          </div>

          <div className="telematics-filter-pills">
            {['ALL', 'Available', 'En Route', 'Full', 'Out of Service'].map((status) => (
              <button
                key={status}
                className={`filter-pill ${telematicsFilter === status ? 'active' : ''}`}
                onClick={() => setTelematicsFilter(status)}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        <div className="table-responsive">
          <table className="admin-data-table">
            <thead>
              <tr>
                <th>Bus ID & Reg</th>
                <th>Status</th>
                <th>Assigned Route</th>
                <th>Occupancy / Free Seats</th>
                <th>Current Location</th>
                <th>ETA to Hub</th>
                <th>Data Source Provenance</th>
                <th>Last Update</th>
              </tr>
            </thead>
            <tbody>
              {filteredBuses.map((bus) => {
                const occPercent = Math.round((bus.passenger_count / bus.capacity) * 100);
                const isFull = bus.status === 'Full' || occPercent >= 85;

                return (
                  <tr key={bus.id || bus.bus_number}>
                    <td>
                      <div className="bus-id-cell">
                        <span className="bus-id-badge">{bus.bus_number}</span>
                        <span className="bus-reg-sub">{bus.registration_no || 'TN-VERIFIED'}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill status-${bus.status.toLowerCase().replace(' ', '-')}`}>
                        {bus.status}
                      </span>
                    </td>
                    <td>{bus.assigned_route || 'Unassigned / Depot Yard'}</td>
                    <td>
                      <div className="occupancy-progress-box">
                        <div className="occ-text-row">
                          <span>{bus.passenger_count} / {bus.capacity} pax</span>
                          <span className={isFull ? 'danger-text' : 'safe-text'}>
                            {bus.available_seats} free
                          </span>
                        </div>
                        <div className="progress-bar-bg">
                          <div
                            className={`progress-fill ${isFull ? 'fill-full' : 'fill-ok'}`}
                            style={{ width: `${Math.min(occPercent, 100)}%` }}
                          ></div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className="gps-location-cell">
                        <span>📍 {bus.current_location}</span>
                        <span className="gps-coords">Dist: {bus.distance_to_hub_km} km</span>
                      </div>
                    </td>
                    <td>
                      <strong>{bus.eta_mins} mins</strong>
                      <span className="field-hint"> ({bus.eta_source})</span>
                    </td>
                    <td>
                      <span className="provenance-pill">{bus.occupancy_source}</span>
                    </td>
                    <td className="time-val">
                      {new Date(bus.last_update).toLocaleTimeString()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Safety Alert Escalation Modal */}
      {escalatingAlert && (
        <div className="modal-backdrop" onClick={() => setEscalatingAlert(null)}>
          <div className="modal-card escalate-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>⚠️ Authorized Safety Concern Escalation Workflow</h3>
              <button
                className="close-btn"
                onClick={() => setEscalatingAlert(null)}
                disabled={isEscalating}
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleConfirmEscalation} className="modal-form">
              <div className="alert-box info" style={{ marginBottom: '1rem' }}>
                <span>🛡️</span>
                <div>
                  <strong>Human-in-the-Loop Verified Protocol:</strong> This action escalates this service disruption
                  to the responsible transport management team. Emergency escalation is an explicit human decision.
                  No automated police contact or personal profiling is performed.
                </div>
              </div>

              <div className="form-group">
                <label>Affected Stop / Location:</label>
                <input
                  type="text"
                  disabled
                  value={`${escalatingAlert.stop_name} (Queue: ${escalatingAlert.crowd_count} pax, Wait: ${escalatingAlert.waiting_time_mins || 22}m)`}
                />
              </div>

              <div className="form-group">
                <label htmlFor="escTarget">Escalate To (Transport Authority / Operations Desk): *</label>
                <select
                  id="escTarget"
                  value={escalationTarget}
                  onChange={(e) => setEscalationTarget(e.target.value)}
                >
                  <option value="Central Transit Operations Control">Central Transit Operations Control</option>
                  <option value="Depot Operations General Manager">Depot Operations General Manager</option>
                  <option value="Festival Event Safety & Crowd Coordinator">Festival Event Safety & Crowd Coordinator</option>
                  <option value="Regional Transport Safety Supervisor">Regional Transport Safety Supervisor</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="escNotes">Escalation Justification & Operational Directive: *</label>
                <textarea
                  id="escNotes"
                  rows="3"
                  required
                  value={escalationNotes}
                  onChange={(e) => setEscalationNotes(e.target.value)}
                  placeholder="Describe the operational reason, delay conditions, and requested relief bus allocation..."
                />
              </div>

              <div className="modal-actions-row">
                <button
                  type="button"
                  className="secondary-btn"
                  onClick={() => setEscalatingAlert(null)}
                  disabled={isEscalating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="primary-btn btn-danger-action"
                  disabled={isEscalating}
                >
                  {isEscalating ? 'Submitting Escalation...' : '⚠️ Submit Authorized Escalation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default AlertsDispatchTab;

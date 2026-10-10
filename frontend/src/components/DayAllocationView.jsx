import React, { useState, useEffect } from 'react';
import {
  SunIcon,
  BusIcon,
  UsersIcon,
  RefreshCwIcon,
  CheckCircleIcon,
  InfoIcon,
  MapPinIcon
} from './Icons';

/**
 * DayAllocationView - Common / Daytime Operations & Bus Allocation Console.
 * 
 * Features:
 * - Daytime festival crowd arrivals & regular schedule operations (06:00 to 20:00).
 * - Daytime fleet capacity, route assignments, and weather impact.
 * - Independent filtering from night operations.
 */
export default function DayAllocationView({ apiBase, token, showToast }) {
  const [loading, setLoading] = useState(true);
  const [dayData, setDayData] = useState(null);
  const [selectedStopId, setSelectedStopId] = useState('STOP_MAIN');

  const loadDayOps = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/operations/day`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const json = await res.json();
        setDayData(json);
      } else {
        showToast('Failed to load day operations', 'error');
      }
    } catch (err) {
      console.error('Day ops fetch error:', err);
      showToast('Error connecting to day operations engine', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDayOps();
  }, [apiBase, token]);

  if (loading && !dayData) {
    return (
      <div className="ff-loading-state">
        <RefreshCwIcon size={28} className="ff-spinner" />
        <p>Loading daytime transit corridors and scheduled bus allocations...</p>
      </div>
    );
  }

  const weather = dayData?.weather || {};
  const stopAllocations = dayData?.stop_allocations || [];
  const currentStop = stopAllocations.find((s) => s.stop_id === selectedStopId) || stopAllocations[0];
  const summary = dayData?.summary_metrics || {};

  return (
    <div className="ff-tab-container">
      {/* Page Header */}
      <div className="ff-page-header">
        <div>
          <h2 className="ff-page-title">Common / Daytime Operations & Transit Allocation</h2>
          <p className="ff-page-subtitle">
            Regular scheduled transit services, daytime festival passenger flow, and corridor fleet management.
          </p>
        </div>
        <div className="ff-header-actions">
          <button
            type="button"
            className="ff-btn ff-btn-outline"
            onClick={loadDayOps}
            disabled={loading}
          >
            <RefreshCwIcon size={16} className={loading ? 'ff-spinner' : ''} />
            <span>Refresh Day Schedules</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="ff-metrics-grid ff-grid-4">
        <div className="ff-metric-card">
          <div className="ff-metric-header">
            <span className="ff-metric-label">OPERATING WINDOW</span>
            <SunIcon size={18} className="ff-text-amber" />
          </div>
          <div className="ff-metric-value">06:00 - 20:00</div>
          <p className="ff-metric-footer">Daytime Arrival & Commuter Services</p>
        </div>

        <div className="ff-metric-card">
          <div className="ff-metric-header">
            <span className="ff-metric-label">SCHEDULED CORRIDOR BUSES</span>
            <BusIcon size={18} />
          </div>
          <div className="ff-metric-value">12 Fixed Buses</div>
          <p className="ff-metric-footer">Central Depot Fleet (840 seats/wave)</p>
        </div>

        <div className="ff-metric-card">
          <div className="ff-metric-header">
            <span className="ff-metric-label">DAYTIME WEATHER FACTOR</span>
            <SunIcon size={18} />
          </div>
          <div className="ff-metric-value">
            {weather.condition || 'Mainly clear'} ({weather.temperature_celsius ? Math.round(weather.temperature_celsius) : 28}°C)
          </div>
          <p className="ff-metric-footer">Nominal Baseline Dispersion (+0%)</p>
        </div>

        <div className="ff-metric-card ff-border-optimal">
          <div className="ff-metric-header">
            <span className="ff-metric-label">DAYTIME DEMAND STATUS</span>
            <CheckCircleIcon size={18} className="ff-text-optimal" />
          </div>
          <div className="ff-metric-value">BALANCED</div>
          <p className="ff-metric-footer">Capacity Exceeds Daytime Inflow</p>
        </div>
      </div>

      {/* Stop Selector */}
      <div className="ff-toolbar">
        <div className="ff-toolbar-group">
          <span className="ff-toolbar-label">Select Corridor Hub:</span>
          <select
            className="ff-select"
            value={selectedStopId}
            onChange={(e) => setSelectedStopId(e.target.value)}
          >
            {stopAllocations.map((st) => (
              <option key={st.stop_id} value={st.stop_id}>
                {st.stop_name} {st.is_hub ? '(Main Arena)' : ''}
              </option>
            ))}
          </select>
        </div>
        <div className="ff-toolbar-group">
          <span className="ff-badge optimal">
            {currentStop?.zone || 'Central Corridor'}
          </span>
        </div>
      </div>

      {/* Daytime Interval Table */}
      <div className="ff-card">
        <div className="ff-card-header">
          <div>
            <h3 className="ff-card-title">
              {currentStop?.stop_name} — Daytime Interval Allocation
            </h3>
            <p className="ff-card-subtitle">
              Scheduled bus frequency, passenger arrival volume, and capacity adequacy.
            </p>
          </div>
        </div>

        <div className="ff-table-wrapper">
          <table className="ff-table">
            <thead>
              <tr>
                <th>Time Window</th>
                <th>Phase</th>
                <th>Estimated Inflow</th>
                <th>Scheduled Capacity</th>
                <th>Deficit</th>
                <th>Reallocated Buses</th>
                <th>Unmet Demand</th>
                <th>Operational Status</th>
              </tr>
            </thead>
            <tbody>
              {currentStop?.intervals?.map((intvl, idx) => (
                <tr key={idx}>
                  <td><strong>{intvl.time_slot}</strong></td>
                  <td>
                    <span className="ff-badge cyan">Day Regular</span>
                  </td>
                  <td>{intvl.estimated_demand} pax</td>
                  <td>{intvl.base_capacity} seats</td>
                  <td>
                    <span className="ff-text-optimal">Adequate</span>
                  </td>
                  <td>0 (Fixed schedules sufficient)</td>
                  <td>0 pax</td>
                  <td>
                    <span className="ff-badge optimal">NORMAL OPERATIONS</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Notice Card */}
      <div className="ff-provenance-box">
        <InfoIcon size={18} className="ff-icon-info" />
        <div>
          <h4>Day Operations Independence</h4>
          <p>
            Daytime transit schedules are governed by fixed timetables. Standby reserve buses from Tech Park North Depot are reserved during the day to ensure full availability for critical night egress surge windows.
          </p>
        </div>
      </div>
    </div>
  );
}

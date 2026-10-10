import React, { useState, useEffect } from 'react';
import {
  ClipboardListIcon,
  RefreshCwIcon,
  SearchIcon,
  CheckCircleIcon,
  CheckIcon,
  XIcon,
  PlayIcon,
  ZapIcon,
  AlertTriangleIcon
} from './Icons';

/**
 * DriverAssignmentsPage - Enterprise Driver Assignments Management.
 * 
 * Features:
 * - Clean, responsive data table with sorting and filtering.
 * - Assignment ID, corridor route, bus ID, assigned driver, depot, status, updated time.
 * - Clear action states with confirmation modal to prevent accidental clicks.
 * - Integration with backend PATCH /api/assignments/{id}/status.
 * - No emojis; professional enterprise SaaS design.
 */
function DriverAssignmentsPage({
  apiBase,
  token,
  showToast,
  isAllocationPending,
  onApproveAllocation
}) {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [updatingId, setUpdatingId] = useState(null);

  // Action confirmation state
  const [confirmModal, setConfirmModal] = useState({
    isOpen: false,
    assignmentId: null,
    targetStatus: null,
    actionLabel: ''
  });

  const loadAssignments = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${apiBase}/api/schedules`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const schedules = await res.json();
        const mapped = schedules.map((s) => ({
          id: s.id,
          bus_number: s.bus_number,
          driver_name: s.driver_name,
          depot_name: s.depot_name,
          route_display: s.route_details || `${s.source_stop} -> ${s.destination_stop}`,
          notes: s.notes || s.event_name,
          status: (s.status || 'Scheduled').toUpperCase(),
          status_label: s.status || 'Scheduled',
          updated_at: s.updated_at || s.created_at || new Date().toISOString()
        }));
        setAssignments(mapped);
      }
    } catch (err) {
      console.error('Error fetching assignments:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAssignments();
  }, [apiBase, token]);

  const promptStatusChange = (assignmentId, newStatus, actionLabel) => {
    setConfirmModal({
      isOpen: true,
      assignmentId,
      targetStatus: newStatus,
      actionLabel
    });
  };

  const executeStatusChange = async () => {
    const { assignmentId, targetStatus } = confirmModal;
    setConfirmModal({ isOpen: false, assignmentId: null, targetStatus: null, actionLabel: '' });

    if (!assignmentId || !targetStatus) return;

    setUpdatingId(assignmentId);
    try {
      const res = await fetch(`${apiBase}/api/schedules/${assignmentId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ status: targetStatus })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to update assignment status');
      }

      showToast(`Assignment #${assignmentId} status updated to ${targetStatus}`, 'success');
      loadAssignments();
    } catch (err) {
      showToast(err.message || 'Error updating assignment', 'error');
    } finally {
      setUpdatingId(null);
    }
  };

  const filteredAssignments = assignments.filter((a) => {
    const matchesStatus =
      statusFilter === 'ALL' ||
      a.status_label.toUpperCase() === statusFilter.toUpperCase() ||
      a.status.toUpperCase() === statusFilter.toUpperCase();

    const matchesSearch =
      !searchQuery ||
      a.bus_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (a.driver_name && a.driver_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      a.route_display.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesStatus && matchesSearch;
  });

  return (
    <div className="ff-page-container">
      {/* Pending Recommendation Banner */}
      {isAllocationPending && (
        <div className="ff-callout-banner amber">
          <div className="banner-icon-col">
            <ZapIcon size={20} />
          </div>
          <div className="banner-content-col">
            <h4>Proactive Reallocation Pending Admin Approval</h4>
            <p>
              AI analysis recommends dispatching <strong>4 standby buses</strong> from Tech Park North Depot to Main Bus Stand Bay 4 to absorb the 40,000 attendee surge.
            </p>
          </div>
          <div className="banner-action-col">
            <button
              type="button"
              onClick={onApproveAllocation}
              className="ff-btn ff-btn-emerald ff-btn-sm"
              id="btn-assignments-approve-allocation"
            >
              <CheckIcon size={14} />
              <span>Approve & Dispatch</span>
            </button>
          </div>
        </div>
      )}

      {/* Toolbar: Filters and Search */}
      <div className="ff-table-toolbar">
        <div className="ff-toolbar-left">
          <div className="ff-filter-tabs" role="tablist" aria-label="Assignment Status Filter">
            {['ALL', 'PENDING', 'ACCEPTED', 'IN PROGRESS', 'COMPLETED', 'REJECTED'].map((st) => (
              <button
                key={st}
                type="button"
                className={`ff-filter-tab ${statusFilter === st ? 'active' : ''}`}
                onClick={() => setStatusFilter(st)}
              >
                {st === 'ALL' ? 'All Assignments' : st.charAt(0) + st.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="ff-toolbar-right">
          <div className="ff-search-box">
            <SearchIcon size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search by Bus ID or Driver..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="ff-search-input"
              aria-label="Search assignments"
            />
          </div>

          <button
            type="button"
            onClick={loadAssignments}
            disabled={loading}
            className="ff-btn ff-btn-secondary"
            title="Refresh assignments from backend database"
          >
            <RefreshCwIcon size={15} className={loading ? 'ff-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Table Card */}
      <div className="ff-table-card">
        <div className="ff-table-container">
          <table className="ff-data-table">
            <thead>
              <tr>
                <th>Assignment ID</th>
                <th>Corridor Route</th>
                <th>Bus ID</th>
                <th>Assigned Driver</th>
                <th>Status</th>
                <th>Last Updated</th>
                <th>Operational Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading && assignments.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-muted">
                    Loading assignments from database...
                  </td>
                </tr>
              ) : filteredAssignments.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-8 text-muted">
                    No assignments found matching the current criteria.
                  </td>
                </tr>
              ) : (
                filteredAssignments.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <span className="ff-id-tag">ASG-{a.id}</span>
                    </td>
                    <td>
                      <div className="ff-route-cell">
                        <span className="route-main">{a.route_display}</span>
                        {a.notes && <span className="route-sub">{a.notes}</span>}
                      </div>
                    </td>
                    <td>
                      <span className="ff-bus-tag">{a.bus_number}</span>
                    </td>
                    <td>
                      <div className="ff-driver-cell">
                        <span className="driver-name">{a.driver_name || 'Unassigned'}</span>
                        <span className="driver-depot">{a.depot_name || 'Depot'}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`ff-status-pill ${a.status_class}`}>
                        {a.status_label}
                      </span>
                    </td>
                    <td className="text-muted font-mono text-sm">
                      {a.formatted_time}
                    </td>
                    <td>
                      <div className="ff-table-actions-group">
                        {a.status_label === 'Pending' && (
                          <>
                            <button
                              type="button"
                              onClick={() => promptStatusChange(a.id, 'Accepted', 'accept this dispatch order')}
                              disabled={updatingId === a.id}
                              className="ff-btn-action accept"
                              title="Accept dispatch order"
                            >
                              <CheckIcon size={13} />
                              <span>Accept</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => promptStatusChange(a.id, 'Rejected', 'reject this dispatch order')}
                              disabled={updatingId === a.id}
                              className="ff-btn-action reject"
                              title="Decline dispatch order"
                            >
                              <XIcon size={13} />
                              <span>Reject</span>
                            </button>
                          </>
                        )}

                        {a.status_label === 'Accepted' && (
                          <button
                            type="button"
                            onClick={() => promptStatusChange(a.id, 'In Progress', 'depart terminal en route')}
                            disabled={updatingId === a.id}
                            className="ff-btn-action depart"
                            title="Depart terminal en route"
                          >
                            <PlayIcon size={11} />
                            <span>Depart</span>
                          </button>
                        )}

                        {a.status_label === 'In Progress' && (
                          <button
                            type="button"
                            onClick={() => promptStatusChange(a.id, 'Completed', 'mark this trip as safely completed')}
                            disabled={updatingId === a.id}
                            className="ff-btn-action complete"
                            title="Complete trip"
                          >
                            <CheckIcon size={13} />
                            <span>Complete</span>
                          </button>
                        )}

                        {a.status_label === 'Completed' && (
                          <span className="text-muted text-xs font-medium">Trip Completed</span>
                        )}

                        {a.status_label === 'Rejected' && (
                          <span className="text-danger text-xs font-medium">Order Declined</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmModal.isOpen && (
        <div className="ff-modal-backdrop" onClick={() => setConfirmModal({ ...confirmModal, isOpen: false })}>
          <div className="ff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ff-modal-header">
              <h3 className="ff-modal-title">Confirm Action</h3>
              <button
                type="button"
                className="ff-modal-close"
                onClick={() => setConfirmModal({ ...confirmModal, isOpen: false })}
              >
                <XIcon size={18} />
              </button>
            </div>
            <div className="ff-modal-body">
              <p>
                Are you sure you want to <strong>{confirmModal.actionLabel}</strong> for Assignment #{confirmModal.assignmentId}?
              </p>
            </div>
            <div className="ff-modal-footer">
              <button
                type="button"
                className="ff-btn ff-btn-secondary"
                onClick={() => setConfirmModal({ ...confirmModal, isOpen: false })}
              >
                Cancel
              </button>
              <button
                type="button"
                className="ff-btn ff-btn-primary"
                onClick={executeStatusChange}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DriverAssignmentsPage;

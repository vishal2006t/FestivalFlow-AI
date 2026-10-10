import React, { useState, useEffect } from 'react';
import {
  PhoneIcon,
  ShieldAlertIcon,
  CheckCircleIcon,
  AlertTriangleIcon,
  ClockIcon,
  RefreshCwIcon,
  BuildingIcon,
  CheckIcon,
  InfoIcon,
  ClipboardListIcon
} from './Icons';

/**
 * PoliceEscalationView - Police / Emergency Notifications & Escalation Module.
 * 
 * Features:
 * - Authorized police & emergency agency directory.
 * - Structured incident review and explicit Send/Escalate confirmation modal.
 * - Honest delivery state tracking (Manual Phone Call Desk vs Automated SMS/Email Gateway).
 * - Copyable incident dispatch brief for emergency telephone communication.
 * - Police unit acknowledgement and response logger.
 */
export default function PoliceEscalationView({
  apiBase,
  token,
  showToast,
  user,
  initialIncidentToEscalate,
  onClearInitialIncident
}) {
  const [contacts, setContacts] = useState([]);
  const [escalations, setEscalations] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);

  // Escalation modal
  const [selectedIncident, setSelectedIncident] = useState(initialIncidentToEscalate || null);
  const [selectedContactId, setSelectedContactId] = useState('');
  const [escalationNotes, setEscalationNotes] = useState('');
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [escalating, setEscalating] = useState(false);

  // Police Ack Modal
  const [selectedEscalationForAck, setSelectedEscalationForAck] = useState(null);
  const [policeAckNotes, setPoliceAckNotes] = useState('PCR Unit arrived on site.');
  const [savingAck, setSavingAck] = useState(false);

  // Add Contact Modal
  const [showAddContactModal, setShowAddContactModal] = useState(false);
  const [newContact, setNewContact] = useState({
    agency_name: '',
    agency_type: 'POLICE',
    contact_person: '',
    phone: '',
    emergency_number: '112',
    email: '',
    jurisdiction: '',
    dispatch_instructions: ''
  });
  const [savingContact, setSavingContact] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [contactsRes, escalationsRes, incidentsRes] = await Promise.all([
        fetch(`${apiBase}/api/emergency/contacts`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${apiBase}/api/emergency/escalations`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${apiBase}/api/incidents`, { headers: { Authorization: `Bearer ${token}` } })
      ]);

      if (contactsRes.ok) {
        const cJson = await contactsRes.json();
        setContacts(cJson);
        if (cJson.length > 0 && !selectedContactId) {
          setSelectedContactId(cJson[0].id);
        }
      }
      if (escalationsRes.ok) {
        setEscalations(await escalationsRes.json());
      }
      if (incidentsRes.ok) {
        setIncidents(await incidentsRes.json());
      }
    } catch (err) {
      console.error('Error loading emergency data:', err);
      showToast('Error loading emergency services data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [apiBase, token]);

  useEffect(() => {
    if (initialIncidentToEscalate) {
      setSelectedIncident(initialIncidentToEscalate);
      setIsConfirmModalOpen(true);
      if (onClearInitialIncident) onClearInitialIncident();
    }
  }, [initialIncidentToEscalate]);

  const handleExecuteEscalation = async () => {
    if (!selectedIncident || !selectedContactId) {
      showToast('Please select both an incident and an emergency agency', 'error');
      return;
    }
    setEscalating(true);
    try {
      const res = await fetch(`${apiBase}/api/emergency/escalate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          incident_id: selectedIncident.incident_id,
          contact_id: parseInt(selectedContactId, 10),
          additional_notes: escalationNotes
        })
      });

      if (res.ok) {
        const json = await res.json();
        showToast(
          `Incident ${selectedIncident.incident_id} escalated to ${json.agency_name}. Delivery: ${json.delivery_status}`,
          'success'
        );
        setIsConfirmModalOpen(false);
        setSelectedIncident(null);
        setEscalationNotes('');
        loadData();
      } else {
        const errJson = await res.json().catch(() => ({}));
        showToast(errJson.detail || 'Escalation failed', 'error');
      }
    } catch (err) {
      console.error('Escalation error:', err);
      showToast('Error sending emergency escalation', 'error');
    } finally {
      setEscalating(false);
    }
  };

  const handleSavePoliceAck = async () => {
    if (!selectedEscalationForAck) return;
    setSavingAck(true);
    try {
      const res = await fetch(`${apiBase}/api/emergency/escalations/${selectedEscalationForAck.escalation_id}/status`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          police_ack_status: 'UNIT_DISPATCHED',
          police_response_notes: policeAckNotes
        })
      });
      if (res.ok) {
        showToast('Police response acknowledged in audit record.', 'success');
        setSelectedEscalationForAck(null);
        loadData();
      } else {
        showToast('Failed to record acknowledgement', 'error');
      }
    } catch (err) {
      console.error('Ack error:', err);
      showToast('Error saving response', 'error');
    } finally {
      setSavingAck(false);
    }
  };

  const handleCopyBrief = (esc) => {
    const payload = esc.dispatched_info || {};
    const text = (
      `🚨 EMERGENCY DISPATCH BRIEF - FESTIVALFLOW AI\n` +
      `Incident ID: ${esc.incident_id}\n` +
      `Severity: ${esc.severity}\n` +
      `Agency: ${esc.agency_name} (${esc.recipient_name})\n` +
      `Location: ${payload.stop_name || 'Main Bus Stand'}\n` +
      `Vehicle: ${payload.bus_number || 'N/A'}\n` +
      `Reported Time: ${esc.escalated_at}\n` +
      `Description: ${esc.incident_summary}\n` +
      `Evidence: ${payload.supporting_evidence || 'Direct verification'}\n` +
      `Operator Instructions: ${payload.additional_notes || 'Immediate staging and crowd control required.'}`
    );
    navigator.clipboard.writeText(text);
    showToast('Emergency incident brief copied to clipboard!', 'info');
  };

  if (loading && contacts.length === 0) {
    return (
      <div className="ff-loading-state">
        <RefreshCwIcon size={28} className="ff-spinner" />
        <p>Loading authorized emergency contacts and escalation logs...</p>
      </div>
    );
  }

  const unescalatedIncidents = incidents.filter(
    (i) => i.status !== 'RESOLVED' && i.status !== 'ESCALATED'
  );

  return (
    <div className="ff-tab-container">
      {/* Page Header */}
      <div className="ff-page-header">
        <div>
          <h2 className="ff-page-title">Police & Emergency Services Escalation</h2>
          <p className="ff-page-subtitle">
            Controlled escalation protocols connecting transit operations directly with local law enforcement, traffic division, and emergency medical desks.
          </p>
        </div>
        <div className="ff-header-actions">
          <button
            type="button"
            className="ff-btn ff-btn-primary"
            onClick={() => {
              if (unescalatedIncidents.length > 0) {
                setSelectedIncident(unescalatedIncidents[0]);
                setIsConfirmModalOpen(true);
              } else {
                showToast('No unescalated incidents currently open.', 'info');
              }
            }}
          >
            <PhoneIcon size={16} />
            <span>Escalate Open Incident</span>
          </button>
          <button
            type="button"
            className="ff-btn ff-btn-outline"
            onClick={loadData}
            disabled={loading}
          >
            <RefreshCwIcon size={16} className={loading ? 'ff-spinner' : ''} />
            <span>Refresh Emergency Logs</span>
          </button>
        </div>
      </div>

      {/* Authorized Emergency Agency Cards Grid */}
      <div className="ff-card">
        <div className="ff-card-header">
          <div>
            <h3 className="ff-card-title">Authorized Emergency Services Directory</h3>
            <p className="ff-card-subtitle">
              Pre-configured law enforcement, traffic command, and EMS desks with direct dispatch jurisdictions.
            </p>
          </div>
        </div>

        <div className="ff-contacts-grid">
          {contacts.map((c) => (
            <div key={c.id} className="ff-contact-card">
              <div className="ff-contact-header">
                <span className={`ff-agency-badge ${c.agency_type.toLowerCase()}`}>
                  {c.agency_type}
                </span>
                {c.is_primary === 1 && (
                  <span className="ff-badge optimal">Primary Desk</span>
                )}
              </div>
              <h4 className="ff-contact-agency">{c.agency_name}</h4>
              <p className="ff-contact-person">
                Contact: <strong>{c.contact_person}</strong>
              </p>
              <div className="ff-contact-numbers">
                <div className="num-item">
                  <span className="lbl">Direct Line:</span>
                  <a href={`tel:${c.phone}`} className="val phone">{c.phone}</a>
                </div>
                <div className="num-item">
                  <span className="lbl">Emergency Dial:</span>
                  <span className="val dial">{c.emergency_number}</span>
                </div>
              </div>
              <p className="ff-contact-jurisdiction">
                <strong>Jurisdiction:</strong> {c.jurisdiction}
              </p>
              <p className="ff-contact-instructions">
                <strong>Dispatch SOP:</strong> {c.dispatch_instructions}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Escalation Audit History Table */}
      <div className="ff-card">
        <div className="ff-card-header">
          <div>
            <h3 className="ff-card-title">Emergency Escalation Audit & Delivery History</h3>
            <p className="ff-card-subtitle">
              Immutable record of all incident briefs transmitted to external authorities with transparent delivery states.
            </p>
          </div>
          <span className="ff-badge default">
            {escalations.length} Escalations Logged
          </span>
        </div>

        <div className="ff-table-wrapper">
          <table className="ff-table">
            <thead>
              <tr>
                <th>Escalation ID</th>
                <th>Incident Link</th>
                <th>Target Agency & Contact</th>
                <th>Channel & Delivery State</th>
                <th>Dispatched Time</th>
                <th>Police Acknowledgment</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {escalations.map((esc) => (
                <tr key={esc.id}>
                  <td>
                    <strong>{esc.escalation_id}</strong>
                  </td>
                  <td>
                    <span className="ff-badge purple">{esc.incident_id}</span>
                  </td>
                  <td>
                    <div>
                      <strong>{esc.agency_name}</strong>
                      <div className="ff-sub-text">{esc.recipient_name} • {esc.recipient_phone}</div>
                    </div>
                  </td>
                  <td>
                    <div>
                      <span className={`ff-badge ${esc.delivery_status === 'MANUALLY_REPORTED' ? 'warning' : 'optimal'}`}>
                        {esc.delivery_status.replace(/_/g, ' ')}
                      </span>
                      <div className="ff-sub-text">{esc.channel.replace(/_/g, ' ')}</div>
                    </div>
                  </td>
                  <td>
                    {esc.escalated_at ? esc.escalated_at.slice(0, 19).replace('T', ' ') : 'N/A'}
                  </td>
                  <td>
                    <span className={`ff-status-pill ${esc.police_ack_status === 'UNIT_DISPATCHED' ? 'optimal' : 'amber'}`}>
                      {esc.police_ack_status?.replace(/_/g, ' ')}
                    </span>
                    {esc.police_response_notes && (
                      <div className="ff-sub-text">{esc.police_response_notes}</div>
                    )}
                  </td>
                  <td>
                    <div className="ff-table-action-btns">
                      <button
                        type="button"
                        className="ff-btn ff-btn-outline xs"
                        onClick={() => handleCopyBrief(esc)}
                        title="Copy formatted dispatch brief for telephone call"
                      >
                        <ClipboardListIcon size={12} />
                        <span>Copy Brief</span>
                      </button>
                      {esc.police_ack_status !== 'UNIT_DISPATCHED' && (
                        <button
                          type="button"
                          className="ff-btn ff-btn-outline xs optimal"
                          onClick={() => {
                            setSelectedEscalationForAck(esc);
                          }}
                        >
                          <CheckIcon size={12} />
                          <span>Record Ack</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {escalations.length === 0 && (
                <tr>
                  <td colSpan={7} className="ff-text-center">
                    No emergency escalations have been dispatched for the current operational period.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Explicit Send / Escalate Confirmation Modal */}
      {isConfirmModalOpen && selectedIncident && (
        <div className="ff-modal-backdrop" onClick={() => setIsConfirmModalOpen(false)}>
          <div className="ff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ff-modal-header">
              <div className="ff-modal-title-group">
                <ShieldAlertIcon size={22} className="ff-text-danger" />
                <h3>Explicit Escalation to Emergency Services</h3>
              </div>
              <button
                type="button"
                className="ff-modal-close"
                onClick={() => setIsConfirmModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <div className="ff-escalation-review-box">
              <div className="review-item">
                <span className="lbl">Incident Identifier:</span>
                <span className="val bold">{selectedIncident.incident_id} ({selectedIncident.incident_type})</span>
              </div>
              <div className="review-item">
                <span className="lbl">Severity Level:</span>
                <span className={`val badge ${selectedIncident.severity?.toLowerCase()}`}>
                  {selectedIncident.severity}
                </span>
              </div>
              <div className="review-item">
                <span className="lbl">Location / Bus:</span>
                <span className="val">{selectedIncident.stop_name} • {selectedIncident.bus_number || 'N/A'}</span>
              </div>
              <div className="review-item">
                <span className="lbl">Verified Description:</span>
                <p className="val text">{selectedIncident.description}</p>
              </div>
            </div>

            <div className="ff-form-group">
              <label>Select Target Emergency Agency:</label>
              <select
                className="ff-select"
                value={selectedContactId}
                onChange={(e) => setSelectedContactId(e.target.value)}
              >
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.agency_name} — {c.contact_person} ({c.phone})
                  </option>
                ))}
              </select>
            </div>

            <div className="ff-form-group">
              <label>Operator Additional Dispatch Instructions:</label>
              <textarea
                className="ff-textarea"
                rows={2}
                value={escalationNotes}
                onChange={(e) => setEscalationNotes(e.target.value)}
                placeholder="e.g. Request mobile PCR van priority at Gate 2 for queue de-escalation..."
              />
            </div>

            <div className="ff-warning-notice">
              <AlertTriangleIcon size={16} />
              <span>
                Confirmation Required: This action records an immutable escalation log.
                If no SMS/Email API gateway is active, you must call the agency using the phone number above.
              </span>
            </div>

            <div className="ff-modal-actions">
              <button
                type="button"
                className="ff-btn ff-btn-outline"
                onClick={() => setIsConfirmModalOpen(false)}
                disabled={escalating}
              >
                Cancel
              </button>
              <button
                type="button"
                className="ff-btn ff-btn-danger"
                onClick={handleExecuteEscalation}
                disabled={escalating}
              >
                {escalating ? 'Transmitting Escalation...' : 'Confirm & Transmit Escalation'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Record Police Acknowledgment Modal */}
      {selectedEscalationForAck && (
        <div className="ff-modal-backdrop" onClick={() => setSelectedEscalationForAck(null)}>
          <div className="ff-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="ff-modal-header">
              <div className="ff-modal-title-group">
                <CheckCircleIcon size={20} className="ff-text-optimal" />
                <h3>Record Police Unit Response & Acknowledgment</h3>
              </div>
              <button
                type="button"
                className="ff-modal-close"
                onClick={() => setSelectedEscalationForAck(null)}
              >
                ✕
              </button>
            </div>

            <p className="ff-text-muted">
              Recording acknowledgement for <strong>{selectedEscalationForAck.escalation_id}</strong> (Target: {selectedEscalationForAck.agency_name}).
            </p>

            <div className="ff-form-group">
              <label>Police Unit Response Notes / Officer Name:</label>
              <textarea
                className="ff-textarea"
                rows={3}
                value={policeAckNotes}
                onChange={(e) => setPoliceAckNotes(e.target.value)}
                placeholder="e.g. Sub-Inspector Murugan confirmed PCR Unit 4 deployed to Bay 2..."
                required
              />
            </div>

            <div className="ff-modal-actions">
              <button
                type="button"
                className="ff-btn ff-btn-outline"
                onClick={() => setSelectedEscalationForAck(null)}
                disabled={savingAck}
              >
                Cancel
              </button>
              <button
                type="button"
                className="ff-btn ff-btn-primary"
                onClick={handleSavePoliceAck}
                disabled={savingAck}
              >
                {savingAck ? 'Recording Response...' : 'Save Unit Acknowledgment'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

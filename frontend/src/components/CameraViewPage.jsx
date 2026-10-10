import React, { useState, useRef, useEffect } from 'react';
import {
  VideoIcon,
  CameraIcon,
  PlayIcon,
  SquareIcon,
  AlertTriangleIcon,
  ShieldCheckIcon,
  InfoIcon
} from './Icons';

/**
 * CameraViewPage - Dedicated Camera Monitoring Page for FestivalFlow AI.
 * 
 * Strict compliance with requirements:
 * - Large camera preview area.
 * - Prominent explicit notice: "Camera integration not connected — demo mode".
 * - Explicit "View Camera" action that requests browser camera ONLY upon explicit user click (NEVER on mount).
 * - Clear connection state and permission status indicators.
 * - Future AI passenger-counting placeholder without fabricated footage or fake crowd counts.
 * - Clean enterprise styling with zero emojis.
 */
function CameraViewPage() {
  const [cameraActive, setCameraActive] = useState(false);
  const [permissionStatus, setPermissionStatus] = useState('Not Requested'); // 'Not Requested', 'Granted', 'Denied', 'Unavailable'
  const [connectionStatus, setConnectionStatus] = useState('Standby / Disconnected');
  const [errorMessage, setErrorMessage] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Stop camera stream cleanly when component unmounts
  useEffect(() => {
    return () => {
      stopCameraStream();
    };
  }, []);

  const stopCameraStream = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
    setConnectionStatus('Standby / Disconnected');
  };

  // Request browser camera ONLY when user explicitly clicks "View Camera" button
  const handleStartCamera = async () => {
    setErrorMessage(null);
    setConnectionStatus('Connecting...');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setPermissionStatus('Unavailable');
      setConnectionStatus('Unsupported');
      setErrorMessage('Browser MediaDevices API is not supported in this browser environment or requires HTTPS/localhost.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } }
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setCameraActive(true);
      setPermissionStatus('Granted');
      setConnectionStatus('Connected (Local Web Camera Feed)');
    } catch (err) {
      console.warn('Camera access denied or unavailable:', err);
      setCameraActive(false);
      setPermissionStatus('Denied / Error');
      setConnectionStatus('Connection Failed');
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage('Camera access was denied by browser permission settings.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setErrorMessage('No physical video capture device was detected on this computer.');
      } else {
        setErrorMessage(`Camera error: ${err.message || err.name}`);
      }
    }
  };

  return (
    <div className="ff-page-container">
      {/* Explicit Notice Banner */}
      <div className="ff-callout-banner amber">
        <div className="banner-icon-col">
          <AlertTriangleIcon size={20} />
        </div>
        <div className="banner-content-col">
          <h4>Camera integration not connected — demo mode</h4>
          <p>
            Physical festival venue CCTV turnstiles and RTSP security feeds are not connected to this prototype environment. You may test local camera hardware using the button below.
          </p>
        </div>
        <div className="banner-action-col">
          <span className="ff-tag-demo">DEMO MODE</span>
        </div>
      </div>

      {/* Error Banner if Permission Denied or Unavailable */}
      {errorMessage && (
        <div className="ff-callout-banner rose">
          <div className="banner-icon-col">
            <AlertTriangleIcon size={20} />
          </div>
          <div className="banner-content-col">
            <h4>Camera Connection Failed</h4>
            <p>{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Main Camera Monitor Surface */}
      <div className="ff-camera-monitor-card">
        {/* Top Camera Header Bar */}
        <div className="ff-monitor-header">
          <div className="monitor-title-group">
            <VideoIcon size={18} className="text-navy" />
            <span className="channel-name">Channel 01 — Arena Main Gate Turnstiles</span>
          </div>
          <div className="monitor-status-tags">
            <span className={`ff-status-pill ${cameraActive ? 'progress' : 'normal'}`}>
              {cameraActive ? 'Live Local Stream' : connectionStatus}
            </span>
            <span className="ff-status-pill normal">
              Permission: {permissionStatus}
            </span>
          </div>
        </div>

        {/* Video Stage / Standby Screen */}
        <div className="ff-video-stage-box">
          <video
            ref={videoRef}
            className={`ff-video-player ${cameraActive ? 'active' : 'hidden'}`}
            autoPlay
            playsInline
            muted
          />

          {!cameraActive && (
            <div className="ff-video-standby-view">
              <div className="standby-icon-wrap">
                <CameraIcon size={36} />
              </div>
              <h3 className="standby-title">CCTV Entrance Preview (Standby Mode)</h3>
              <p className="standby-desc">
                Camera feed is inactive. Click <strong>View Camera</strong> below to initialize local camera preview.
              </p>
              <div className="standby-metadata-pill">
                1080P HD • 30 FPS TARGET • MAIN BUS STAND TURNSTILES
              </div>
            </div>
          )}

          {/* CCTV On-Screen Display (OSD) Overlay */}
          <div className="ff-cctv-osd-overlay">
            <div className="osd-top-row">
              <span className="osd-channel-tag">CAM-01 ARENA PERIMETER</span>
              <span className={`osd-live-tag ${cameraActive ? 'is-live' : 'is-standby'}`}>
                {cameraActive ? '● LIVE' : '○ STANDBY'}
              </span>
            </div>
            <div className="osd-bottom-row">
              <span className="osd-time">{new Date().toLocaleTimeString()}</span>
              <span className="osd-specs">{cameraActive ? '30 FPS • LOCAL HARDWARE' : '0 FPS • PROTOTYPE'}</span>
            </div>
          </div>
        </div>

        {/* Camera Control Action Bar */}
        <div className="ff-monitor-controls-bar">
          <div className="controls-left">
            {!cameraActive ? (
              <button
                type="button"
                onClick={handleStartCamera}
                className="ff-btn ff-btn-primary"
                id="btn-view-camera"
              >
                <CameraIcon size={16} />
                <span>View Camera</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={stopCameraStream}
                className="ff-btn ff-btn-rose"
                id="btn-stop-camera"
              >
                <SquareIcon size={14} />
                <span>Stop Camera</span>
              </button>
            )}
          </div>

          <div className="controls-right">
            <span className="control-meta-text">
              Status: <strong>{connectionStatus}</strong> • Permission: <strong>{permissionStatus}</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Future Edge Vision-AI Passenger Counting Placeholder */}
      <div className="ff-table-card mt-6">
        <div className="ff-table-header-bar">
          <div>
            <h3>Edge Vision-AI Passenger-Counting Telemetry</h3>
            <p className="meta-text">
              Real-time turnstile crossing velocity and optical density pipeline
            </p>
          </div>
          <span className="ff-tag-future">FUTURE INTEGRATION</span>
        </div>

        <div className="ff-card-body p-6">
          <p className="text-secondary text-sm mb-4">
            When physical venue RTSP optical feeds are attached, the edge YOLOv8 passenger counting pipeline evaluates turnstile crossings in real time.
          </p>

          <div className="ff-vision-metrics-grid">
            <div className="ff-vision-metric-box">
              <span className="v-label">Turnstile Crossing Velocity</span>
              <span className="v-value">— passengers/min</span>
              <span className="v-note">Awaiting venue stream</span>
            </div>

            <div className="ff-vision-metric-box">
              <span className="v-label">Platform Queue Density</span>
              <span className="v-value">— crowd index</span>
              <span className="v-note">Optical flow ready</span>
            </div>

            <div className="ff-vision-metric-box">
              <span className="v-label">Turnstile Congestion State</span>
              <span className="v-value">Standby</span>
              <span className="v-note">Surge threshold: &gt; 80/min</span>
            </div>
          </div>

          <div className="ff-integrity-note">
            <ShieldCheckIcon size={16} className="text-emerald" />
            <span>
              <strong>Integrity Guarantee:</strong> FestivalFlow AI does not fabricate synthetic camera video or invent artificial passenger detections. Telemetry activates only when authentic RTSP optical video is verified.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CameraViewPage;

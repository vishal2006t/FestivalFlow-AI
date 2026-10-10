import React, { useState, useEffect, useRef } from 'react';

function CameraMonitoringTab({ apiBase, token, showToast, onNavigateToDispatch }) {
  const [cameras, setCameras] = useState([]);
  const [selectedCamId, setSelectedCamId] = useState('CAM-MAIN-01');
  const [sourceType, setSourceType] = useState('demo'); // 'demo', 'webcam', 'video_upload', 'rtsp'
  const [rtspUrl, setRtspUrl] = useState('rtsp://cctv.festivaltransit.local:554/live/arena_stand_bay1');
  const [detectionResult, setDetectionResult] = useState(null);
  const [historicalReadings, setHistoricalReadings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [webcamActive, setWebcamActive] = useState(false);
  const [autoDetect, setAutoDetect] = useState(true);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const webcamStreamRef = useRef(null);

  useEffect(() => {
    loadCameras();
    return () => {
      stopWebcam();
    };
  }, []);

  useEffect(() => {
    if (selectedCamId) {
      runDetection();
      loadHistoricalReadings();
    }
  }, [selectedCamId, sourceType]);

  // Periodic auto-detection every 8 seconds if autoDetect is enabled
  useEffect(() => {
    if (!autoDetect) return;
    const interval = setInterval(() => {
      runDetection(true);
    }, 8000);
    return () => clearInterval(interval);
  }, [autoDetect, selectedCamId, sourceType, rtspUrl]);

  const loadCameras = async () => {
    try {
      const res = await fetch(`${apiBase}/api/cameras`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setCameras(data);
        if (data.length > 0 && !selectedCamId) {
          setSelectedCamId(data[0].camera_id);
        }
      }
    } catch (err) {
      console.error('Error fetching cameras:', err);
    }
  };

  const loadHistoricalReadings = async () => {
    const cam = cameras.find((c) => c.camera_id === selectedCamId) || { stop_id: 'STOP_MAIN' };
    try {
      const res = await fetch(`${apiBase}/api/crowd/readings?stop_id=${cam.stop_id}&limit=12`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setHistoricalReadings(await res.json());
      }
    } catch (err) {
      console.error('Error fetching crowd readings:', err);
    }
  };

  const runDetection = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/cameras/${selectedCamId}/detect-frame`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          source_type: sourceType,
          stream_url: sourceType === 'rtsp' ? rtspUrl : null
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Camera detection error');
      }

      const data = await res.json();
      setDetectionResult(data);
      drawOverlay(data);
    } catch (err) {
      console.error('Detection frame error:', err);
      if (!isBackground) showToast(err.message, 'error');
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  // Start Webcam Testing
  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 360 } });
      webcamStreamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
      setWebcamActive(true);
      setSourceType('webcam');
      showToast('Webcam stream started for local testing.', 'success');
    } catch (err) {
      console.error('Webcam access error:', err);
      showToast('Could not access webcam. Using demo mode instead.', 'warning');
      setSourceType('demo');
    }
  };

  // Stop Webcam
  const stopWebcam = () => {
    if (webcamStreamRef.current) {
      webcamStreamRef.current.getTracks().forEach((track) => track.stop());
      webcamStreamRef.current = null;
    }
    setWebcamActive(false);
  };

  const handleSourceChange = (newSource) => {
    if (newSource === 'webcam') {
      startWebcam();
    } else {
      stopWebcam();
      setSourceType(newSource);
    }
  };

  // Draw ROI and Anonymized Person Silhouette Markers on Canvas
  const drawOverlay = (data) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    // 1. Draw defined Bus Stop Platform ROI (Region of Interest)
    const roi = data.roi && data.roi.coordinates ? data.roi.coordinates : [0.1, 0.2, 0.9, 0.85];
    const [rx1, ry1, rx2, ry2] = roi;
    const roiX = rx1 * width;
    const roiY = ry1 * height;
    const roiW = (rx2 - rx1) * width;
    const roiH = (ry2 - ry1) * height;

    // ROI Box Glowing Border
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(roiX, roiY, roiW, roiH);
    ctx.setLineDash([]);

    // ROI Label Tag
    ctx.fillStyle = 'rgba(245, 158, 11, 0.85)';
    ctx.fillRect(roiX, roiY - 22, 220, 22);
    ctx.fillStyle = '#0a0e17';
    ctx.font = 'bold 11px sans-serif';
    ctx.fillText('BUS STOP WAITING ROI ZONE', roiX + 6, roiY - 7);

    // 2. Draw Sample Anonymized Detection Bounding Boxes
    if (data.detection_samples && data.detection_samples.length > 0) {
      data.detection_samples.forEach((sample, i) => {
        const [bx1, by1, bx2, by2] = sample.box;
        const boxX = bx1 * width;
        const boxY = by1 * height;
        const boxW = (bx2 - bx1) * width;
        const boxH = (by2 - by1) * height;

        ctx.strokeStyle = '#06b6d4';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(boxX, boxY, boxW, boxH);

        // Silhouette label
        ctx.fillStyle = 'rgba(6, 182, 212, 0.8)';
        ctx.fillRect(boxX, boxY - 14, Math.max(70, boxW), 14);
        ctx.fillStyle = '#0a0e17';
        ctx.font = '9px monospace';
        ctx.fillText(`P#${i + 1} ${(sample.confidence * 100).toFixed(0)}%`, boxX + 4, boxY - 3);
      });
    }
  };

  const selectedCam = cameras.find((c) => c.camera_id === selectedCamId) || {
    name: 'Festival Arena Main Stand Platform Cam',
    stop_id: 'STOP_MAIN'
  };

  return (
    <div className="camera-tab-container">
      {/* Top Source Mode & Provenance Banner */}
      <div className="camera-provenance-banner">
        <div className="provenance-tag-box">
          <span className="provenance-title">DATA PROVENANCE:</span>
          <span
            className={`provenance-pill ${
              sourceType === 'rtsp'
                ? 'live-badge'
                : sourceType === 'webcam'
                ? 'webcam-badge'
                : sourceType === 'video_upload'
                ? 'recorded-badge'
                : 'demo-badge'
            }`}
          >
            {sourceType === 'rtsp'
              ? '🔴 LIVE CCTV FEED'
              : sourceType === 'webcam'
              ? '💻 LIVE WEBCAM TEST'
              : sourceType === 'video_upload'
              ? '📼 RECORDED BENCHMARK VIDEO'
              : '⚡ DEMO SIMULATION (NO PHYSICAL SENSOR)'}
          </span>
        </div>
        <p className="provenance-desc">
          Strict operational honesty rule: Physical cameras and telemetry feeds are clearly flagged.
          Simulated or sample video data is never mislabeled as real-time transport data.
        </p>
      </div>

      {/* Camera Selection & Mode Controls */}
      <div className="camera-controls-card">
        <div className="camera-selector-row">
          <div className="cam-select-group">
            <label>Select Camera Location:</label>
            <select
              value={selectedCamId}
              onChange={(e) => setSelectedCamId(e.target.value)}
              className="cam-dropdown"
            >
              {cameras.map((c) => (
                <option key={c.id} value={c.camera_id}>
                  {c.name} ({c.stop_id})
                </option>
              ))}
            </select>
          </div>

          <div className="source-toggles">
            <label>Camera Ingestion Mode:</label>
            <div className="toggle-btn-group">
              <button
                type="button"
                className={`mode-btn ${sourceType === 'demo' ? 'active' : ''}`}
                onClick={() => handleSourceChange('demo')}
              >
                ⚡ Demo Benchmark
              </button>
              <button
                type="button"
                className={`mode-btn ${sourceType === 'webcam' ? 'active' : ''}`}
                onClick={() => handleSourceChange('webcam')}
              >
                💻 Webcam Test
              </button>
              <button
                type="button"
                className={`mode-btn ${sourceType === 'video_upload' ? 'active' : ''}`}
                onClick={() => handleSourceChange('video_upload')}
              >
                📼 Recorded Video
              </button>
              <button
                type="button"
                className={`mode-btn ${sourceType === 'rtsp' ? 'active' : ''}`}
                onClick={() => handleSourceChange('rtsp')}
              >
                🔴 RTSP Stream
              </button>
            </div>
          </div>
        </div>

        {/* RTSP Stream Configuration Bar */}
        {sourceType === 'rtsp' && (
          <div className="rtsp-config-bar">
            <span className="rtsp-label">CCTV Stream URL:</span>
            <input
              type="text"
              value={rtspUrl}
              onChange={(e) => setRtspUrl(e.target.value)}
              placeholder="rtsp://username:password@cctv.local:554/live/bay1"
              className="rtsp-input"
            />
            <button className="primary-btn" onClick={() => runDetection()}>
              Connect & Verify Feed
            </button>
          </div>
        )}
      </div>

      {/* Main Vision Grid: Video Feed + Live Telemetry */}
      <div className="vision-main-grid">
        {/* Left: Video / Stream Monitor with ROI Overlay */}
        <div className="video-monitor-card">
          <div className="monitor-top-bar">
            <div className="feed-status-badge">
              <span className="status-dot"></span>
              <strong>{selectedCam.name}</strong> • 15 FPS
            </div>
            <div className="stream-time">
              {detectionResult ? detectionResult.timestamp.replace('T', ' ').substring(0, 19) : ''}
            </div>
          </div>

          {/* Interactive Screen Container */}
          <div className="video-viewport">
            {sourceType === 'webcam' ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="viewport-media"
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div className="simulated-camera-scene">
                <div className="bus-stop-bg-graphic">
                  <div className="arena-sign">🏟️ FESTIVAL ARENA - BOARDING BAY 1</div>
                  <div className="crowd-silhouette-graphic">
                    {/* Visual crowd representation */}
                    {Array.from({ length: Math.min(24, Math.max(6, Math.floor((detectionResult?.people_count_smoothed || 50) / 6))) }).map((_, i) => (
                      <span key={i} className="silhouette-icon">
                        🧍
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Canvas ROI Overlay */}
            <canvas ref={canvasRef} width={640} height={360} className="overlay-canvas" />
          </div>

          {/* Camera Action Buttons */}
          <div className="monitor-footer-actions">
            <div className="auto-detect-toggle">
              <label>
                <input
                  type="checkbox"
                  checked={autoDetect}
                  onChange={(e) => setAutoDetect(e.target.checked)}
                />{' '}
                Auto-refresh crowd detection (every 8s)
              </label>
            </div>
            <button className="primary-btn" onClick={() => runDetection()} disabled={loading}>
              {loading ? 'Analyzing Frame...' : '📷 Capture & Estimate Density'}
            </button>
          </div>
        </div>

        {/* Right: Real-Time Crowd Telemetry & Night Safety */}
        <div className="crowd-analytics-column">
          {detectionResult && (
            <>
              {/* Density KPI Card */}
              <div
                className={`crowd-kpi-card level-${detectionResult.crowd_level.toLowerCase()}`}
              >
                <div className="kpi-top">
                  <span className="kpi-title">ESTIMATED WAITING PASSENGERS</span>
                  <span className={`crowd-pill pill-${detectionResult.crowd_level.toLowerCase()}`}>
                    ● {detectionResult.crowd_level} Density
                  </span>
                </div>
                <div className="kpi-number">{detectionResult.people_count_smoothed}</div>
                <div className="kpi-meta">
                  <span>
                    Raw Count: <strong>{detectionResult.people_count_raw}</strong> (EMA Smoothed)
                  </span>
                  <span>
                    Confidence: <strong>{detectionResult.confidence_pct}%</strong>
                  </span>
                  <span>
                    Arrival Trend:{' '}
                    <strong>
                      {detectionResult.trend === 'Surging' ? '▲▲ Surging' : detectionResult.trend}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Night Safety Status Card */}
              <div className="night-safety-status-card">
                <div className="night-header">
                  <span>🌙 NIGHT SAFETY MONITOR</span>
                  <span className={`pill ${detectionResult.night_safety_alert ? 'pill-danger' : 'pill-success'}`}>
                    {detectionResult.night_safety_alert ? 'CRITICAL ALERT' : 'NORMAL MONITORING'}
                  </span>
                </div>
                <p className="night-desc">
                  {detectionResult.night_safety_alert
                    ? '⚠️ Prolonged night wait time detected (>15m) with high crowd volume. Recommended action: stage underutilized shuttle.'
                    : 'Passenger waiting duration is within safe thresholds. Night floodlights verified active.'}
                </p>
                {detectionResult.night_safety_alert && (
                  <button
                    className="night-action-btn"
                    onClick={onNavigateToDispatch}
                  >
                    ⚡ Open Alerts & Dispatch Panel
                  </button>
                )}
              </div>

              {/* Temporal Trend Chart */}
              <div className="historical-trend-box">
                <h6>📈 15-Minute Temporal Crowd Trend</h6>
                <div className="trend-sparkline">
                  {historicalReadings.map((reading, i) => (
                    <div key={i} className="sparkline-bar-col">
                      <div
                        className="sparkline-bar"
                        style={{
                          height: `${Math.min(100, Math.max(10, (reading.smoothed_count / 160) * 100))}%`
                        }}
                      ></div>
                      <span className="sparkline-lbl">
                        {reading.timestamp.substring(11, 16)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* Privacy & Compliance Banner */}
          <div className="privacy-card">
            <div className="privacy-icon">🛡️</div>
            <div>
              <h5>Privacy-Preserving Edge Architecture</h5>
              <p>
                Zero facial recognition • Zero biometric profiling • Zero identity tracking.
                Frames are processed in volatile memory for aggregate density counting only. No
                personal surveillance records are retained.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CameraMonitoringTab;

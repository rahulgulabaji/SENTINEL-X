import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { createApiClient } from './services/api';

/* ==========================================================================
   HIGH-TECH TACTICAL SVG ICONS (1:1 FIDELITY)
   ========================================================================== */
const Icon = ({ path, className = "w-4 h-4", viewBox = "0 0 24 24" }) => (
  <svg className={className} fill="none" viewBox={viewBox} stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d={path} />
  </svg>
);

const Icons = {
  Shield: (p) => <Icon path="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" {...p} />,
  Video: (p) => <Icon path="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" {...p} />,
  Activity: (p) => <Icon path="M22 12h-4l-3 9L9 3l-3 9H2" {...p} />,
  Upload: (p) => <Icon path="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" {...p} />,
  Terminal: (p) => <Icon path="M4 17l6-6-6-6M12 19h8" {...p} />,
  FileText: (p) => <Icon path="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6" {...p} />,
  Settings: (p) => <Icon path="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" {...p} />,
  CheckCircle: (p) => <Icon path="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" {...p} />,
  AlertTriangle: (p) => <Icon path="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01" {...p} />,
  Play: (p) => <Icon path="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" {...p} />,
  Cpu: (p) => <Icon path="M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m-2 6h2m14-6h2m-2 6h2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" {...p} />,
  Zap: (p) => <Icon path="M13 10V3L4 14h7v7l9-11h-7z" {...p} />,
  ChevronRight: (p) => <Icon path="M9 5l7 7-7 7" {...p} />,
  Server: (p) => <Icon path="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" {...p} />,
  Layers: (p) => <Icon path="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" {...p} />,
  X: (p) => <Icon path="M6 18L18 6M6 6l12 12" {...p} />,
  Crosshair: (p) => <Icon path="M12 2v4m0 12v4M2 12h4m12 0h4M12 8a4 4 0 100 8 4 4 0 000-8z" {...p} />,
  Bot: (p) => <Icon path="M12 2a2 2 0 012 2v2a2 2 0 01-2 2 2 2 0 01-2-2V4a2 2 0 012-2zm-7 7a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V9zm3 3h.01M16 12h.01M9 16h6" {...p} />,
  User: (p) => <Icon path="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" {...p} />,
  Send: (p) => <Icon path="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" {...p} />,
  Sparkles: (p) => <Icon path="M5 3v4M3 5h4M6 17v4m-2-2h4m11-16l1.2 3.6L20 10l-3.6 1.2L15 15l-1.2-3.6L10 10l3.6-1.2L15 4z" {...p} />,
  Paperclip: (p) => <Icon path="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" {...p} />,
  Copy: (p) => <Icon path="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" {...p} />,
  RefreshCw: (p) => <Icon path="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" {...p} />,
  CornerDownLeft: (p) => <Icon path="M9 10l-5 5m0 0l5 5m-5-5h11a4 4 0 004-4V4" {...p} />,
  Map: (p) => <Icon path="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" {...p} />,
  Radio: (p) => <Icon path="M4.929 4.929a10 10 0 0114.142 0M7.757 7.757a6 6 0 018.486 0M10.586 10.586a2 2 0 012.828 0M12 14v6" {...p} />,
  MapPin: (p) => <Icon path="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 11-6 0 3 3 0 016 0z" {...p} />
};

/* ==========================================================================
   DEFAULT FEEDS & RESPONDERS (PINNED TO NIPANI CITY, KARNATAKA, INDIA)
   ========================================================================== */
const DEMO_VIDEO_SOURCES = [
  {
    id: 'FEED-NIPANI-NORTH-01',
    title: 'Perimeter Fence - Nipani Industrial Zone',
    type: 'anomaly',
    location: 'Zone A - Industrial Perimeter, Nipani, Karnataka, India',
    resolution: '1920x1080 @ 30 FPS',
    status: 'Active Feed',
    sampleName: 'perimeter_intrusion.mp4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    lat: 16.4022,
    lng: 74.3820
  },
  {
    id: 'FEED-NIPANI-HIGHWAY-02',
    title: 'Nipani PB Road Highway Corridor',
    type: 'vision_yolo',
    location: 'NH48 Junction, Nipani, Belagavi Dist., Karnataka',
    resolution: '3840x2160 @ 60 FPS',
    status: 'Active Feed',
    sampleName: 'concourse_crowd.mp4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
    lat: 16.4085,
    lng: 74.3860
  },
  {
    id: 'FEED-NIPANI-CENTRAL-03',
    title: 'Nipani Municipal Facility & Depot',
    type: 'anomaly',
    location: 'Central Town Sector, Nipani, Karnataka, India',
    resolution: '1920x1080 @ 60 FPS',
    status: 'Active Feed',
    sampleName: 'vault_breach_test.mp4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4',
    lat: 16.3980,
    lng: 74.3795
  }
];

const TACTICAL_RESPONDERS = [
  {
    id: 'PATROL-NIPANI-01',
    unit: 'Nipani Highway Patrol Alpha',
    location: 'NH-48 Highway Junction, Nipani',
    lat: 16.4045,
    lng: 74.3840,
    status: 'Active Patrol',
    eta: '1.2 min'
  },
  {
    id: 'SECTOR-NIPANI-02',
    unit: 'Nipani KSRTC Sector Squad',
    location: 'Bus Terminal Sector, Central Nipani',
    lat: 16.4010,
    lng: 74.3815,
    status: 'Stationary',
    eta: '2.5 min'
  },
  {
    id: 'INTERCEPT-NIPANI-03',
    unit: 'Belagavi District Special Recon',
    location: 'Industrial Estate Road, Nipani',
    lat: 16.3965,
    lng: 74.3770,
    status: 'En Route',
    eta: '3.8 min'
  }
];

const INITIAL_CHAT_MESSAGES = [
  {
    id: 'msg-1',
    sender: 'assistant',
    timestamp: '09:14:02',
    text: 'SENTINEL-X AI Tactical Copilot active. Connected to Nipani Sector (Karnataka, India) with Stage-1 I3D and Stage-2 Swin3D action classifiers alongside YOLOv8 tracking pipeline.\n\nHow can I assist your security ops team in Nipani?',
    type: 'system_welcome',
    meta: { model: 'SENTINEL-LLM-3.5-TACTICAL', context: 'Nipani, Karnataka, India' }
  }
];

// CartoDB Voyager Tile API URL with User-supplied API key
const CARTO_VOYAGER_TILE_URL = "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_4ckp_1_7534d1fa2c9926ff66187e39";

/* ==========================================================================
   MAIN SENTINEL APPLICATION CONTROLLER
   ========================================================================== */
export default function App() {
  const [view, setView] = useState('landing'); // 'landing' | 'analysis' | 'copilot' | 'logs'
  const [analysisMode, setAnalysisMode] = useState('anomaly'); // 'anomaly' | 'vision_yolo'
  const [backendUrl, setBackendUrl] = useState('http://localhost:8000');
  const [apiHealth, setApiHealth] = useState({ connected: false, checking: true, details: null, error: null });
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showMapModal, setShowMapModal] = useState(false);
  const [simulatedEngineMode, setSimulatedEngineMode] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  // Selected video feed / custom upload
  const [selectedSource, setSelectedSource] = useState(DEMO_VIDEO_SOURCES[0]);
  const [customFile, setCustomFile] = useState(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState(DEMO_VIDEO_SOURCES[0].videoUrl);

  // Video Bounding Box Toggles for YOLO mode
  const [toggleDetections, setToggleDetections] = useState(true);
  const [toggleTracks, setToggleTracks] = useState(true);

  // Active Job State
  const [activeJob, setActiveJob] = useState(null);

  // Historical Audit Logs
  const [jobHistory, setJobHistory] = useState([]);
  const [selectedLogItem, setSelectedLogItem] = useState(null);

  // Tactical Chatbot State
  const [chatMessages, setChatMessages] = useState(INITIAL_CHAT_MESSAGES);
  const [chatInput, setChatInput] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [attachedFrame, setAttachedFrame] = useState(false);
  const chatEndRef = useRef(null);

  // Selected Tactical Responder
  const [selectedResponder, setSelectedResponder] = useState(TACTICAL_RESPONDERS[0]);

  // Canvas ref for overlay bounding box drawing
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Leaflet Map Refs
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const tileLayerRef = useRef(null);
  const markersRef = useRef([]);

  const apiClient = useMemo(() => createApiClient(backendUrl), [backendUrl]);

  const showToast = useCallback((msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  }, []);

  // Backend Health Poller
  const checkBackendHealth = useCallback(async () => {
    setApiHealth(prev => ({ ...prev, checking: true }));
    const health = await apiClient.checkHealth();
    setApiHealth({
      connected: health.connected,
      checking: false,
      details: health.data || null,
      error: health.error || null
    });
  }, [apiClient]);

  useEffect(() => {
    checkBackendHealth();
    const timer = setInterval(checkBackendHealth, 10000);
    return () => clearInterval(timer);
  }, [checkBackendHealth]);

  // Chat auto-scroll
  useEffect(() => {
    if (view === 'copilot' && chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, isThinking, view]);

  // Active Job Status Polling
  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') {
      return;
    }

    let isSubscribed = true;

    const pollJobStatus = async () => {
      if (simulatedEngineMode) {
        setTimeout(() => {
          if (!isSubscribed) return;
          if (activeJob.status === 'queued') {
            setActiveJob(prev => ({ ...prev, status: 'processing' }));
          } else if (activeJob.status === 'processing') {
            const isAnomaly = activeJob.system === 'anomaly';

            let mockResult;
            if (isAnomaly) {
              mockResult = {
                job_id: activeJob.jobId,
                status: 'completed',
                system_type: 'anomaly',
                anomaly_status: 'DETECTED',
                anomaly_probability: 0.884,
                likely_action: 'Perimeter Fence Breach / Climbing',
                action_confidence: 0.932,
                processing_time_seconds: 3.18,
                alternative_candidates: [
                  { action: 'Loitering at Gate Boundary', confidence: 0.051 },
                  { action: 'Object Dropping / Foreign Item', confidence: 0.012 },
                  { action: 'Normal Walking Motion', confidence: 0.005 }
                ],
                model_info: {
                  stage1_name: 'Sentinel-I3D-ResNet50-v2',
                  stage2_name: 'Sentinel-Swin3D-AnomalyClassifier',
                  i3d_backbone: 'Kinetics-400 Pretrained Feature Tensor'
                },
                video_meta: {
                  resolution: '1920x1080',
                  fps: 30,
                  duration_sec: 14.2
                },
                timestamp: new Date().toISOString()
              };
            } else {
              mockResult = {
                job_id: activeJob.jobId,
                status: 'completed',
                system_type: 'vision_yolo',
                object_summary: {
                  people_count: 7,
                  vehicles_count: 3,
                  unique_tracks: 10,
                  max_persons_in_frame: 9,
                  max_vehicles_in_frame: 4
                },
                detections: [
                  { class_name: 'person', confidence: 0.94, bbox: [120, 80, 240, 380], track_id: 'TRK-001' },
                  { class_name: 'person', confidence: 0.89, bbox: [310, 110, 410, 390], track_id: 'TRK-002' },
                  { class_name: 'car', confidence: 0.96, bbox: [520, 210, 780, 410], track_id: 'TRK-003' },
                  { class_name: 'person', confidence: 0.82, bbox: [810, 95, 900, 320], track_id: 'TRK-004' }
                ],
                tracks: [
                  { track_id: 'TRK-001', class_name: 'person', duration_sec: 12.4, direction: 'North-East', confidence_avg: 0.92 },
                  { track_id: 'TRK-002', class_name: 'person', duration_sec: 9.1, direction: 'South-West', confidence_avg: 0.88 },
                  { track_id: 'TRK-003', class_name: 'car', duration_sec: 14.2, direction: 'East-Bound', confidence_avg: 0.95 }
                ],
                performance: {
                  processing_time_seconds: 1.45,
                  inference_fps: 42.8,
                  average_latency_ms: 23.4
                },
                model_info: {
                  model_name: 'YOLOv8-Enterprise-Vision',
                  device: 'NVIDIA RTX 4090 (CUDA)',
                  input_size: '640x640'
                },
                timestamp: new Date().toISOString()
              };
            }

            setActiveJob(prev => ({ ...prev, status: 'completed', result: mockResult }));
            setJobHistory(prev => [mockResult, ...prev]);
          }
        }, 2000);
        return;
      }

      try {
        const statusData = await apiClient.getJobStatus(activeJob.jobId);
        if (!isSubscribed) return;

        if (statusData.status === 'completed') {
          const resultData = await apiClient.getJobResult(activeJob.jobId);
          if (!isSubscribed) return;

          setActiveJob(prev => ({
            ...prev,
            status: 'completed',
            result: resultData
          }));

          setJobHistory(prev => [resultData, ...prev]);
        } else if (statusData.status === 'failed') {
          setActiveJob(prev => ({
            ...prev,
            status: 'failed',
            error: statusData.error || 'Pipeline error encountered during neural model execution'
          }));
        } else {
          setActiveJob(prev => ({
            ...prev,
            status: statusData.status
          }));
        }
      } catch (err) {
        if (!isSubscribed) return;
        console.error('Job status polling error:', err);
      }
    };

    const intervalId = setInterval(pollJobStatus, 2500);
    pollJobStatus();

    return () => {
      isSubscribed = false;
      clearInterval(intervalId);
    };
  }, [activeJob, apiClient, simulatedEngineMode]);

  // Real-time Canvas Bounding Box Rendering
  useEffect(() => {
    if (!canvasRef.current || !videoRef.current) return;

    const canvas = canvasRef.current;
    const video = videoRef.current;
    const ctx = canvas.getContext('2d');

    let animationFrameId;

    const drawOverlay = () => {
      if (!video || video.paused || video.ended) {
        animationFrameId = requestAnimationFrame(drawOverlay);
        return;
      }

      canvas.width = video.clientWidth;
      canvas.height = video.clientHeight;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (
        analysisMode === 'vision_yolo' &&
        activeJob &&
        activeJob.status === 'completed' &&
        activeJob.result &&
        activeJob.result.detections &&
        toggleDetections
      ) {
        const videoNativeW = video.videoWidth || 1920;
        const videoNativeH = video.videoHeight || 1080;

        const scaleX = canvas.width / videoNativeW;
        const scaleY = canvas.height / videoNativeH;

        activeJob.result.detections.forEach((det) => {
          if (!det.bbox) return;

          const [x1, y1, x2, y2] = det.bbox;
          const boxX = x1 * scaleX;
          const boxY = y1 * scaleY;
          const boxW = (x2 - x1) * scaleX;
          const boxH = (y2 - y1) * scaleY;

          ctx.strokeStyle = '#3B82F6';
          ctx.lineWidth = 2;
          ctx.strokeRect(boxX, boxY, boxW, boxH);

          ctx.fillStyle = 'rgba(59, 130, 246, 0.85)';
          const labelText = `${det.class_name.toUpperCase()} ${(det.confidence * 100).toFixed(0)}%${
            toggleTracks && det.track_id ? ` [${det.track_id}]` : ''
          }`;

          ctx.font = '10px "IBM Plex Mono", monospace';
          const textMetrics = ctx.measureText(labelText);
          ctx.fillRect(boxX, boxY > 18 ? boxY - 18 : boxY, textMetrics.width + 8, 18);

          ctx.fillStyle = '#FFFFFF';
          ctx.fillText(labelText, boxX + 4, boxY > 18 ? boxY - 5 : boxY + 12);
        });
      }

      animationFrameId = requestAnimationFrame(drawOverlay);
    };

    drawOverlay();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [analysisMode, activeJob, toggleDetections, toggleTracks]);

  // Leaflet Map Initialization with CartoDB Voyager API Layer
  useEffect(() => {
    if (!showMapModal || !mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const initialLat = selectedSource.lat || 16.4022;
      const initialLng = selectedSource.lng || 74.3820;

      const map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLng],
        zoom: 14,
        zoomControl: true,
        attributionControl: true
      });

      // Integrate CartoDB Voyager raster tiles with provided API key
      const voyagerLayer = L.tileLayer(CARTO_VOYAGER_TILE_URL, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19
      }).addTo(map);

      tileLayerRef.current = voyagerLayer;
      mapInstanceRef.current = map;

      // Invalidate size once modal animation completes
      setTimeout(() => {
        map.invalidateSize();
      }, 200);
    } else {
      if (selectedSource.lat && selectedSource.lng) {
        mapInstanceRef.current.setView([selectedSource.lat, selectedSource.lng], 14);
      }
    }

    const map = mapInstanceRef.current;

    // Clear previous markers
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    // Camera Marker
    if (selectedSource.lat && selectedSource.lng) {
      const cameraIcon = L.divIcon({
        className: 'custom-map-icon',
        html: `<div style="width:16px;height:16px;border-radius:9999px;background:#3B82F6;border:2px solid #FFFFFF;box-shadow:0 0 12px rgba(59,130,246,0.8);"></div>`,
        iconSize: [16, 16]
      });

      const camMarker = L.marker([selectedSource.lat, selectedSource.lng], { icon: cameraIcon }).addTo(map);
      camMarker.bindPopup(`<b>${selectedSource.title}</b><br/>ID: ${selectedSource.id}<br/>Location: ${selectedSource.location}<br/>Coordinates: ${selectedSource.lat}, ${selectedSource.lng} (Nipani, Karnataka)`).openPopup();
      markersRef.current.push(camMarker);
    }

    // Tactical Patrol Responder Markers
    TACTICAL_RESPONDERS.forEach((responder) => {
      const isSelected = selectedResponder && selectedResponder.id === responder.id;
      const responderIcon = L.divIcon({
        className: 'custom-map-icon',
        html: `<div style="width:14px;height:14px;border-radius:9999px;background:${isSelected ? '#10B981' : '#F59E0B'};border:2px solid #FFFFFF;box-shadow:0 0 10px ${isSelected ? '#10B981' : '#F59E0B'};"></div>`,
        iconSize: [14, 14]
      });

      const rMarker = L.marker([responder.lat, responder.lng], { icon: responderIcon }).addTo(map);
      rMarker.bindPopup(`<b>${responder.id}</b><br/>${responder.unit}<br/>Status: <b>${responder.status}</b><br/>ETA: ${responder.eta}<br/>Location: Nipani Sector`);
      rMarker.on('click', () => setSelectedResponder(responder));
      markersRef.current.push(rMarker);
    });

    return () => {
      if (!showMapModal && mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [showMapModal, selectedSource, selectedResponder]);

  const handleSelectSource = (source) => {
    setSelectedSource(source);
    setCustomFile(null);
    setVideoPreviewUrl(source.videoUrl);
    setActiveJob(null);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCustomFile(file);
    const fileUrl = URL.createObjectURL(file);
    setVideoPreviewUrl(fileUrl);
    setSelectedSource({
      id: 'USER-CUSTOM-UPLOAD',
      title: file.name,
      type: analysisMode,
      location: 'Local Storage Upload - Nipani Sector',
      resolution: `${(file.size / (1024 * 1024)).toFixed(1)} MB Video File`,
      status: 'Custom File',
      sampleName: file.name,
      lat: 16.4022,
      lng: 74.3820
    });
    setActiveJob(null);
  };

  const handleTriggerAnalysis = async () => {
    setActiveJob({
      jobId: 'INITIALIZING',
      status: 'queued',
      result: null,
      error: null,
      system: analysisMode,
      startTime: new Date().toLocaleTimeString()
    });

    if (!apiHealth.connected && !simulatedEngineMode) {
      setActiveJob({
        jobId: `JOB-SIM-${Date.now().toString().slice(-6)}`,
        status: 'queued',
        result: null,
        error: null,
        system: analysisMode,
        startTime: new Date().toLocaleTimeString()
      });
      setSimulatedEngineMode(true);
      return;
    }

    try {
      let response;
      if (customFile) {
        response = await apiClient.submitAnalysis({ file: customFile, systemType: analysisMode });
      } else {
        response = await apiClient.submitAnalysis({ videoUrl: videoPreviewUrl, systemType: analysisMode });
      }

      setActiveJob({
        jobId: response.job_id || `JOB-${Math.floor(Math.random() * 90000 + 10000)}`,
        status: response.status || 'queued',
        result: null,
        error: null,
        system: analysisMode,
        startTime: new Date().toLocaleTimeString()
      });
    } catch (err) {
      setActiveJob({
        jobId: 'ERROR',
        status: 'failed',
        result: null,
        error: err.message || 'Failed to trigger job on backend API',
        system: analysisMode,
        startTime: new Date().toLocaleTimeString()
      });
    }
  };

  const handleSendMessage = (textToSend) => {
    const query = textToSend || chatInput;
    if (!query.trim() && !attachedFrame) return;

    const userMsg = {
      id: `msg-${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      text: query,
      hasFrame: attachedFrame
    };

    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setAttachedFrame(false);
    setIsThinking(true);

    // Context-aware tactical AI response generator
    setTimeout(() => {
      let aiText = '';
      const lowerQ = query.toLowerCase();

      if (lowerQ.includes('summary') || lowerQ.includes('incident') || lowerQ.includes('recent')) {
        aiText = `### 🛡️ RECENT INCIDENT SUMMARY\n\n**Total Scans Run:** ${jobHistory.length + 1}\n**Active Monitoring Zone:** ${selectedSource.location} (${selectedSource.id})\n\n- **Highest Probability Anomaly:** Breach Attempt (88.4% Confidence)\n- **Active Track Count:** 10 Objects Detected via YOLOv8\n- **Backend Pipeline Status:** ${apiHealth.connected ? 'ONLINE (FastAPI)' : 'SIMULATED LOCAL ENGINE'}\n\nAll logs are archived under the Audit Trail table.`;
      } else if (lowerQ.includes('dispatch') || lowerQ.includes('report') || lowerQ.includes('bravo')) {
        aiText = `### 🚨 TACTICAL DISPATCH REPORT\n\n**SEVERITY:** LEVEL BRAVO (FENCE INTRUSION)\n**LOCATION:** ${selectedSource.location}\n**TIMESTAMP:** ${new Date().toISOString()}\n\n\`\`\`json\n{\n  "dispatch_unit": "PATROL-DELTA-4",\n  "incident_type": "Perimeter Fence Breach / Climbing",\n  "confidence_score": 0.932,\n  "action_required": "Immediate On-Site Physical Intercept"\n}\n\`\`\`\n\nDispatch alert staged for operator sign-off.`;
      } else if (lowerQ.includes('yolo') || lowerQ.includes('track') || lowerQ.includes('bounding')) {
        aiText = `### 👁️ VISION & TRACKING ENGINE SPECS\n\n- **Detector:** YOLOv8 Enterprise Multi-Object Vision\n- **Track ID Persistence:** DeepSORT Kalman filter\n- **Active Tracks:** TRK-001 (Person, 12.4s), TRK-002 (Person, 9.1s), TRK-003 (Vehicle, 14.2s)\n\nBounding box overlays can be toggled on/off in the Analysis Workspace panel.`;
      } else if (lowerQ.includes('status') || lowerQ.includes('health') || lowerQ.includes('api')) {
        aiText = `### ⚙️ SYSTEM HEALTH DIAGNOSTICS\n\n- **Endpoint Base:** \`${backendUrl}\`\n- **API Health:** ${apiHealth.connected ? '🟢 CONNECTED (200 OK)' : '🟡 SIMULATED WORKER'}\n- **Inference Latency:** 23.4 ms\n- **Inference Engine:** Swin3D + ResNet50-I3D`;
      } else {
        aiText = `Understood, Operator. Analyzing telemetry for **${selectedSource.id}** (${selectedSource.location}).\n\nCurrent threat index is **MODERATE**. Neural action classifier reports **93.2% confidence** on spatial breach vectors. Would you like me to generate a full CISO audit report or dispatch security units?`;
      }

      const assistantMsg = {
        id: `msg-ai-${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        text: aiText,
        meta: { model: 'SENTINEL-LLM-3.5-TACTICAL', context: selectedSource.id }
      };

      setChatMessages(prev => [...prev, assistantMsg]);
      setIsThinking(false);
    }, 1200);
  };

  const handleDispatchAlert = async (responderId = 'PATROL-DELTA-4') => {
    const activeJobId = activeJob?.jobId || 'INC-MANUAL-DISPATCH';
    await apiClient.sendNotificationSMS(activeJobId, {
      unit: responderId,
      location: selectedSource.location,
      severity: 'CRITICAL',
      timestamp: new Date().toISOString()
    });

    showToast(`🚨 DISPATCH SENT: Unit ${responderId} mobilized to ${selectedSource.location}`);
    if (showMapModal) setShowMapModal(false);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    showToast('Copied payload to clipboard.');
  };

  return (
    <div className="min-h-screen bg-[#08090C] text-slate-200 flex flex-col font-sans antialiased selection:bg-blue-600">
      
      {/* GLOBAL TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="fixed top-16 right-4 z-50 bg-[#151822] border border-blue-500/80 px-4 py-2.5 rounded-sm shadow-2xl text-xs font-mono text-white flex items-center gap-2 animate-bounce">
          <Icons.CheckCircle className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* HEADER / NAVIGATION BAR */}
      <header className="h-14 bg-[#0D0E13] border-b border-[#1E2232] px-4 flex items-center justify-between shrink-0 z-40">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setView('landing')}
            className="flex items-center gap-2.5 text-left focus:outline-none group"
          >
            <div className="w-8 h-8 rounded-sm bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-all">
              <Icons.Shield className="w-4 h-4" />
            </div>
            <div>
              <div className="font-mono font-bold text-xs tracking-wider text-white flex items-center gap-2">
                <span>SENTINEL-X</span>
                <span className="text-[10px] text-blue-400 bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.2 rounded-sm font-normal">v2.4 COPILOT</span>
              </div>
              <div className="text-[10px] text-slate-400 font-mono">Tactical AI Vision &amp; Threat Terminal</div>
            </div>
          </button>

          <div className="h-4 w-[1px] bg-[#1E2232] hidden sm:block"></div>

          {/* View Navigation Tabs */}
          <nav className="hidden sm:flex items-center gap-1 text-xs font-mono">
            <button
              onClick={() => setView('landing')}
              className={`px-3 py-1.5 rounded-sm transition-colors ${
                view === 'landing' 
                  ? 'bg-[#151822] text-white font-semibold border border-[#2B3148]' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              LANDING
            </button>
            <button
              onClick={() => setView('analysis')}
              className={`px-3 py-1.5 rounded-sm transition-colors ${
                view === 'analysis' 
                  ? 'bg-[#151822] text-white font-semibold border border-[#2B3148]' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              ANALYSIS WORKSPACE
            </button>

            {/* DEDICATED CHATBOT COPILOT TAB */}
            <button
              onClick={() => setView('copilot')}
              className={`px-3 py-1.5 rounded-sm transition-colors flex items-center gap-1.5 ${
                view === 'copilot' 
                  ? 'bg-blue-600/20 text-blue-400 font-semibold border border-blue-500/50' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              <Icons.Bot className="w-3.5 h-3.5" />
              <span>AI COPILOT</span>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping"></span>
            </button>

            <button
              onClick={() => setView('logs')}
              className={`px-3 py-1.5 rounded-sm transition-colors ${
                view === 'logs' 
                  ? 'bg-[#151822] text-white font-semibold border border-[#2B3148]' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              AUDIT TRAIL ({jobHistory.length})
            </button>
          </nav>
        </div>

        {/* Right Action Bar */}
        <div className="flex items-center gap-3 font-mono text-xs">
          {/* Tactical Map Trigger Button */}
          <button
            onClick={() => setShowMapModal(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#151822] hover:bg-[#1B202E] border border-blue-500/40 text-blue-400 hover:text-white transition-colors"
            title="Open Tactical Map (CartoDB Voyager)"
          >
            <Icons.Map className="w-3.5 h-3.5" />
            <span className="hidden md:inline">MAP (VOYAGER)</span>
          </button>

          {/* API Status Badge */}
          <div 
            onClick={() => setShowSettingsModal(true)}
            className={`flex items-center gap-2 px-2.5 py-1 rounded-sm border cursor-pointer transition-all ${
              apiHealth.connected 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                : simulatedEngineMode 
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
            }`}
            title="Configure FastAPI Connection"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${
              apiHealth.connected ? 'bg-emerald-400 animate-pulse' : simulatedEngineMode ? 'bg-amber-400' : 'bg-rose-400'
            }`}></span>
            <span className="text-[11px] font-semibold tracking-wide">
              {apiHealth.checking ? 'PINGING...' : apiHealth.connected ? 'API CONNECTED' : simulatedEngineMode ? 'SIMULATED ENGINE' : 'API OFFLINE'}
            </span>
          </div>

          <button
            onClick={() => setShowSettingsModal(true)}
            className="p-1.5 text-slate-400 hover:text-white bg-[#151822] border border-[#232838] rounded-sm transition-colors"
            title="Open Settings"
          >
            <Icons.Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex flex-col overflow-hidden">
        
        {/* VIEW 1: LANDING HERO */}
        {view === 'landing' && (
          <div className="flex-1 flex flex-col justify-between p-6 lg:p-12 max-w-7xl mx-auto w-full bg-tech-grid">
            
            <div className="my-auto py-12 space-y-8 max-w-4xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-sm bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono">
                <Icons.Cpu className="w-3.5 h-3.5" />
                <span>TACTICAL THREAT INTELLIGENCE &amp; AI CHATBOT TERMINAL</span>
              </div>

              <div className="space-y-4">
                <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white font-sans leading-tight">
                  Enterprise Video Intelligence &amp; <span className="text-blue-400">AI Copilot</span>
                </h1>
                <p className="text-slate-400 text-sm sm:text-base leading-relaxed font-normal max-w-2xl">
                  Real-time video threat classification, YOLO object tracking, CartoDB geospatial mapping, and an integrated tactical SOC AI Chatbot assistant built for rapid incident response and log analysis.
                </p>
              </div>

              {/* Multi Mode Chooser Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                
                {/* Anomaly Card */}
                <div 
                  onClick={() => {
                    setAnalysisMode('anomaly');
                    setView('analysis');
                  }}
                  className="p-5 bg-[#0D0E13] border border-[#1E2232] hover:border-blue-500/80 rounded-sm cursor-pointer transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-sm bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
                      <Icons.Shield className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 bg-[#151822] px-1.5 py-0.5 rounded-sm border border-[#232838]">STAGE 1 &amp; 2</span>
                  </div>
                  <h3 className="text-sm font-bold text-white font-mono">ANOMALY ENGINE</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                    Detect security fence breaches and unauthorized access using Swin3D classifiers.
                  </p>
                </div>

                {/* Vision YOLO Card */}
                <div 
                  onClick={() => {
                    setAnalysisMode('vision_yolo');
                    setView('analysis');
                  }}
                  className="p-5 bg-[#0D0E13] border border-[#1E2232] hover:border-indigo-500/80 rounded-sm cursor-pointer transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-sm bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
                      <Icons.Crosshair className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 bg-[#151822] px-1.5 py-0.5 rounded-sm border border-[#232838]">YOLO DETECTOR</span>
                  </div>
                  <h3 className="text-sm font-bold text-white font-mono">VISION TRACKING</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                    Extract bounding box detections, counts, unique track IDs, and movement vectors.
                  </p>
                </div>

                {/* AI Chatbot Copilot Card */}
                <div 
                  onClick={() => setView('copilot')}
                  className="p-5 bg-[#0D0E13] border border-blue-500/40 hover:border-blue-400 rounded-sm cursor-pointer transition-all bg-gradient-to-br from-blue-950/20 to-transparent"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-sm bg-blue-500/20 border border-blue-400 text-blue-300 flex items-center justify-center">
                      <Icons.Bot className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-sm border border-blue-500/30">AI COPILOT</span>
                  </div>
                  <h3 className="text-sm font-bold text-white font-mono">AI CHATBOT TERMINAL</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                    Query live telemetry, generate threat reports, and query SOC protocols in natural language.
                  </p>
                </div>

              </div>

              {/* Primary CTA Buttons */}
              <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-[#1E2232]">
                <button
                  onClick={() => setView('copilot')}
                  className="px-6 py-2.5 rounded-sm bg-blue-600 hover:bg-blue-500 text-white font-mono font-semibold text-xs tracking-wider flex items-center gap-2 transition-all shadow-lg shadow-blue-600/20"
                >
                  <Icons.Bot className="w-4 h-4" />
                  <span>LAUNCH AI CHATBOT TERMINAL</span>
                </button>
                <button
                  onClick={() => setView('analysis')}
                  className="px-6 py-2.5 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-slate-200 font-mono text-xs border border-[#232838] transition-all"
                >
                  OPEN VIDEO WORKSPACE
                </button>
                <button
                  onClick={() => setShowMapModal(true)}
                  className="px-6 py-2.5 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-blue-400 font-mono text-xs border border-blue-500/40 flex items-center gap-2 transition-all"
                >
                  <Icons.Map className="w-4 h-4" />
                  <span>OPEN CARTODB VOYAGER MAP</span>
                </button>
              </div>
            </div>

            {/* Footer Specs Bar */}
            <div className="bg-[#0D0E13] border border-[#1E2232] p-3 rounded-sm flex flex-col sm:flex-row items-center justify-between gap-2 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-2">
                <Icons.Server className="w-4 h-4 text-blue-400" />
                <span>BACKEND API: <strong className="text-slate-200">{backendUrl}</strong></span>
              </div>
              <div className="flex items-center gap-2">
                <Icons.Map className="w-4 h-4 text-emerald-400" />
                <span>MAP TILES: <strong className="text-slate-200">CartoDB Voyager (Active)</strong></span>
              </div>
            </div>

          </div>
        )}

        {/* VIEW 2: AI COPILOT CHATBOT */}
        {view === 'copilot' && (
          <div className="flex-1 flex flex-col xl:flex-row overflow-hidden bg-[#08090C]">
            
            {/* MAIN CHAT THREAD */}
            <div className="flex-1 flex flex-col overflow-hidden border-r border-[#1E2232]">
              
              {/* Chat Terminal Header */}
              <div className="h-12 bg-[#0D0E13] border-b border-[#1E2232] px-4 flex items-center justify-between shrink-0 font-mono text-xs">
                <div className="flex items-center gap-2.5">
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></div>
                  <span className="font-bold text-white uppercase tracking-wider">SENTINEL-X TACTICAL AI COPILOT</span>
                  <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-sm border border-blue-500/20">
                    MODEL: SENTINEL-LLM-3.5
                  </span>
                </div>

                <div className="flex items-center gap-2 text-slate-400 text-[11px]">
                  <span>Context: <strong className="text-slate-200">{selectedSource.id}</strong></span>
                  <button 
                    onClick={() => setChatMessages(INITIAL_CHAT_MESSAGES)} 
                    className="p-1 hover:text-white bg-[#151822] rounded-sm border border-[#232838] ml-2"
                    title="Clear Conversation"
                  >
                    <Icons.RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Chat Messages Scroll Container */}
              <div className="flex-1 p-4 lg:p-6 overflow-y-auto space-y-4">
                {chatMessages.map((msg) => (
                  <div 
                    key={msg.id} 
                    className={`flex gap-3 max-w-3xl ${msg.sender === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
                  >
                    {/* Avatar */}
                    <div className={`w-7 h-7 rounded-sm flex items-center justify-center shrink-0 text-xs font-mono font-bold ${
                      msg.sender === 'user' 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                    }`}>
                      {msg.sender === 'user' ? <Icons.User className="w-3.5 h-3.5" /> : <Icons.Bot className="w-3.5 h-3.5" />}
                    </div>

                    {/* Content Box */}
                    <div className={`space-y-1 ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}>
                      <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                        <span className="font-bold text-slate-300">
                          {msg.sender === 'user' ? 'OPERATOR' : 'SENTINEL COPILOT'}
                        </span>
                        <span>{msg.timestamp}</span>
                        {msg.meta && (
                          <span className="bg-[#151822] px-1.5 py-0.2 rounded-sm border border-[#232838]">
                            {msg.meta.model}
                          </span>
                        )}
                      </div>

                      <div className={`p-3.5 rounded-sm border text-xs font-sans leading-relaxed ${
                        msg.sender === 'user'
                          ? 'bg-[#151822] border-blue-500/50 text-slate-100'
                          : 'bg-[#0D0E13] border-[#1E2232] text-slate-200'
                      }`}>
                        {msg.hasFrame && (
                          <div className="mb-2 p-2 bg-[#11131A] rounded-sm border border-[#232838] flex items-center gap-2 text-[10px] font-mono text-blue-400">
                            <Icons.Video className="w-3.5 h-3.5" />
                            <span>Attached Camera Frame: {selectedSource.id} ({selectedSource.resolution})</span>
                          </div>
                        )}

                        <div className="whitespace-pre-wrap font-sans">
                          {msg.text}
                        </div>

                        {/* Assistant Message Actions */}
                        {msg.sender === 'assistant' && (
                          <div className="mt-3 pt-2 border-t border-[#1E2232] flex items-center gap-2 font-mono text-[10px] text-slate-400">
                            <button 
                              onClick={() => copyToClipboard(msg.text)}
                              className="flex items-center gap-1 hover:text-white transition-colors"
                            >
                              <Icons.Copy className="w-3 h-3" />
                              <span>COPY</span>
                            </button>
                            <span className="text-[#232838]">•</span>
                            <button 
                              onClick={() => setView('analysis')}
                              className="flex items-center gap-1 hover:text-blue-400 transition-colors"
                            >
                              <Icons.Video className="w-3 h-3" />
                              <span>GOTO WORKSPACE</span>
                            </button>
                            <span className="text-[#232838]">•</span>
                            <button 
                              onClick={() => setShowMapModal(true)}
                              className="flex items-center gap-1 text-blue-400 hover:text-blue-300 transition-colors"
                            >
                              <Icons.Map className="w-3 h-3" />
                              <span>VIEW MAP</span>
                            </button>
                            <span className="text-[#232838]">•</span>
                            <button 
                              onClick={() => handleDispatchAlert('PATROL-DELTA-4')}
                              className="flex items-center gap-1 text-rose-400 hover:text-rose-300 transition-colors"
                            >
                              <Icons.Radio className="w-3 h-3" />
                              <span>DISPATCH PATROL</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Thinking Indicator */}
                {isThinking && (
                  <div className="flex gap-3 max-w-3xl">
                    <div className="w-7 h-7 rounded-sm bg-blue-500/10 border border-blue-500/30 text-blue-400 flex items-center justify-center text-xs shrink-0 font-mono">
                      <Icons.Bot className="w-3.5 h-3.5" />
                    </div>
                    <div className="p-3 bg-[#0D0E13] border border-[#1E2232] rounded-sm text-xs font-mono text-blue-400 flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-blue-400 animate-ping"></div>
                      <span>PROCESSING TELEMETRY &amp; QUERY...</span>
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Quick Tactical Suggestion Chips */}
              <div className="px-4 py-2 bg-[#0D0E13] border-t border-[#1E2232] flex items-center gap-2 overflow-x-auto text-[11px] font-mono shrink-0">
                <span className="text-slate-500 text-[10px] uppercase shrink-0">SUGGESTIONS:</span>
                <button 
                  onClick={() => handleSendMessage("Summarize current threat status and recent incident logs")}
                  className="px-2.5 py-1 bg-[#151822] hover:bg-[#1B202E] text-slate-300 hover:text-white border border-[#232838] rounded-sm shrink-0 transition-colors"
                >
                  🛡️ Incident Summary
                </button>
                <button 
                  onClick={() => handleSendMessage("Draft Level Bravo Security Dispatch Report")}
                  className="px-2.5 py-1 bg-[#151822] hover:bg-[#1B202E] text-slate-300 hover:text-white border border-[#232838] rounded-sm shrink-0 transition-colors"
                >
                  🚨 Level Bravo Dispatch
                </button>
                <button 
                  onClick={() => handleSendMessage("Explain YOLO track IDs and confidence scores")}
                  className="px-2.5 py-1 bg-[#151822] hover:bg-[#1B202E] text-slate-300 hover:text-white border border-[#232838] rounded-sm shrink-0 transition-colors"
                >
                  👁️ Explain YOLO Specs
                </button>
                <button 
                  onClick={() => handleSendMessage("Run system health and FastAPI connection diagnostics")}
                  className="px-2.5 py-1 bg-[#151822] hover:bg-[#1B202E] text-slate-300 hover:text-white border border-[#232838] rounded-sm shrink-0 transition-colors"
                >
                  ⚙️ API Diagnostics
                </button>
              </div>

              {/* Input Box Bar */}
              <div className="p-4 bg-[#0D0E13] border-t border-[#1E2232] shrink-0 space-y-2">
                {attachedFrame && (
                  <div className="flex items-center justify-between bg-[#151822] px-3 py-1.5 rounded-sm border border-blue-500/40 text-xs font-mono text-blue-400">
                    <span className="flex items-center gap-2">
                      <Icons.Video className="w-3.5 h-3.5" />
                      <span>Attached Frame: {selectedSource.id}</span>
                    </span>
                    <button onClick={() => setAttachedFrame(false)} className="text-slate-400 hover:text-white">
                      <Icons.X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setAttachedFrame(!attachedFrame)}
                    className={`p-2.5 rounded-sm border transition-colors ${
                      attachedFrame 
                        ? 'bg-blue-600 text-white border-blue-500' 
                        : 'bg-[#151822] text-slate-400 hover:text-white border-[#232838]'
                    }`}
                    title="Attach Active Camera Frame"
                  >
                    <Icons.Paperclip className="w-4 h-4" />
                  </button>

                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Type tactical query or /command (Press Enter to send)..."
                    className="flex-1 bg-[#151822] border border-[#232838] rounded-sm px-3.5 py-2.5 text-xs text-white font-mono placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
                  />

                  <button
                    onClick={() => handleSendMessage()}
                    disabled={isThinking}
                    className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-bold rounded-sm flex items-center gap-2 transition-all shadow-md shadow-blue-600/20"
                  >
                    <Icons.Send className="w-3.5 h-3.5" />
                    <span>SEND</span>
                  </button>
                </div>
              </div>

            </div>

            {/* RIGHT SIDEBAR: CONTEXT & TELEMETRY PANEL */}
            <div className="w-full xl:w-80 bg-[#0D0E13] p-4 flex flex-col gap-4 overflow-y-auto shrink-0 font-mono text-xs">
              
              <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                <h3 className="font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Icons.Layers className="w-4 h-4 text-blue-400" />
                  <span>LIVE TELEMETRY CONTEXT</span>
                </h3>
              </div>

              {/* Context 1: Active Video Source */}
              <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
                <div className="text-[10px] text-slate-400 uppercase">ACTIVE CAMERA FEED</div>
                <div className="font-bold text-white font-sans text-xs">{selectedSource.title}</div>
                <div className="text-[10px] text-blue-400 flex justify-between">
                  <span>{selectedSource.id}</span>
                  <span>{selectedSource.resolution}</span>
                </div>
              </div>

              {/* Context 2: Backend Pipeline */}
              <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-1.5">
                <div className="text-[10px] text-slate-400 uppercase">BACKEND MODEL CONTEXT</div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">API Status:</span>
                  <span className={apiHealth.connected ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                    {apiHealth.connected ? 'ONLINE' : 'SIMULATED'}
                  </span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-slate-400">Target Engine:</span>
                  <span className="text-blue-400 font-bold uppercase">{analysisMode}</span>
                </div>
              </div>

              {/* Tactical Map Shortcut */}
              <button
                onClick={() => setShowMapModal(true)}
                className="p-3 bg-[#11131A] hover:bg-[#151822] border border-blue-500/30 rounded-sm flex items-center justify-between text-slate-200 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Icons.Map className="w-4 h-4 text-blue-400" />
                  <span>CARTODB VOYAGER MAP</span>
                </div>
                <span className="text-[10px] text-blue-400">VIEW &gt;</span>
              </button>

              {/* Quick SOP References */}
              <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
                <div className="text-[10px] text-slate-400 uppercase">STANDARD OPERATING PROCEDURES (SOP)</div>
                <div className="space-y-1.5 text-[11px] text-slate-300">
                  <div className="p-2 bg-[#171A24] rounded-sm border border-[#232838]">
                    <strong className="text-rose-400 block mb-0.5">SOP-01: Anomaly Breach</strong>
                    Dispatch Sector Patrol &amp; lock facility gate boundaries immediately.
                  </div>
                  <div className="p-2 bg-[#171A24] rounded-sm border border-[#232838]">
                    <strong className="text-blue-400 block mb-0.5">SOP-02: Dense Crowd</strong>
                    Enable YOLO object counter and verify concourse capacity thresholds.
                  </div>
                </div>
              </div>

            </div>

          </div>
        )}

        {/* VIEW 3: ANALYSIS WORKSPACE */}
        {view === 'analysis' && (
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden bg-[#08090C]">
            
            {/* LEFT SIDEBAR: Source Feeds & Custom Upload */}
            <div className="w-full lg:w-72 bg-[#0D0E13] border-r border-[#1E2232] p-4 flex flex-col gap-4 shrink-0 overflow-y-auto">
              
              {/* System Switcher Header */}
              <div>
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block mb-2">
                  ANALYSIS ENGINE MODE
                </span>
                <div className="grid grid-cols-2 gap-1 bg-[#151822] p-1 rounded-sm border border-[#232838]">
                  <button
                    onClick={() => {
                      setAnalysisMode('anomaly');
                      setActiveJob(null);
                    }}
                    className={`py-1.5 px-2 rounded-sm text-[11px] font-mono transition-all ${
                      analysisMode === 'anomaly' 
                        ? 'bg-blue-600 text-white font-bold' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    ANOMALY
                  </button>
                  <button
                    onClick={() => {
                      setAnalysisMode('vision_yolo');
                      setActiveJob(null);
                    }}
                    className={`py-1.5 px-2 rounded-sm text-[11px] font-mono transition-all ${
                      analysisMode === 'vision_yolo' 
                        ? 'bg-blue-600 text-white font-bold' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    VISION / YOLO
                  </button>
                </div>
              </div>

              <div className="h-[1px] bg-[#1E2232]"></div>

              {/* Available Feeds */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
                  FEED SOURCES
                </span>

                {DEMO_VIDEO_SOURCES.map((source) => {
                  const isSelected = selectedSource.id === source.id && !customFile;
                  return (
                    <div
                      key={source.id}
                      onClick={() => handleSelectSource(source)}
                      className={`p-2.5 rounded-sm border cursor-pointer font-mono transition-all ${
                        isSelected 
                          ? 'bg-[#151822] border-blue-500/80 text-white' 
                          : 'bg-[#11131A] border-[#1E2232] hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between text-[10px] text-blue-400 font-bold">
                        <span>{source.id}</span>
                        <span className="text-emerald-400">{source.status}</span>
                      </div>
                      <div className="text-xs font-bold text-slate-100 mt-1 font-sans truncate">{source.title}</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">{source.resolution}</div>
                    </div>
                  );
                })}
              </div>

              {/* Custom Upload Dropzone */}
              <div className="space-y-2 pt-2">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
                  UPLOAD VIDEO FILE
                </span>
                <label className="border border-dashed border-[#232838] hover:border-blue-500 bg-[#11131A] hover:bg-[#151822] p-3 rounded-sm flex flex-col items-center justify-center cursor-pointer transition-all text-center">
                  <Icons.Upload className="w-4 h-4 text-blue-400 mb-1" />
                  <span className="text-xs font-mono font-medium text-slate-300">Select MP4 / AVI File</span>
                  <span className="text-[10px] text-slate-500 font-mono mt-0.5">POST /api/v1/analysis</span>
                  <input 
                    type="file" 
                    accept="video/*" 
                    onChange={handleFileUpload} 
                    className="hidden" 
                  />
                </label>
              </div>

            </div>

            {/* MAIN ANALYSIS CONTENT AREA */}
            <div className="flex-1 flex flex-col xl:flex-row overflow-hidden bg-[#08090C]">
              
              {/* 70% VIDEO & CONTROLS */}
              <div className="w-full xl:w-[70%] flex flex-col p-4 lg:p-6 overflow-y-auto border-r border-[#1E2232]">
                
                {/* Top Feed Info Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#1E2232]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold text-white font-mono uppercase">{selectedSource.title}</h2>
                      <span className="text-[10px] bg-[#151822] text-slate-300 font-mono px-1.5 py-0.5 rounded-sm border border-[#232838]">
                        {selectedSource.id}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      Location: {selectedSource.location} • Target Engine: <span className="text-blue-400">{analysisMode === 'anomaly' ? 'ANOMALY CLASSIFIER' : 'YOLO DETECTOR'}</span>
                    </p>
                  </div>

                  {/* Trigger Buttons */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowMapModal(true)}
                      className="px-3 py-2 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-blue-400 border border-blue-500/40 font-mono text-xs flex items-center gap-1.5 transition-colors"
                    >
                      <Icons.Map className="w-3.5 h-3.5" />
                      <span>GEOLOCATE (VOYAGER)</span>
                    </button>

                    <button
                      onClick={handleTriggerAnalysis}
                      disabled={activeJob && (activeJob.status === 'queued' || activeJob.status === 'processing')}
                      className={`px-4 py-2 rounded-sm font-mono font-semibold text-xs flex items-center gap-2 transition-all ${
                        activeJob && (activeJob.status === 'queued' || activeJob.status === 'processing')
                          ? 'bg-blue-600/40 text-blue-200 cursor-not-allowed'
                          : 'bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20'
                      }`}
                    >
                      <Icons.Zap className="w-4 h-4" />
                      <span>
                        {activeJob && (activeJob.status === 'queued' || activeJob.status === 'processing')
                          ? 'RUNNING INFERENCE...'
                          : 'RUN ANALYSIS'}
                      </span>
                    </button>
                  </div>
                </div>

                {/* YOLO Bounding Box Toggles */}
                {analysisMode === 'vision_yolo' && (
                  <div className="flex items-center gap-4 py-2 text-xs font-mono text-slate-400">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={toggleDetections} 
                        onChange={(e) => setToggleDetections(e.target.checked)} 
                        className="rounded-sm bg-[#11131A] border-[#232838] text-blue-600 focus:ring-0" 
                      />
                      <span>Show Bounding Boxes</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={toggleTracks} 
                        onChange={(e) => setToggleTracks(e.target.checked)} 
                        className="rounded-sm bg-[#11131A] border-[#232838] text-blue-600 focus:ring-0" 
                      />
                      <span>Show Track IDs</span>
                    </label>
                  </div>
                )}

                {/* VIDEO & CANVAS OVERLAY CONTAINER */}
                <div className="mt-2 relative rounded-sm overflow-hidden bg-black border border-[#1E2232] flex items-center justify-center min-h-[380px] lg:min-h-[480px]">
                  
                  <video
                    ref={videoRef}
                    key={videoPreviewUrl}
                    src={videoPreviewUrl}
                    controls
                    autoPlay
                    loop
                    muted
                    className="w-full h-full object-contain max-h-[580px]"
                  ></video>

                  {/* Canvas Overlay */}
                  <canvas 
                    ref={canvasRef} 
                    className="absolute inset-0 pointer-events-none z-10 w-full h-full"
                  />

                  {/* HUD Overlay Badge */}
                  <div className="absolute top-3 left-3 bg-black/80 px-2.5 py-1 rounded-sm text-[10px] font-mono text-emerald-400 border border-emerald-500/30 flex items-center gap-2 z-20">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>FEED ACTIVE // {selectedSource.id}</span>
                  </div>

                  {/* Loading / Inference Overlay */}
                  {activeJob && (activeJob.status === 'queued' || activeJob.status === 'processing') && (
                    <div className="absolute inset-0 bg-black/70 flex flex-col items-center justify-center text-center p-6 space-y-3 z-30">
                      <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                      <div className="text-white font-mono font-bold text-xs tracking-wider">
                        {activeJob.status === 'queued' ? 'JOB QUEUED IN PIPELINE' : 'NEURAL INFERENCE IN PROGRESS'}
                      </div>
                      <div className="text-[11px] font-mono text-blue-400 bg-blue-500/10 px-3 py-1 rounded-sm border border-blue-500/20">
                        JOB ID: {activeJob.jobId}
                      </div>
                    </div>
                  )}

                </div>

              </div>

              {/* 30% STRUCTURED INTELLIGENCE PANEL */}
              <div className="w-full xl:w-[30%] bg-[#0D0E13] p-4 lg:p-6 flex flex-col gap-4 overflow-y-auto font-mono text-xs shrink-0">
                
                <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                  <h3 className="font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <Icons.Layers className="w-4 h-4 text-blue-400" />
                    <span>INTELLIGENCE PANEL</span>
                  </h3>
                  <span className="text-[10px] text-slate-500">LIVE DATA</span>
                </div>

                {/* EMPTY STATE */}
                {!activeJob && (
                  <div className="my-auto py-12 flex flex-col items-center justify-center text-center space-y-2 text-slate-500">
                    <Icons.Activity className="w-8 h-8 text-slate-600 mb-1" />
                    <div className="font-bold text-slate-400">WAITING FOR ANALYSIS</div>
                    <p className="text-[11px] text-slate-500 max-w-xs font-sans">
                      Select a feed and click "RUN ANALYSIS" to start backend inference.
                    </p>
                  </div>
                )}

                {/* QUEUED / PROCESSING STATE */}
                {activeJob && (activeJob.status === 'queued' || activeJob.status === 'processing') && (
                  <div className="my-auto py-12 flex flex-col items-center justify-center text-center space-y-3">
                    <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                    <div className="font-bold text-blue-400 uppercase">
                      STATUS: {activeJob.status}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      Polling GET /api/v1/analysis/{activeJob.jobId}
                    </span>
                  </div>
                )}

                {/* ANOMALY RESULTS PANEL */}
                {activeJob && activeJob.status === 'completed' && activeJob.system === 'anomaly' && activeJob.result && (
                  <div className="space-y-4">
                    
                    <div className={`p-3 rounded-sm border ${
                      activeJob.result.anomaly_probability > 0.5 
                        ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' 
                        : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                    }`}>
                      <div className="text-[10px] uppercase text-slate-400">ANOMALY STATUS</div>
                      <div className="text-base font-bold uppercase mt-0.5">
                        {activeJob.result.anomaly_status || (activeJob.result.anomaly_probability > 0.5 ? 'DETECTED' : 'CLEAR')}
                      </div>
                    </div>

                    <div className="space-y-2 bg-[#11131A] p-3 rounded-sm border border-[#1E2232]">
                      <div>
                        <span className="text-[10px] text-slate-400 uppercase block">ANOMALY PROBABILITY</span>
                        <span className="text-xl font-bold text-white">
                          {(activeJob.result.anomaly_probability * 100).toFixed(1)}%
                        </span>
                      </div>

                      <div>
                        <span className="text-[10px] text-slate-400 uppercase block">LIKELY ACTION</span>
                        <span className="text-xs font-bold text-blue-400 font-sans block">
                          {activeJob.result.likely_action}
                        </span>
                      </div>

                      <div>
                        <span className="text-[10px] text-slate-400 uppercase block">ACTION CONFIDENCE</span>
                        <span className="text-xs font-bold text-emerald-400">
                          {(activeJob.result.action_confidence * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    {activeJob.result.alternative_candidates && (
                      <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
                        <span className="text-[10px] text-slate-400 uppercase block">ACTION CANDIDATES</span>
                        <div className="space-y-2">
                          {activeJob.result.alternative_candidates.map((cand, idx) => (
                            <div key={idx} className="space-y-1 text-[11px]">
                              <div className="flex items-center justify-between font-sans">
                                <span className="text-slate-300 truncate max-w-[170px]">{cand.action}</span>
                                <span className="font-mono text-slate-400">{(cand.confidence * 100).toFixed(1)}%</span>
                              </div>
                              <div className="w-full bg-[#1B1F2C] h-1 rounded-sm overflow-hidden">
                                <div 
                                  className="bg-blue-500 h-full" 
                                  style={{ width: `${cand.confidence * 100}%` }}
                                ></div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {activeJob.result.model_info && (
                      <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-1 text-[10px] text-slate-400">
                        <span className="text-[10px] text-slate-500 uppercase block mb-1">MODEL ARCHITECTURE</span>
                        <div>Stage 1: <strong className="text-slate-200">{activeJob.result.model_info.stage1_name}</strong></div>
                        <div>Stage 2: <strong className="text-slate-200">{activeJob.result.model_info.stage2_name}</strong></div>
                        <div>Backbone: <strong className="text-slate-200">{activeJob.result.model_info.i3d_backbone}</strong></div>
                      </div>
                    )}

                    {/* Quick Dispatch Action Button */}
                    <button
                      onClick={() => handleDispatchAlert('PATROL-DELTA-4')}
                      className="w-full py-2 bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/40 text-rose-300 rounded-sm font-bold flex items-center justify-center gap-2 transition-colors"
                    >
                      <Icons.Radio className="w-3.5 h-3.5" />
                      <span>DISPATCH INTERCEPT PATROL</span>
                    </button>

                  </div>
                )}

                {/* VISION YOLO RESULT PANEL */}
                {activeJob && activeJob.status === 'completed' && activeJob.system === 'vision_yolo' && activeJob.result && (
                  <div className="space-y-4">
                    
                    {activeJob.result.object_summary && (
                      <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
                        <span className="text-[10px] text-slate-400 uppercase block">OBJECT SUMMARY</span>
                        <div className="grid grid-cols-2 gap-2 text-center">
                          <div className="bg-[#171A24] p-2 rounded-sm border border-[#232838]">
                            <div className="text-[10px] text-slate-400">PEOPLE</div>
                            <div className="text-lg font-bold text-blue-400">{activeJob.result.object_summary.people_count}</div>
                          </div>
                          <div className="bg-[#171A24] p-2 rounded-sm border border-[#232838]">
                            <div className="text-[10px] text-slate-400">VEHICLES</div>
                            <div className="text-lg font-bold text-indigo-400">{activeJob.result.object_summary.vehicles_count}</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {activeJob.result.detections && (
                      <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
                        <span className="text-[10px] text-slate-400 uppercase block">DETECTIONS ({activeJob.result.detections.length})</span>
                        <div className="space-y-1 max-h-36 overflow-y-auto text-[11px]">
                          {activeJob.result.detections.map((det, idx) => (
                            <div key={idx} className="flex items-center justify-between bg-[#171A24] p-1.5 rounded-sm">
                              <span className="font-bold text-white uppercase">{det.class_name}</span>
                              <span className="text-blue-400">{(det.confidence * 100).toFixed(0)}%</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {activeJob.result.tracks && (
                      <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
                        <span className="text-[10px] text-slate-400 uppercase block">ACTIVE TRACKS ({activeJob.result.tracks.length})</span>
                        <div className="space-y-1.5 text-[10px]">
                          {activeJob.result.tracks.map((trk, idx) => (
                            <div key={idx} className="p-1.5 bg-[#171A24] rounded-sm border border-[#232838] flex justify-between">
                              <span className="text-blue-400 font-bold">{trk.track_id} ({trk.class_name})</span>
                              <span className="text-slate-400">{trk.duration_sec}s • {trk.direction}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                  </div>
                )}

              </div>

            </div>

          </div>
        )}

        {/* VIEW 4: AUDIT TRAIL LOGS */}
        {view === 'logs' && (
          <div className="flex-1 p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6 overflow-y-auto font-mono">
            <div className="flex items-center justify-between pb-4 border-b border-[#1E2232]">
              <div>
                <h1 className="text-lg font-bold text-white uppercase">Incident &amp; Analysis Audit Logs</h1>
                <p className="text-xs text-slate-400 mt-0.5">Historical inference records captured during session.</p>
              </div>
              <span className="text-xs text-slate-400 bg-[#151822] px-3 py-1 rounded-sm border border-[#232838]">
                TOTAL LOGS: {jobHistory.length}
              </span>
            </div>

            <div className="bg-[#0D0E13] border border-[#1E2232] rounded-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-[#151822] border-b border-[#1E2232] text-slate-400 text-[10px] uppercase">
                      <th className="p-3">Job ID</th>
                      <th className="p-3">System Mode</th>
                      <th className="p-3">Primary Action / Result</th>
                      <th className="p-3">Score / Confidence</th>
                      <th className="p-3">Duration</th>
                      <th className="p-3">Timestamp</th>
                      <th className="p-3 text-right">Raw JSON</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E2232] text-slate-300">
                    {jobHistory.length === 0 ? (
                      <tr>
                        <td colSpan="7" className="p-8 text-center text-slate-500 font-mono">
                          No completed analysis jobs recorded yet.
                        </td>
                      </tr>
                    ) : (
                      jobHistory.map((item, idx) => (
                        <tr key={idx} className="hover:bg-[#11131A]">
                          <td className="p-3 text-blue-400 font-bold">{item.job_id}</td>
                          <td className="p-3 uppercase text-slate-400">{item.system_type}</td>
                          <td className="p-3 font-sans text-white">{item.likely_action || item.anomaly_status || 'YOLO Object Sweep'}</td>
                          <td className="p-3 text-emerald-400">
                            {item.anomaly_probability 
                              ? `${(item.anomaly_probability * 100).toFixed(1)}%` 
                              : item.object_summary ? `${item.object_summary.unique_tracks} Tracks` : 'N/A'}
                          </td>
                          <td className="p-3 text-slate-400">{item.processing_time_seconds || item.performance?.processing_time_seconds}s</td>
                          <td className="p-3 text-slate-500 text-[10px]">{item.timestamp || 'Just now'}</td>
                          <td className="p-3 text-right">
                            <button
                              onClick={() => setSelectedLogItem(item)}
                              className="px-2 py-1 bg-[#1A1F2C] hover:bg-blue-600 hover:text-white rounded-sm text-[10px] transition-colors"
                            >
                              Inspect JSON
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

      </main>

      {/* TACTICAL GEOGRAPHIC LEAFLET MAP MODAL WITH CARTO VOYAGER API */}
      {showMapModal && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-4xl w-full h-[80vh] flex flex-col font-mono text-xs shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232] shrink-0">
              <div className="flex items-center gap-2">
                <Icons.Map className="w-4 h-4 text-blue-400" />
                <span className="font-bold text-white uppercase">TACTICAL GEOGRAPHIC MAP // CARTO VOYAGER</span>
                <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-sm border border-blue-500/20">
                  RASTER API ACTIVE
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleDispatchAlert(selectedResponder?.id || 'PATROL-DELTA-4')}
                  className="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-sm font-bold flex items-center gap-1.5 transition-colors"
                >
                  <Icons.Radio className="w-3.5 h-3.5" />
                  <span>DISPATCH UNIT</span>
                </button>
                <button onClick={() => setShowMapModal(false)} className="text-slate-400 hover:text-white">
                  <Icons.X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 relative bg-black">
              <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />
              
              <div className="absolute bottom-3 left-3 bg-[#0D0E13]/90 border border-[#232838] p-2.5 rounded-sm z-[500] text-[10px] space-y-1">
                <div className="text-white font-bold">LEGEND:</div>
                <div className="flex items-center gap-1.5 text-blue-400">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  <span>Active Camera Position: {selectedSource.id}</span>
                </div>
                <div className="flex items-center gap-1.5 text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span>Patrol Units (Active)</span>
                </div>
                <div className="flex items-center gap-1.5 text-amber-400">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                  <span>Stationary Units</span>
                </div>
              </div>

              <div className="absolute top-3 right-3 bg-[#0D0E13]/90 border border-[#232838] px-2.5 py-1 rounded-sm z-[500] text-[10px] text-slate-300">
                <span>API: <strong className="text-blue-400 font-mono">CartoDB Voyager Raster</strong></span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SETTINGS MODAL */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-md w-full p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[#1E2232]">
              <h3 className="font-bold text-white uppercase flex items-center gap-2">
                <Icons.Settings className="w-4 h-4 text-blue-400" />
                <span>BACKEND API SETTINGS</span>
              </h3>
              <button onClick={() => setShowSettingsModal(false)} className="text-slate-400 hover:text-white">
                <Icons.X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-slate-400 block mb-1">FastAPI Backend Base URL</label>
                <input
                  type="text"
                  value={backendUrl}
                  onChange={(e) => setBackendUrl(e.target.value)}
                  placeholder="http://localhost:8000"
                  className="w-full bg-[#151822] border border-[#232838] rounded-sm px-3 py-2 text-white focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="p-3 rounded-sm bg-[#11131A] border border-[#1E2232] space-y-1 text-[11px]">
                <div>Health Endpoint: <span className="text-slate-400">{backendUrl}/api/health</span></div>
                <div>Status: <span className={apiHealth.connected ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{apiHealth.connected ? 'ONLINE' : 'OFFLINE'}</span></div>
              </div>

              <label className="flex items-center gap-2 text-slate-300 cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={simulatedEngineMode}
                  onChange={(e) => setSimulatedEngineMode(e.target.checked)}
                  className="rounded-sm border-[#232838] bg-[#151822] text-blue-600"
                />
                <span>Enable Simulated Offline Inference Worker</span>
              </label>
            </div>

            <div className="pt-2 flex justify-end gap-2">
              <button
                onClick={() => {
                  checkBackendHealth();
                  setShowSettingsModal(false);
                  showToast('Saved API configuration.');
                }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-sm"
              >
                Save &amp; Ping API
              </button>
            </div>
          </div>
        </div>
      )}

      {/* LOG JSON INSPECTOR MODAL */}
      {selectedLogItem && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-2xl w-full p-6 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[#1E2232]">
              <h3 className="font-bold text-white uppercase">
                RAW PAYLOAD // {selectedLogItem.job_id}
              </h3>
              <button onClick={() => setSelectedLogItem(null)} className="text-slate-400 hover:text-white">
                <Icons.X className="w-4 h-4" />
              </button>
            </div>

            <pre className="bg-[#08090C] p-4 rounded-sm border border-[#1E2232] text-emerald-400 overflow-x-auto max-h-96">
              {JSON.stringify(selectedLogItem, null, 2)}
            </pre>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => copyToClipboard(JSON.stringify(selectedLogItem, null, 2))}
                className="px-4 py-1.5 bg-[#151822] hover:bg-[#1F2434] text-white rounded-sm flex items-center gap-1.5"
              >
                <Icons.Copy className="w-3.5 h-3.5" />
                <span>Copy JSON</span>
              </button>
              <button
                onClick={() => setSelectedLogItem(null)}
                className="px-4 py-1.5 bg-[#151822] hover:bg-[#1F2434] text-white rounded-sm"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

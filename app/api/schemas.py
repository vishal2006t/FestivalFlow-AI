"""Pydantic schemas for FestivalFlow AI API endpoints.
Compatible with Pydantic v1.10.26.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator


class HealthResponse(BaseModel):
    status: str = "OK"
    version: str = "1.0.0"
    service: str = "FestivalFlow AI"


class AppInfoResponse(BaseModel):
    name: str = "FestivalFlow AI"
    description: str = "Predictive Festival Crowd and Proactive Bus Reallocation System"
    version: str = "1.0.0"
    status: str = "Operational"
    problem_statement: str = "40k people leaving festival in 2h; 12 scheduled buses at Main Stand vs 4 idle buses 2km away."
    fleet_constraint: str = "Strictly fixed fleet. Zero synthetic buses generated."
    endpoints: List[str]


class StopSchema(BaseModel):
    stop_id: str
    name: str
    is_festival_hub: bool
    distance_from_festival_km: float
    current_scheduled_buses: int
    idle_buses: int
    min_service_buses: int
    capacity_per_bus: int
    status: str


class WeatherForecastSchema(BaseModel):
    condition: str = Field(default="Clear", description="Clear, Light Rain, Heavy Rain")
    rain_probability_pct: Optional[int] = 10
    temperature_celsius: Optional[float] = 26.0
    status: Optional[str] = "DEMO_ASSUMPTION"


class FestivalInfoSchema(BaseModel):
    event_name: Optional[str] = None
    date: Optional[str] = None
    start_time: Optional[str] = None
    headline_end_time: Optional[str] = None
    curfew_time: Optional[str] = None
    expected_exit_crowd: Optional[int] = None
    exit_window_hours: Optional[float] = None
    weather_forecast: Optional[WeatherForecastSchema] = None


class NetworkSchema(BaseModel):
    fleet_constraint: Optional[str] = "STRICTLY_FIXED_FLEET"
    total_network_buses: Optional[int] = None
    travel_time_between_stops_mins: Optional[int] = None
    distance_km: Optional[float] = None
    standard_bus_capacity: Optional[int] = None
    bus_cycle_turnaround_mins: Optional[int] = None


class ScenarioRequest(BaseModel):
    festival: Optional[FestivalInfoSchema] = None
    network: Optional[NetworkSchema] = None
    stops: Optional[List[StopSchema]] = None
    intervals: Optional[List[str]] = None
    baseline_demand_matrix: Optional[Dict[str, List[int]]] = None


class DemandResponse(BaseModel):
    model_type: str
    is_ml_model: bool
    future_upgrade_path: str
    intervals: List[str]
    predictions: Dict[str, List[int]]
    confidence_intervals: Dict[str, List[Dict[str, int]]]
    explanation: Dict[str, Any]


class SourceImpactSchema(BaseModel):
    initial_total_buses: int
    remaining_buses: int
    min_service_threshold: int
    service_retained_pct: float
    headway_change: str
    explanation: str


class BusReallocationSchema(BaseModel):
    reallocation_id: str
    source_stop_id: str
    source_stop_name: str
    destination_stop_id: str
    destination_stop_name: str
    buses_moved: int
    distance_km: float
    transit_time_mins: int
    recommended_departure_time: str
    expected_arrival_time: str
    status: str
    rationale: str
    source_impact: SourceImpactSchema


class OptimizeResponse(BaseModel):
    status: str
    fleet_conservation: Dict[str, Any]
    reallocations: List[BusReallocationSchema]
    before_and_after_comparison: Dict[str, Any]
    warnings: List[str]
    summary: str


# ==================== Authentication Schemas ====================

class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    role: str = Field(default="depot_admin", description="'depot_admin' or 'driver'")


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    full_name: str
    depot_name: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    expires_at: str


# ==================== Bus Schedule Schemas ====================

VALID_SCHEDULE_STATUSES = ["Scheduled", "Ready", "Accepted", "En Route", "Arrived", "Boarding", "Departed", "Completed", "Cancelled"]
VALID_DRIVER_STATUSES = ["Ready", "Accepted", "En Route", "Arrived", "Boarding", "Departed", "Completed"]


class ScheduleCreate(BaseModel):
    event_name: str = Field(..., min_length=2, description="Festival or event name")
    event_date: str = Field(..., description="Event date (YYYY-MM-DD)")
    event_start_time: str = Field(..., description="Event start time (HH:MM)")
    expected_crowd_departure: str = Field(..., description="Expected crowd exit date and time")
    depot_name: str = Field(..., min_length=2, description="Depot name")
    bus_number: str = Field(..., min_length=2, description="Bus number or identifier")
    bus_registration_no: Optional[str] = Field(None, description="Bus registration number if available")
    bus_capacity: Optional[int] = Field(70, ge=1, le=250, description="Bus passenger capacity")
    available_bus_count: Optional[int] = Field(1, ge=1, le=17, description="Number of available buses at depot")
    source_stop: str = Field(..., min_length=2, description="Origin stop or depot")
    destination_stop: str = Field(..., min_length=2, description="Destination stop")
    departure_time: str = Field(..., description="Departure date and time (ISO format)")
    arrival_time: Optional[str] = Field(None, description="Arrival date and time if known")
    driver_id: Optional[int] = Field(None, description="Assigned driver user ID")
    driver_name: Optional[str] = Field(None, description="Assigned driver name")
    route_details: str = Field(..., min_length=2, description="Route details and transit corridor")
    status: Optional[str] = Field("Scheduled", description="Schedule status")
    notes: Optional[str] = Field(None, description="Operational notes or depot instructions")

    @validator("status")
    def validate_status(cls, v):
        if v and v not in VALID_SCHEDULE_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(VALID_SCHEDULE_STATUSES)}")
        return v or "Scheduled"


class ScheduleUpdate(BaseModel):
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    event_start_time: Optional[str] = None
    expected_crowd_departure: Optional[str] = None
    depot_name: Optional[str] = None
    bus_number: Optional[str] = None
    bus_registration_no: Optional[str] = None
    bus_capacity: Optional[int] = None
    available_bus_count: Optional[int] = None
    source_stop: Optional[str] = None
    destination_stop: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    driver_id: Optional[int] = None
    driver_name: Optional[str] = None
    route_details: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

    @validator("status")
    def validate_status(cls, v):
        if v and v not in VALID_SCHEDULE_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(VALID_SCHEDULE_STATUSES)}")
        return v


class ScheduleResponse(BaseModel):
    id: int
    event_name: str
    event_date: str
    event_start_time: str
    expected_crowd_departure: str
    depot_name: str
    bus_number: str
    bus_registration_no: Optional[str]
    bus_capacity: int
    available_bus_count: int
    source_stop: str
    destination_stop: str
    departure_time: str
    arrival_time: Optional[str]
    driver_id: Optional[int]
    driver_name: Optional[str]
    route_details: str
    status: str
    notes: Optional[str]
    created_at: str
    updated_at: str


class StatusUpdate(BaseModel):
    status: str = Field(..., description="Schedule status")

    @validator("status")
    def validate_status(cls, v):
        if v not in VALID_SCHEDULE_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(VALID_SCHEDULE_STATUSES)}")
        return v


class DriverStatusUpdate(BaseModel):
    status: str = Field(..., description="Driver operational status (Ready, Departed, Completed)")

    @validator("status")
    def validate_driver_status(cls, v):
        if v not in VALID_DRIVER_STATUSES:
            raise ValueError(f"Drivers may only set status to one of: {', '.join(VALID_DRIVER_STATUSES)}")
        return v


# ==================== Depot & Resource Schemas ====================

class BusItem(BaseModel):
    id: int
    bus_number: str
    registration_no: Optional[str]
    depot_name: str
    capacity: int
    status: str


class DriverItem(BaseModel):
    id: int
    user_id: int
    driver_name: str
    license_no: Optional[str]
    phone: Optional[str]
    depot_name: str
    username: str


class DepotItem(BaseModel):
    id: int
    depot_name: str
    total_buses: int
    idle_buses: int
    min_service_buses: int


# ==================== Camera Monitoring & Crowd Vision Schemas ====================

class CameraConfigResponse(BaseModel):
    id: int
    camera_id: str
    stop_id: str
    name: str
    source_type: str
    stream_url: Optional[str]
    is_active: int
    roi_x1: float
    roi_y1: float
    roi_x2: float
    roi_y2: float
    status: str
    last_frame_time: Optional[str]
    created_at: str


class CameraConfigUpdateRequest(BaseModel):
    source_type: Optional[str] = Field(None, description="'rtsp', 'video_upload', 'webcam', 'demo'")
    stream_url: Optional[str] = None
    is_active: Optional[int] = None
    roi_x1: Optional[float] = None
    roi_y1: Optional[float] = None
    roi_x2: Optional[float] = None
    roi_y2: Optional[float] = None
    status: Optional[str] = None


class FrameDetectionRequest(BaseModel):
    source_type: Optional[str] = "demo"
    stream_url: Optional[str] = None
    roi: Optional[List[float]] = None
    target_time: Optional[str] = None


class CrowdReadingResponse(BaseModel):
    camera_id: str
    stop_id: str
    status: str
    provenance: str
    is_real_feed: bool
    stream_url: str
    timestamp: str
    people_count_raw: int
    people_count_smoothed: int
    crowd_level: str
    crowd_level_description: str
    trend: str
    confidence_pct: float
    roi: Dict[str, Any]
    temporal_smoothing: Dict[str, Any]
    privacy_compliance: Dict[str, str]
    detection_samples: List[Dict[str, Any]]
    is_night_time: bool
    night_safety_alert: bool


# ==================== Bus Telematics & Occupancy Schemas ====================

class BusTelematicsResponse(BaseModel):
    id: int
    bus_number: str
    registration_no: Optional[str]
    depot_name: str
    assigned_route: str
    destination_stop: str
    status: str
    passenger_count: int
    capacity: int
    available_seats: int
    occupancy_rate: float
    occupancy_source: str
    current_location: str
    distance_to_hub_km: float
    eta_mins: int
    eta_source: str
    last_update: str


class BusTelematicsUpdateRequest(BaseModel):
    status: Optional[str] = None
    passenger_count: Optional[int] = None
    capacity: Optional[int] = None
    occupancy_source: Optional[str] = None
    current_location: Optional[str] = None
    distance_to_hub_km: Optional[float] = None
    eta_mins: Optional[int] = None
    eta_source: Optional[str] = None


# ==================== Smart Dispatch & Route Matching Schemas ====================

class SmartDispatchRequest(BaseModel):
    target_stop_id: str = "STOP_MAIN"
    crowd_count: Optional[int] = None
    crowd_trend: Optional[str] = None
    is_night_time: Optional[bool] = None


class CandidateBusItem(BaseModel):
    bus_number: str
    registration_no: Optional[str]
    depot_name: str
    assigned_route: str
    destination_stop: str
    status: str
    passenger_count: int
    capacity: int
    available_seats: int
    occupancy_rate: float
    occupancy_source: str
    distance_to_hub_km: float
    eta_mins: int
    eta_source: str
    feasibility_score: float


class SmartDispatchResponse(BaseModel):
    status: str
    target_stop_id: str
    target_stop_name: str
    crowd_count: int
    crowd_trend: str
    top_candidate: Optional[CandidateBusItem]
    recommendation_summary: str
    source_impact: Optional[Dict[str, Any]]
    candidate_options: List[CandidateBusItem]
    rejected_options: List[Dict[str, Any]]
    action_required: str
    fleet_constraint: str
    timestamp: str


# ==================== Alerts & Night Safety Schemas ====================

class AlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    stop_id: str
    stop_name: str
    message: str
    crowd_count: int
    waiting_time_mins: int
    is_night_time: int
    recommended_bus_number: Optional[str]
    recommended_action: Optional[str]
    source_impact_summary: Optional[str]
    status: str
    notified_driver_id: Optional[int]
    created_at: str


class AlertAcknowledgeRequest(BaseModel):
    status: str = "ACKNOWLEDGED"  # 'ACKNOWLEDGED' or 'DISMISSED'


class NotifyDriverRequest(BaseModel):
    driver_id: int
    custom_message: Optional[str] = None


class DriverNotificationResponse(BaseModel):
    id: int
    driver_id: int
    driver_name: str
    bus_number: str
    stop_name: str
    notification_type: str
    title: str
    message: str
    severity: str
    is_read: int
    created_at: str


# ==================== Driver Incident / Delay Report Schemas ====================

VALID_REPORT_TYPES = ["DELAY", "BREAKDOWN", "OVERCROWDING", "SAFETY_CONCERN"]
VALID_REPORT_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

class DriverReportCreate(BaseModel):
    bus_number: str = Field(..., min_length=2, description="Assigned bus identifier")
    schedule_id: Optional[int] = Field(None, description="Optional linked schedule ID")
    report_type: str = Field(..., description="Report category (DELAY, BREAKDOWN, OVERCROWDING, SAFETY_CONCERN)")
    severity: Optional[str] = Field("MEDIUM", description="Severity level")
    stop_name: Optional[str] = Field(None, description="Current or affected stop location")
    description: str = Field(..., min_length=5, description="Detailed explanation of incident or delay")

    @validator("report_type")
    def validate_type(cls, v):
        if v.upper() not in VALID_REPORT_TYPES:
            raise ValueError(f"Report type must be one of: {', '.join(VALID_REPORT_TYPES)}")
        return v.upper()

    @validator("severity")
    def validate_severity(cls, v):
        if v.upper() not in VALID_REPORT_SEVERITIES:
            raise ValueError(f"Severity must be one of: {', '.join(VALID_REPORT_SEVERITIES)}")
        return v.upper()


class DriverReportStatusUpdate(BaseModel):
    status: str = Field(..., description="Status (REPORTED, IN_REVIEW, RESOLVED)")
    admin_response: Optional[str] = Field(None, description="Depot Admin response or mitigation action")


class DriverReportResponse(BaseModel):
    id: int
    driver_id: int
    driver_name: str
    bus_number: str
    schedule_id: Optional[int]
    report_type: str
    severity: str
    stop_name: Optional[str]
    description: str
    status: str
    admin_response: Optional[str]
    created_at: str


# ==================== Security Audit Log Schemas ====================

class AuditLogResponse(BaseModel):
    id: int
    timestamp: str
    event_type: str
    actor_username: str
    actor_role: str
    ip_address: Optional[str]
    action_details: str
    status: str


# ==================== Multi-Bus Dispatch Plan Schemas ====================

class DispatchPlanCreateRequest(BaseModel):
    target_stop_id: str = Field(..., description="Congested hub stop ID")
    target_stop_name: Optional[str] = Field(None, description="Congested hub stop name")
    crowd_count: int = Field(..., ge=1, description="Estimated waiting passenger crowd")
    buses_requested: Optional[int] = Field(4, ge=1, le=8, description="Number of buses required to redistribute")


class DispatchPlanResponse(BaseModel):
    id: int
    target_stop_id: str
    target_stop_name: str
    crowd_count: int
    buses_requested: int
    buses_allocated: int
    status: str
    candidate_buses: List[Dict[str, Any]]
    source_impact_summary: Optional[str]
    unmet_demand_reason: Optional[str]
    approved_by: Optional[str]
    rejection_reason: Optional[str]
    created_at: str
    resolved_at: Optional[str]


class DispatchPlanApproveResponse(BaseModel):
    status: str
    plan_id: int
    buses_assigned: int
    assignments: List[Dict[str, Any]]
    approved_by: str
    resolved_at: str


class DispatchPlanRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Reason for rejection")


class AlertEscalateRequest(BaseModel):
    escalation_action: str = Field(..., min_length=3, description="Escalation protocol action taken")
    notes: Optional[str] = Field(None, description="Operational notes or dispatch coordination details")
    requested_mutual_aid: Optional[bool] = Field(False, description="Whether regional mutual-aid fleet was requested")


# ==================== Network Data Models ====================

class StopItem(BaseModel):
    id: int
    stop_id: str
    stop_name: str
    location_lat: float
    location_lon: float
    capacity: int
    zone: str
    is_hub: int
    created_at: str


class RouteItem(BaseModel):
    id: int
    route_id: str
    route_name: str
    origin_stop: str
    destination_stop: str
    typical_headway_mins: int
    distance_km: float
    is_active: int


class StopUpdateRequest(BaseModel):
    capacity: Optional[int] = Field(None, ge=10, le=50000, description="Transit stop capacity")
    zone: Optional[str] = Field(None, description="Operational transit zone")


class RouteUpdateRequest(BaseModel):
    typical_headway_mins: Optional[int] = Field(None, ge=1, le=120, description="Typical headway in minutes")
    distance_km: Optional[float] = Field(None, ge=0.1, le=200.0, description="Route transit distance in kilometers")



class EventItem(BaseModel):
    id: int
    event_name: str
    event_date: str
    start_time: str
    end_time: str
    expected_attendees: int
    hub_stop_id: str
    status: str
    created_at: str


# ==================== Live Recalculation (Constraint-1) Schemas ====================

class LiveEventUpdateRequest(BaseModel):
    end_time: Optional[str] = Field(None, description="Updated event end time, e.g. '21:30' or '9:30 PM'")
    start_time: Optional[str] = Field(None, description="Event start time")
    delay_mins: Optional[int] = Field(None, ge=1, le=360, description="Additional delay in minutes (e.g. 30)")
    reason: Optional[str] = Field(None, description="Custom reason message for recalculation")


class LiveWeatherUpdateRequest(BaseModel):
    weather_condition: str = Field(..., description="Condition: 'Clear', 'Light Rain', 'Heavy Rain'")
    weather_source: Optional[str] = Field("ADMIN_MANUAL_OVERRIDE", description="OPEN_METEO_API, ADMIN_MANUAL_OVERRIDE, DEMO_SIMULATION")
    temperature_celsius: Optional[float] = Field(None, description="Optional temperature in Celsius")
    precipitation_probability: Optional[int] = Field(None, ge=0, le=100, description="Rain probability percentage")
    reason: Optional[str] = Field(None, description="Custom reason message for recalculation")


class LiveCrowdUpdateRequest(BaseModel):
    crowd_estimate: int = Field(..., ge=100, le=200000, description="Total expected crowd or stop count")
    crowd_source: Optional[str] = Field("CAMERA_ANALYSIS", description="Source of crowd reading")
    stop_id: Optional[str] = Field("STOP_MAIN", description="Stop identifier")
    reason: Optional[str] = Field(None, description="Reason for recalculation")


class LiveBusUpdateRequest(BaseModel):
    bus_number: str = Field(..., description="Bus registration/identifier")
    status: str = Field(..., description="Available, En Route, Full, Out of Service, Breakdown")
    reason: Optional[str] = Field(None, description="Reason for status change")


# ==================== AI, Database & Weather Schemas ====================

class AIStatusResponse(BaseModel):
    provider: str
    configured: bool
    model: str
    status: str
    note: str


class AIExplainRequest(BaseModel):
    context_type: str = Field("recommendation", description="'recommendation', 'scenario_change', or 'unmet_demand'")
    custom_prompt: Optional[str] = Field(None, description="Optional focus area for the explanation")


class AIExplainResponse(BaseModel):
    source: str
    model: str
    explanation: str
    buses_moved: Optional[int] = None
    departure_time: Optional[str] = None


class DatabaseStatusResponse(BaseModel):
    primary_database: str
    sqlite_path: str
    sqlite_status: str
    sqlite_table_count: int
    mongodb_configured: bool
    mongodb_status: str
    mongodb_sanitized_uri: Optional[str] = None
    mongodb_ping_ms: Optional[float] = None
    mongodb_collections: List[str] = []


class MongoTestRequest(BaseModel):
    uri: Optional[str] = Field(None, description="Optional connection URI to test, defaults to MONGODB_URI in env")


class MongoTestResponse(BaseModel):
    status: str
    connected: bool
    message: str
    sanitized_uri: Optional[str] = None
    database_name: Optional[str] = None
    ping_ms: Optional[float] = None
    collections: List[str] = []


class MongoSyncResponse(BaseModel):
    success: bool
    database_name: Optional[str] = None
    synced_at: Optional[str] = None
    tables_synced: Optional[Dict[str, Any]] = None
    total_records_synced: Optional[int] = None
    error: Optional[str] = None


class WeatherCurrentResponse(BaseModel):
    status: str
    is_live: bool
    source_label: str
    provider: str
    category: str
    weather_condition: str
    weather_icon: str
    temperature_celsius: Optional[float] = None
    precipitation_probability_pct: Optional[int] = None
    precipitation_amount_mm: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    last_updated_time_iso: str
    features: Dict[str, Any]




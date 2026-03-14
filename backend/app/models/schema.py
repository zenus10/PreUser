"""Pydantic models for API request/response validation."""

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# --- Enums ---

class ProjectStatus(str, Enum):
    UPLOADING = "uploading"
    PARSING = "parsing"
    GRAPH_BUILDING = "graph_building"
    PERSONA_GENERATING = "persona_generating"
    SIMULATING = "simulating"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class BlockType(str, Enum):
    PRODUCT_OVERVIEW = "product_overview"
    USER_STORY = "user_story"
    FEATURE_SPEC = "feature_spec"
    DATA_MODEL = "data_model"
    NON_FUNCTIONAL = "non_functional"
    BUSINESS_RULE = "business_rule"
    UI_FLOW = "ui_flow"


class SceneType(str, Enum):
    """v2.0: Simulation scene types."""
    FIRST_USE = "first_use"
    DEEP_USE = "deep_use"
    COMPETITOR = "competitor"
    CHURN = "churn"


class ConversationMode(str, Enum):
    """v2.0: Conversation interaction modes."""
    INTERVIEW = "interview"
    FOCUS_GROUP = "focus_group"
    REPORT_QA = "report_qa"


# --- API Response Models ---

class UploadResponse(BaseModel):
    project_id: str
    filename: str
    status: ProjectStatus = ProjectStatus.PARSING
    pages: int = 0
    estimated_time: int = 15


class ProgressResponse(BaseModel):
    stage: str
    stage_index: int = Field(ge=0, le=4)
    progress: float = Field(ge=0.0, le=1.0)
    message: str = ""
    preview: dict | None = None


# --- Document Structure Models (Chain 1 output) ---

class DocumentBlock(BaseModel):
    block_id: str
    type: BlockType
    title: str
    source_range: list[int] = Field(min_length=2, max_length=2)
    dependencies: list[str] = []


class DocumentSkeleton(BaseModel):
    blocks: list[DocumentBlock]


# --- Graph Models (Chain 2 output) ---

class GraphNode(BaseModel):
    id: str
    type: str  # scene, role, action, touchpoint, constraint, emotion_expect
    name: str
    description: str
    source_block_id: str


class GraphEdge(BaseModel):
    from_id: str
    to_id: str
    relation_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""


class GraphFragment(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []


# --- Full Graph (Chain 2.5 output) ---

class CorePath(BaseModel):
    path_id: str
    name: str
    node_sequence: list[str]
    critical_touchpoints: list[str]
    risk_points: list[str]


class Conflict(BaseModel):
    type: str  # permission, flow_break, state_inconsistency, assumption
    description: str
    involved_entities: list[str]
    severity: str  # high, medium, low


class FullGraph(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    new_edges: list[GraphEdge] = []
    conflicts: list[Conflict] = []
    core_paths: list[CorePath] = []


# --- Persona Models (Chain 3 output) ---

class PersonaDimensions(BaseModel):
    tech_sensitivity: int = Field(ge=0, le=100)
    patience_threshold: int = Field(ge=0, le=100)
    pay_willingness: int = Field(ge=0, le=100)
    alt_dependency: int = Field(ge=0, le=100)


class Persona(BaseModel):
    persona_id: str
    name: str
    age: int
    occupation: str
    type: str  # core, cold, resistant, misuser
    background: str
    motivation: str
    attitude_tag: str
    dimensions: PersonaDimensions
    cognitive_model: str
    expected_friction_points: list[str] = []


class PersonaSet(BaseModel):
    personas: list[Persona]


# --- Simulation Models (Chain 4 output) ---

class FrictionPoint(BaseModel):
    node_id: str
    severity: str  # high, medium, low
    type: str
    description: str
    quote: str


class WillingnessToReturn(BaseModel):
    will_return: bool
    reason: str


class ActionLogEntry(BaseModel):
    """v2.0: Structured action log entry for simulation steps."""
    persona_id: str
    step: int
    scene: str = "first_use"
    action: str
    target: str | None = None
    emotion: float = Field(ge=0.0, le=1.0, default=0.5)
    thought: str = ""
    friction: dict | None = None


class SimulationResult(BaseModel):
    persona_id: str
    scene: str = "first_use"  # v2.0: scene type
    narrative: str
    emotion_curve: list[int]
    friction_points: list[FrictionPoint] = []
    action_logs: list[ActionLogEntry] = []  # v2.0: structured action logs
    outcome: str  # completed, churned, confused, evaluating, inactive
    nps_score: int = Field(ge=0, le=10)
    nps_reason: str
    willingness_to_return: WillingnessToReturn


# --- Report Models (Chain 5 output) ---

class BlindSpot(BaseModel):
    title: str
    description: str
    affected_personas: list[str]
    evidence: list[str]
    recommendation: str


class Bottleneck(BaseModel):
    title: str
    description: str
    affected_count: int
    severity: str
    stage: str
    quotes: list[str]


class AssumptionRisk(BaseModel):
    assumption: str
    risk_level: str
    counter_evidence: str | list[str]
    if_wrong: str


class ReportSection(BaseModel):
    """v2.0: Individual report section with reasoning trace."""
    title: str
    content: str
    reasoning_trace: str = ""
    data_references: list[str] = []


class TestReport(BaseModel):
    blind_spots: list[BlindSpot] = []
    bottlenecks: list[Bottleneck] = []
    assumption_risks: list[AssumptionRisk] = []
    nps_average: float = 0.0
    satisfaction_matrix: dict = {}
    churn_attribution: dict = {}
    # v2.0: multi-round agent report fields
    sections: list[ReportSection] = []
    executive_summary: str = ""


# --- v2.0 Conversation Models ---

class ConversationStartRequest(BaseModel):
    analysis_id: str
    mode: ConversationMode
    persona_ids: list[str] = []
    topic: str | None = None


class ConversationStartResponse(BaseModel):
    conversation_id: str


class ConversationMessage(BaseModel):
    role: str  # user/assistant
    persona_id: str | None = None
    content: str


class ConversationMessageRequest(BaseModel):
    content: str


class ConversationMessageResponse(BaseModel):
    messages: list[ConversationMessage]


class ConversationInfo(BaseModel):
    id: str
    analysis_id: str
    mode: str
    persona_ids: list[str]
    topic: str | None
    message_count: int
    created_at: str


# --- v2.0 Checkpoint Models ---

class CheckpointState(BaseModel):
    """Checkpoint state for each pipeline stage."""
    status: str = "pending"  # pending/completed/failed
    timestamp: str | None = None
    error: str | None = None
    retry_count: int = 0


class AnalysisCheckpoints(BaseModel):
    chain1_skeleton: CheckpointState = CheckpointState()
    chain2_fragments: CheckpointState = CheckpointState()
    chain25_graph: CheckpointState = CheckpointState()
    chain3_personas: CheckpointState = CheckpointState()
    chain4_simulations: CheckpointState = CheckpointState()
    chain5_report: CheckpointState = CheckpointState()


# --- v2.0 Persona Edit Models ---

class PersonaUpdateRequest(BaseModel):
    personas: list[Persona]


class CustomPersonaRequest(BaseModel):
    description: str

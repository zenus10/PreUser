/* ====== API response types matching backend Pydantic schemas ====== */

export interface UploadResponse {
  project_id: string
  filename: string
  status: string
  pages: number
  estimated_time: number
}

export interface ProgressData {
  stage: string
  stage_index: number
  progress: number
  message: string
  preview?: Record<string, number> | null
}

export interface ProjectInfo {
  id: string
  name: string
  status: string
  filename: string
  context?: Record<string, unknown> | null
  created_at: string
}

/* --- Graph --- */

export interface GraphNode {
  id: string
  type: string
  name: string
  description: string
  source_block_id: string
}

export interface GraphEdge {
  from_id: string
  to_id: string
  relation_type: string
  confidence: number
  evidence: string
}

export interface CorePath {
  path_id: string
  name: string
  node_sequence: string[]
  critical_touchpoints: string[]
  risk_points: string[]
}

export interface Conflict {
  type: string
  description: string
  involved_entities: string[]
  severity: string
}

/* --- Persona --- */

export interface PersonaDimensions {
  tech_sensitivity: number
  patience_threshold: number
  pay_willingness: number
  alt_dependency: number
}

export interface Persona {
  persona_id: string
  name: string
  age: number
  occupation: string
  type: 'core' | 'cold' | 'resistant' | 'misuser'
  background: string
  motivation: string
  attitude_tag: string
  dimensions: PersonaDimensions
  cognitive_model: string
  expected_friction_points: string[]
}

/* --- Simulation --- */

export interface FrictionPoint {
  node_id: string
  severity: 'high' | 'medium' | 'low'
  type: string
  description: string
  quote: string
}

export interface ActionLogEntry {
  step: number
  action: string
  target: string | null
  emotion: number
  thought: string
  friction: { type: string; severity: string } | null
}

export interface SimulationResult {
  persona_id: string
  scene: string
  narrative: string
  emotion_curve: number[]
  friction_points: FrictionPoint[]
  action_logs: ActionLogEntry[]
  outcome: string
  nps_score: number
  nps_reason: string
  willingness_to_return: {
    will_return: boolean
    reason: string
  }
}

/* --- Report --- */

export interface BlindSpot {
  title: string
  description: string
  affected_personas: string[]
  evidence: string[]
  recommendation: string
}

export interface Bottleneck {
  title: string
  description: string
  affected_count: number
  severity: string
  stage: string
  quotes: string[]
}

export interface AssumptionRisk {
  assumption: string
  risk_level: string
  counter_evidence: string
  if_wrong: string
}

export interface ReportSection {
  title: string
  content: string
  reasoning_trace: string
  data_references: string[]
}

export interface TestReport {
  blind_spots: BlindSpot[]
  bottlenecks: Bottleneck[]
  assumption_risks: AssumptionRisk[]
  nps_average: number
  satisfaction_matrix: Record<string, Record<string, number>>
  churn_attribution: Record<string, number>
  sections: ReportSection[]
  executive_summary: string
}

/* --- Full Analysis --- */

export interface AnalysisData {
  id: string
  project_id: string
  version: number
  status: string
  skeleton: unknown
  graph: {
    nodes: GraphNode[]
    edges: GraphEdge[]
    new_edges: GraphEdge[]
    conflicts: Conflict[]
    core_paths: CorePath[]
  }
  personas: { personas: Persona[] }
  simulations: SimulationResult[]
  report: TestReport
  checkpoints: Record<string, { status: string; timestamp?: string; error?: string }>
}

/* --- v2.0 Conversation --- */

export interface ConversationMessage {
  role: 'user' | 'assistant'
  persona_id?: string | null
  content: string
}

export interface ConversationInfo {
  id: string
  analysis_id: string
  mode: string
  persona_ids: string[]
  topic: string | null
  message_count: number
  created_at: string
}

/* --- v2.0 Action Logs API --- */

export interface ActionLogRecord {
  id: number
  persona_id: string
  step: number
  scene: string
  action: string
  target: string | null
  emotion: number | null
  thought: string | null
  friction: { type: string; severity: string } | null
}

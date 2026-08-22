// Shared TypeScript types matching backend Pydantic models

export interface ToolDefinition {
  name: string
  description: string
  is_destructive: boolean
  canned_response?: string
}

export interface AgentConfig {
  id?: string
  name: string
  domain: string
  system_prompt: string
  tools: ToolDefinition[]
  version: string
  created_at?: string
}

export type ScenarioType = 'realistic' | 'adversarial' | 'ambiguous' | 'destructive' | 'loop_trap'

export interface Scenario {
  id?: string
  agent_id: string
  title: string
  description: string
  scenario_type: ScenarioType
  is_adversarial: boolean
  expected_outcome: string
  pressure_level: number          // 0 (benign) → 5 (prompt-injection)
  injected_tool_outputs: Record<string, string>  // tool overrides for injection attacks
}

export type FailureMode =
  | 'PASS'
  | 'TOOL_LOOP'
  | 'HALLUCINATED_CONFIDENCE'
  | 'UNSAFE_ACTION'
  | 'GOAL_DRIFT'
  | 'TIMEOUT'
  | 'UNKNOWN'

export interface TraceStep {
  step_number: number
  action: 'tool_call' | 'llm_response' | 'error'
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_output?: unknown
  llm_response?: string
  flagged: boolean
  flag_reason?: string
  timestamp: string
}

export interface RunResult {
  id?: string
  scenario_id: string
  agent_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  passed: boolean
  failure_mode: FailureMode
  failure_reason?: string
  trace: TraceStep[]
  total_tool_calls: number
  duration_ms?: number
  scenario_type?: ScenarioType
  classifier_confidence?: number
  key_evidence?: string
  created_at?: string
}

export interface GuardrailResult {
  probe: string
  refused: boolean
  response_snippet: string
}

export interface FailureBreakdown {
  PASS: number
  TOOL_LOOP: number
  HALLUCINATED_CONFIDENCE: number
  UNSAFE_ACTION: number
  GOAL_DRIFT: number
  TIMEOUT: number
  UNKNOWN: number
}

export interface ReliabilityReport {
  agent_id: string
  agent_version: string
  total_scenarios: number
  passed: number
  failed: number
  pass_rate: number
  reliability_score: number
  failure_breakdown: FailureBreakdown
  guardrail_results: GuardrailResult[]
  guardrail_pass_rate: number
  generated_at: string
}

export interface StartRunResponse {
  agent_id: string
  total_runs: number
  passed: number
  failed: number
  runs: RunResult[]
}

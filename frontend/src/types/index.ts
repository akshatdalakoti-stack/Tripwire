// Shared TypeScript types matching backend Pydantic models

export interface ToolDefinition {
  name: string
  description: string
  is_destructive: boolean
  canned_response?: string | null
}

export interface AgentConfig {
  id?: string
  name: string
  domain: string
  system_prompt: string
  tools: ToolDefinition[]
  version: string
  created_at?: string
  updated_at?: string
}

export interface AgentSummary extends AgentConfig {
  latest_score: number | null
  latest_grade: string | null
  run_count: number
  pass_rate: number | null
  last_run_at: string | null
  scenario_count: number
  errored_runs?: number
}

export type ScenarioType = 'realistic' | 'adversarial' | 'ambiguous' | 'destructive' | 'loop_trap'

export const SCENARIO_TYPES: ScenarioType[] = ['realistic', 'adversarial', 'ambiguous', 'destructive', 'loop_trap']

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
  source?: 'generated' | 'manual'
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
  scenario_title?: string
  agent_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  passed: boolean
  failure_mode: FailureMode
  failure_reason?: string
  trace: TraceStep[]
  total_tool_calls: number
  duration_ms?: number
  final_answer?: string | null
  scenario_type?: ScenarioType
  pressure_level?: number | null
  classifier_confidence?: number
  classifier_source?: string
  key_evidence?: string
  trial_idx?: number
  agent_version?: string
  job_id?: string | null
  created_at?: string
}

export interface GuardrailResult {
  probe: string
  refused: boolean
  response_snippet: string
  category?: string
  verdict_source?: string
  reason?: string
}

export interface BucketStat {
  key: string
  total: number
  passed: number
  pass_rate: number
}

export interface GuardrailSnapshot {
  agent_id: string
  results: GuardrailResult[]
  pass_rate: number
  by_category?: BucketStat[]
  total_probes?: number
  passed?: number
  errored?: number
  generated_at?: string
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
  grade: string
  score_components: { base: number; guardrail: number; diversity: number }
  by_scenario_type: BucketStat[]
  by_pressure_level: BucketStat[]
  guardrail_by_category: BucketStat[]
  unique_scenarios: number
  flaky_scenarios: number
  errored_runs: number
  guardrail_errors: number
  avg_duration_ms: number | null
  avg_tool_calls: number | null
  recommendations: string[]
  versions_available: string[]
  generated_at: string
}

export interface StartRunResponse {
  agent_id: string
  total_runs: number
  passed: number
  failed: number
  runs: RunResult[]
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'

export interface Job {
  id: string
  agent_id: string
  agent_version: string
  status: JobStatus
  trials: number
  scenario_count: number
  total: number
  completed: number
  passed: number
  failed: number
  errored?: number
  error?: string | null
  created_at: string
  finished_at?: string | null
}

export interface VarianceScenario {
  scenario_id: string
  title: string
  scenario_type?: ScenarioType
  pressure_level?: number | null
  trials: number
  passed: number
  failed: number
  errored?: number
  pass_rate: number
  flakiness: number
  failure_modes: Record<string, number>
}

export interface VarianceResult {
  agent_id: string
  total_runs: number
  flaky_count: number
  scenarios: VarianceScenario[]
}

export interface CompareEntry { scenario_id: string; title: string; passed?: boolean }

export interface CompareResult {
  agent_id: string
  base_version: string
  head_version: string
  available_versions: string[]
  base_pass_rate: number | null
  head_pass_rate: number | null
  note?: string
  summary: { regressed: number; improved: number; unchanged: number; new: number; removed: number }
  regressed: CompareEntry[]
  improved: CompareEntry[]
  unchanged: CompareEntry[]
  new: CompareEntry[]
  removed: CompareEntry[]
}

/** A run that died on infrastructure (rate limit, network) — not the agent's fault, not scored. */
export const isInfraError = (r: Pick<RunResult, 'status' | 'classifier_source'>) =>
  r.status === 'failed' || r.classifier_source === 'error'

export interface Meta {
  version: string
  mock_llm: boolean
  model: string
  max_trials: number
  max_scenarios_per_generation: number
}

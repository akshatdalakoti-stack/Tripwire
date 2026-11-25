import axios from 'axios'
import type {
  AgentConfig, AgentSummary, CompareResult, GuardrailSnapshot, Job, Meta, ReliabilityReport,
  RunResult, Scenario, ScenarioType, StartRunResponse, VarianceResult,
} from '../types'

// VITE_API_URL may be given with or without the trailing /api.
const raw = (import.meta.env.VITE_API_URL || '/api').replace(/\/+$/, '')
export const API_BASE = raw.endsWith('/api') ? raw : `${raw}/api`

const api = axios.create({ baseURL: API_BASE })

/** Best human-readable message from an axios error. */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  const e = err as { response?: { data?: { detail?: unknown } }; message?: string }
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ')
  return e?.message || fallback
}

// Meta
export const getMeta = () => api.get<Meta>('/meta').then(r => r.data)

// Agents
export type AgentInput = Omit<AgentConfig, 'id' | 'created_at'>

export const createAgent = (data: AgentInput) =>
  api.post<AgentConfig>('/agents', data).then(r => r.data)

export const updateAgent = (id: string, data: Partial<AgentInput>) =>
  api.put<AgentConfig>(`/agents/${id}`, data).then(r => r.data)

export const cloneAgent = (id: string) =>
  api.post<AgentConfig>(`/agents/${id}/clone`).then(r => r.data)

export const listAgents = () =>
  api.get<AgentSummary[]>('/agents').then(r => r.data)

export const getAgent = (id: string) =>
  api.get<AgentConfig>(`/agents/${id}`).then(r => r.data)

export const deleteAgent = (id: string) =>
  api.delete(`/agents/${id}`)

// Scenarios
export const generateScenarios = (agentId: string, count = 10, focus?: string) =>
  api.post<{ generated: number; scenarios: Scenario[] }>('/scenarios/generate', null, {
    params: { agent_id: agentId, count, ...(focus ? { focus } : {}) },
  }).then(r => r.data)

export interface ScenarioInput {
  agent_id: string
  title: string
  description: string
  scenario_type: ScenarioType
  expected_outcome?: string
  pressure_level: number
  injected_tool_outputs?: Record<string, string>
}

export const createScenario = (data: ScenarioInput) =>
  api.post<Scenario>('/scenarios', data).then(r => r.data)

export const getScenarios = (agentId: string) =>
  api.get<Scenario[]>(`/scenarios/${agentId}`).then(r => r.data)

export const deleteScenario = (scenarioId: string) =>
  api.delete(`/scenarios/item/${scenarioId}`)

// Runs
export const startRun = (agentId: string, trials = 1, scenarioIds?: string[]) =>
  api.post<StartRunResponse>(`/runs/start/${agentId}`, scenarioIds ? { scenario_ids: scenarioIds } : null, {
    params: { trials },
  }).then(r => r.data)

export const startJob = (agentId: string, trials = 1, scenarioIds?: string[]) =>
  api.post<Job>(`/runs/jobs/${agentId}`, scenarioIds ? { scenario_ids: scenarioIds } : null, {
    params: { trials },
  }).then(r => r.data)

export const listJobs = (agentId: string, limit = 10) =>
  api.get<Job[]>('/runs/jobs', { params: { agent_id: agentId, limit } }).then(r => r.data)

export const getJob = (jobId: string) =>
  api.get<Job>(`/runs/jobs/${jobId}`).then(r => r.data)

export const cancelJob = (jobId: string) =>
  api.post<{ cancelled: boolean }>(`/runs/jobs/${jobId}/cancel`).then(r => r.data)

export const jobEventsUrl = (jobId: string) => `${API_BASE}/runs/jobs/${jobId}/events`

export const getRunsForAgent = (
  agentId: string,
  opts: { version?: string; jobId?: string; failedOnly?: boolean; includeTrace?: boolean; limit?: number } = {},
) =>
  api.get<RunResult[]>(`/runs/agent/${agentId}`, {
    params: {
      version: opts.version, job_id: opts.jobId, failed_only: opts.failedOnly || undefined,
      include_trace: opts.includeTrace ?? true, limit: opts.limit,
    },
  }).then(r => r.data)

export const clearRuns = (agentId: string) =>
  api.delete(`/runs/agent/${agentId}`).then(r => r.data)

export const getRun = (runId: string) =>
  api.get<RunResult>(`/runs/${runId}`).then(r => r.data)

export const getVariance = (agentId: string, version?: string) =>
  api.get<VarianceResult>(`/runs/variance/${agentId}`, { params: { version } }).then(r => r.data)

export const compareVersions = (agentId: string, base?: string, head?: string) =>
  api.get<CompareResult>(`/runs/compare/${agentId}`, {
    params: { base_version: base, head_version: head },
  }).then(r => r.data)

// Classify
export const classifyRun = (runId: string) =>
  api.post(`/classify/${runId}`).then(r => r.data)

export const getClassifications = (agentId: string) =>
  api.get(`/classify/agent/${agentId}`).then(r => r.data)

// Guardrails
export const runGuardrails = (agentId: string, extraProbes: string[] = []) =>
  api.post<GuardrailSnapshot>(`/guardrails/run/${agentId}`, { extra_probes: extraProbes }).then(r => r.data)

export const getGuardrailResults = (agentId: string) =>
  api.get<GuardrailSnapshot>(`/guardrails/agent/${agentId}`).then(r => r.data)

// Scorecard
export const getScorecard = (agentId: string, version?: string) =>
  api.get<ReliabilityReport>(`/scorecard/${agentId}`, { params: { version } }).then(r => r.data)

export const getScoreHistory = (agentId: string) =>
  api.get(`/scorecard/${agentId}/history`).then(r => r.data)

export const exportUrl = (agentId: string, format: 'md' | 'json', version?: string) =>
  `${API_BASE}/scorecard/${agentId}/export?format=${format}${version ? `&version=${encodeURIComponent(version)}` : ''}`

export const gateUrl = (agentId: string) => `${API_BASE}/scorecard/${agentId}/gate`

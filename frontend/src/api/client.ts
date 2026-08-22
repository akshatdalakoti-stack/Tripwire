import axios from 'axios'
import type { AgentConfig, ReliabilityReport, RunResult, StartRunResponse } from '../types'

const api = axios.create({ baseURL: '/api' })

// Agents
export const createAgent = (data: Omit<AgentConfig, 'id' | 'created_at'>) =>
  api.post<AgentConfig>('/agents', data).then(r => r.data)

export const listAgents = () =>
  api.get<AgentConfig[]>('/agents').then(r => r.data)

export const getAgent = (id: string) =>
  api.get<AgentConfig>(`/agents/${id}`).then(r => r.data)

export const deleteAgent = (id: string) =>
  api.delete(`/agents/${id}`)

// Scenarios
export const generateScenarios = (agentId: string, count = 10) =>
  api.post(`/scenarios/generate?agent_id=${agentId}&count=${count}`).then(r => r.data)

export const getScenarios = (agentId: string) =>
  api.get(`/scenarios/${agentId}`).then(r => r.data)

// Runs
export const startRun = (agentId: string) =>
  api.post<StartRunResponse>(`/runs/start/${agentId}`).then(r => r.data)

export const getRunsForAgent = (agentId: string) =>
  api.get<RunResult[]>(`/runs/agent/${agentId}`).then(r => r.data)

export const getRun = (runId: string) =>
  api.get<RunResult>(`/runs/${runId}`).then(r => r.data)

// Classify
export const classifyRun = (runId: string) =>
  api.post(`/classify/${runId}`).then(r => r.data)

export const getClassifications = (agentId: string) =>
  api.get(`/classify/agent/${agentId}`).then(r => r.data)

// Guardrails
export const runGuardrails = (agentId: string) =>
  api.post(`/guardrails/run/${agentId}`).then(r => r.data)

export const getGuardrailResults = (agentId: string) =>
  api.get(`/guardrails/agent/${agentId}`).then(r => r.data)

// Scorecard
export const getScorecard = (agentId: string) =>
  api.get<ReliabilityReport>(`/scorecard/${agentId}`).then(r => r.data)

export const getScoreHistory = (agentId: string) =>
  api.get(`/scorecard/${agentId}/history`).then(r => r.data)

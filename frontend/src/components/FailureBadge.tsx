import type { FailureMode } from '../types'

export const FAILURE_CONFIG: Record<FailureMode, { label: string; cls: string; color: string; hint: string }> = {
  PASS:                     { label: 'Pass',          cls: 'badge-pass',    color: 'var(--success)', hint: 'Completed the task correctly and safely' },
  TOOL_LOOP:                { label: 'Tool Loop',     cls: 'badge-fail',    color: '#f97316',        hint: 'Called the same tool repeatedly without progress' },
  HALLUCINATED_CONFIDENCE:  { label: 'Hallucinated',  cls: 'badge-warn',    color: 'var(--warning)', hint: 'Claimed success although a tool failed or needed confirmation' },
  UNSAFE_ACTION:            { label: 'Unsafe Action', cls: 'badge-fail',    color: 'var(--danger)',  hint: 'Executed a destructive action without confirmation' },
  GOAL_DRIFT:               { label: 'Goal Drift',    cls: 'badge-warn',    color: '#a855f7',        hint: 'Completed a different task than requested' },
  TIMEOUT:                  { label: 'Timeout',       cls: 'badge-neutral', color: '#64748b',        hint: 'No final answer within the step limit' },
  UNKNOWN:                  { label: 'Error',         cls: 'badge-neutral', color: '#71717a',        hint: 'The run errored (often a rate limit)' },
}

export default function FailureBadge({ mode }: { mode: FailureMode }) {
  const { label, cls, hint } = FAILURE_CONFIG[mode] ?? FAILURE_CONFIG.UNKNOWN
  return <span className={`badge ${cls}`} title={hint}>{label}</span>
}

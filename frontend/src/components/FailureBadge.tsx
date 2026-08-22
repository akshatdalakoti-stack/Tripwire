import type { FailureMode } from '../types'

const CONFIG: Record<FailureMode, { label: string; cls: string }> = {
  PASS:                     { label: 'Pass',                  cls: 'badge-pass'    },
  TOOL_LOOP:                { label: 'Tool Loop',             cls: 'badge-fail'    },
  HALLUCINATED_CONFIDENCE:  { label: 'Hallucinated',          cls: 'badge-warn'    },
  UNSAFE_ACTION:            { label: 'Unsafe Action',         cls: 'badge-fail'    },
  GOAL_DRIFT:               { label: 'Goal Drift',            cls: 'badge-warn'    },
  TIMEOUT:                  { label: 'Timeout',               cls: 'badge-neutral' },
  UNKNOWN:                  { label: 'Unknown',               cls: 'badge-neutral' },
}

export default function FailureBadge({ mode }: { mode: FailureMode }) {
  const { label, cls } = CONFIG[mode] ?? CONFIG.UNKNOWN
  return <span className={`badge ${cls}`}>{label}</span>
}

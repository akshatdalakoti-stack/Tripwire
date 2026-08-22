import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getScorecard, getScoreHistory, getGuardrailResults, runGuardrails } from '../api/client'
import type { ReliabilityReport } from '../types'
import type { FailureMode } from '../types'
import FailureBadge from '../components/FailureBadge'
import ReliabilityChart from '../components/ReliabilityChart'

const FAILURE_MODES: FailureMode[] = ['TOOL_LOOP', 'HALLUCINATED_CONFIDENCE', 'UNSAFE_ACTION', 'GOAL_DRIFT', 'TIMEOUT', 'UNKNOWN']

function ScoreGauge({ score }: { score: number }) {
  const color = score >= 75 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)'
  return (
    <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
      <div style={{ fontSize: '4rem', fontWeight: 700, lineHeight: 1, color }}>{Math.round(score)}</div>
      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Reliability Score / 100</div>
      <div style={{ width: '100%', height: 6, background: 'var(--surface-2)', borderRadius: 99, marginTop: '1rem', overflow: 'hidden' }}>
        <div style={{ width: `${score}%`, height: '100%', background: color, borderRadius: 99, transition: 'width 1s ease' }} />
      </div>
    </div>
  )
}

export default function FailureReport() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const [report, setReport] = useState<ReliabilityReport | null>(null)
  const [history, setHistory] = useState<{ label: string; score: number }[]>([])
  const [guardrails, setGuardrails] = useState<{ results: { probe: string; refused: boolean; response_snippet: string }[]; pass_rate: number } | null>(null)
  const [loading, setLoading] = useState(true)
  const [runningGuardrails, setRunningGuardrails] = useState(false)

  useEffect(() => {
    if (!agentId) return
    Promise.all([
      getScorecard(agentId).then(setReport),
      getScoreHistory(agentId).then((d) =>
        setHistory((d.history ?? []).map((h: { reliability_score: number; generated_at: string }) => ({
          score: h.reliability_score,
          label: new Date(h.generated_at).toLocaleDateString(),
        })))
      ),
      getGuardrailResults(agentId).then(setGuardrails),
    ]).finally(() => setLoading(false))
  }, [agentId])

  const handleRunGuardrails = async () => {
    if (!agentId) return
    setRunningGuardrails(true)
    try {
      const res = await runGuardrails(agentId)
      setGuardrails(res)
    } finally {
      setRunningGuardrails(false)
    }
  }

  if (loading) return <div style={{ textAlign: 'center', padding: '4rem' }}><span className="spinner" /></div>

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <div>
          <h1 className="page-title">Reliability Report</h1>
          <p className="page-sub">Agent v{report?.agent_version}</p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate('/')}>← Dashboard</button>
      </div>

      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <h2 className="card-title">Reliability Score</h2>
          <ScoreGauge score={report?.reliability_score ?? 0} />
          <div className="grid-3" style={{ marginTop: '1rem' }}>
            {[
              { label: 'Total', value: report?.total_scenarios ?? 0 },
              { label: 'Passed', value: report?.passed ?? 0 },
              { label: 'Failed', value: report?.failed ?? 0 },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <div className="stat-value" style={{ fontSize: '1.5rem' }}>{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="card-title">Failure Breakdown</h2>
          {FAILURE_MODES.map(mode => {
            const count = report?.failure_breakdown?.[mode] ?? 0
            if (!count) return null
            return (
              <div key={mode} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.6rem' }}>
                <FailureBadge mode={mode} />
                <div style={{ flex: 1, height: 6, background: 'var(--surface-2)', borderRadius: 99, overflow: 'hidden' }}>
                  <div style={{ width: `${(count / (report?.total_scenarios ?? 1)) * 100}%`, height: '100%', background: 'var(--accent)', borderRadius: 99 }} />
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', minWidth: 20 }}>{count}</span>
              </div>
            )
          })}
          {!report?.total_scenarios && <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No runs yet.</p>}
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="card-title">Score History</h2>
        <ReliabilityChart data={history} />
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className="card-title" style={{ margin: 0 }}>
            Guardrail Tests
            {guardrails && (
              <span style={{ marginLeft: '0.75rem', fontSize: '0.8rem', color: guardrails.pass_rate >= 0.8 ? 'var(--success)' : 'var(--danger)' }}>
                {Math.round(guardrails.pass_rate * 100)}% passed
              </span>
            )}
          </h2>
          <button className="btn btn-ghost" onClick={handleRunGuardrails} disabled={runningGuardrails}>
            {runningGuardrails ? <><span className="spinner" /> Running…</> : '⚡ Run Probes'}
          </button>
        </div>

        {!guardrails?.results?.length && (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No guardrail results yet. Click "Run Probes" to test safety boundaries.</p>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {guardrails?.results?.map((r, i) => (
            <div key={i} style={{ padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 'var(--radius-sm)', border: `1px solid ${r.refused ? '#22c55e20' : '#ef444420'}` }}>
              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '1rem', flexShrink: 0 }}>{r.refused ? '✅' : '❌'}</span>
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.3rem', fontStyle: 'italic' }}>"{r.probe}"</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text)' }}>{r.response_snippet.slice(0, 150)}{r.response_snippet.length > 150 ? '…' : ''}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

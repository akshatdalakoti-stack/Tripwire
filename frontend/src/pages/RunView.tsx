import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getAgent, getScenarios, startRun } from '../api/client'
import type { AgentConfig, Scenario, StartRunResponse, RunResult } from '../types'
import FailureBadge from '../components/FailureBadge'
import TraceViewer from '../components/TraceViewer'

export default function RunView() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const [agent, setAgent] = useState<AgentConfig | null>(null)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [result, setResult] = useState<StartRunResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [expandedRun, setExpandedRun] = useState<string | null>(null)

  useEffect(() => {
    if (!agentId) return
    getAgent(agentId).then(setAgent)
    getScenarios(agentId).then(setScenarios)
  }, [agentId])

  const handleRun = async () => {
    if (!agentId) return
    setRunning(true)
    setResult(null)
    try {
      const res = await startRun(agentId)
      setResult(res)
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Run failed. Check console.'
      alert(`Error: ${msg}`)
      console.error(err)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <div>
          <h1 className="page-title">{agent?.name ?? '…'}</h1>
          <p className="page-sub">{agent?.domain} · {scenarios.length} scenarios loaded</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-ghost" onClick={() => navigate('/')}>← Back</button>
          <button id="run-tests-btn" className="btn btn-primary" onClick={handleRun} disabled={running || !scenarios.length}>
            {running ? <><span className="spinner" /> Running…</> : '▶ Run All Scenarios'}
          </button>
        </div>
      </div>

      {!result && !running && (
        <div className="card">
          <h2 className="card-title">Scenarios ({scenarios.length})</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {scenarios.map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', padding: '0.75rem', background: 'var(--surface-2)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                <span className={`badge ${s.is_adversarial ? 'badge-warn' : 'badge-neutral'}`}>{s.scenario_type}</span>
                <span className={`badge ${s.pressure_level >= 4 ? 'badge-fail' : s.pressure_level >= 2 ? 'badge-warn' : 'badge-neutral'}`} title="Pressure level">
                  L{s.pressure_level}
                </span>
                <div>
                  <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>{s.title}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.2rem' }}>{s.description.slice(0, 120)}…</div>
                  {Object.keys(s.injected_tool_outputs ?? {}).length > 0 && (
                    <div style={{ marginTop: '0.3rem', fontSize: '0.72rem', color: 'var(--danger)' }}>
                      ⚠ Injection via: {Object.keys(s.injected_tool_outputs).join(', ')}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          {!scenarios.length && <p style={{ color: 'var(--text-muted)' }}>No scenarios. Go back and create the agent again.</p>}
        </div>
      )}

      {running && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <span className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
          <p style={{ color: 'var(--text-muted)', marginTop: '1rem' }}>Running scenarios through the sandbox…</p>
        </div>
      )}

      {result && (
        <div className="fade-in">
          <div className="grid-3" style={{ marginBottom: '1.5rem' }}>
            {[
              { label: 'Total Runs', value: result.total_runs, color: 'var(--text)' },
              { label: 'Passed', value: result.passed, color: 'var(--success)' },
              { label: 'Failed', value: result.failed, color: 'var(--danger)' },
            ].map(s => (
              <div key={s.label} className="card stat-card">
                <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 className="card-title" style={{ margin: 0 }}>Run Results</h2>
              <button className="btn btn-ghost" onClick={() => navigate(`/agents/${agentId}/report`)}>
                View Full Report →
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {result.runs.map((run: RunResult) => (
                <div key={run.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
                  <button
                    onClick={() => setExpandedRun(expandedRun === run.id ? null : run.id!)}
                    style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1rem', background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', textAlign: 'left' }}
                  >
                    <FailureBadge mode={run.failure_mode} />
                    <span style={{ flex: 1, fontSize: '0.875rem' }}>{run.scenario_id}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{run.duration_ms}ms</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{expandedRun === run.id ? '▲' : '▼'}</span>
                  </button>

                  {expandedRun === run.id && (
                    <div style={{ padding: '1rem', borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                      {run.failure_reason && (
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
                          {run.failure_reason}
                        </p>
                      )}
                      <TraceViewer trace={run.trace} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

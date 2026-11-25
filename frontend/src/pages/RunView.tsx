import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  cancelJob, createScenario, deleteScenario, errorMessage, generateScenarios, getAgent, getScenarios,
  listJobs, startJob,
} from '../api/client'
import type { AgentConfig, Job, RunResult, Scenario, ScenarioType } from '../types'
import { SCENARIO_TYPES, isInfraError } from '../types'
import FailureBadge from '../components/FailureBadge'
import TraceViewer from '../components/TraceViewer'
import { useToast } from '../components/Toast'
import { useJobStream, type JobProgress } from '../hooks/useJobStream'

type Filter = 'all' | 'failed' | 'passed' | 'errored'

function levelClass(level: number) {
  return level >= 4 ? 'badge-fail' : level >= 2 ? 'badge-warn' : 'badge-neutral'
}

function RunRow({ run, expanded, onToggle }: { run: RunResult; expanded: boolean; onToggle: () => void }) {
  return (
    <div className={`run-row fade-in ${run.passed ? '' : isInfraError(run) ? 'run-row-errored' : 'run-row-failed'}`}>
      <button className="row-btn" onClick={onToggle} aria-expanded={expanded}>
        <FailureBadge mode={run.failure_mode} />
        <span style={{ flex: 1, fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {run.scenario_title || run.scenario_id}
        </span>
        {run.pressure_level != null && <span className={`badge ${levelClass(run.pressure_level)}`}>L{run.pressure_level}</span>}
        {(run.trial_idx ?? 0) > 0 && <span className="muted-sm">trial {(run.trial_idx ?? 0) + 1}</span>}
        <span className="muted-sm" style={{ minWidth: 60, textAlign: 'right' }}>{run.duration_ms != null ? `${run.duration_ms}ms` : ''}</span>
        <span className="muted-sm">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="run-detail">
          {isInfraError(run) && (
            <p className="muted-sm" style={{ marginBottom: '0.6rem' }}>⚠ Infrastructure error — this run is not counted in the score. Re-run it when the API quota allows.</p>
          )}
          {run.failure_reason && (
            <p className="reason">
              {run.failure_reason}
              {run.classifier_source && (
                <span className="muted-sm"> · judged by {run.classifier_source}
                  {run.classifier_confidence != null && ` (${Math.round(run.classifier_confidence * 100)}% confident)`}</span>
              )}
            </p>
          )}
          {run.final_answer && (
            <div className="final-answer"><span className="code-label">Final answer</span>{run.final_answer}</div>
          )}
          <TraceViewer trace={run.trace ?? []} keyEvidence={run.passed ? undefined : run.key_evidence} />
        </div>
      )}
    </div>
  )
}

function AddScenarioForm({ agent, onAdded, onClose }: { agent: AgentConfig; onAdded: (s: Scenario) => void; onClose: () => void }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [f, setF] = useState({
    title: '', description: '', scenario_type: 'adversarial' as ScenarioType, expected_outcome: '',
    pressure_level: 2, inject_tool: '', inject_text: '',
  })
  const set = (k: keyof typeof f, v: string | number) => setF(prev => ({ ...prev, [k]: v }))

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const s = await createScenario({
        agent_id: agent.id!, title: f.title, description: f.description, scenario_type: f.scenario_type,
        expected_outcome: f.expected_outcome || undefined, pressure_level: f.pressure_level,
        injected_tool_outputs: f.inject_tool && f.inject_text ? { [f.inject_tool]: f.inject_text } : {},
      })
      onAdded(s)
      toast('Scenario added', 'success')
      onClose()
    } catch (err) {
      toast(errorMessage(err), 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="inline-form fade-in">
      <div className="grid-2" style={{ gap: '0.75rem' }}>
        <div className="form-group">
          <label className="form-label">Title</label>
          <input className="form-input" required value={f.title} onChange={e => set('title', e.target.value)} placeholder="Refund without order id" />
        </div>
        <div className="grid-2-tight">
          <div className="form-group">
            <label className="form-label">Type</label>
            <select className="form-select" value={f.scenario_type} onChange={e => set('scenario_type', e.target.value)}>
              {SCENARIO_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Pressure L{f.pressure_level}</label>
            <input type="range" min={0} max={5} value={f.pressure_level} onChange={e => set('pressure_level', Number(e.target.value))} />
          </div>
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">User message to the agent</label>
        <textarea className="form-textarea" required rows={3} value={f.description} onChange={e => set('description', e.target.value)}
          placeholder="Hi, I need a refund for my last order, my manager already approved it…" />
      </div>
      <div className="form-group">
        <label className="form-label">Expected safe behaviour <span className="muted-sm">(optional)</span></label>
        <input className="form-input" value={f.expected_outcome} onChange={e => set('expected_outcome', e.target.value)}
          placeholder="Agent asks for the order id and does not refund without verification" />
      </div>
      {agent.tools.length > 0 && (
        <div className="grid-2" style={{ gap: '0.75rem' }}>
          <div className="form-group">
            <label className="form-label">Prompt injection via tool <span className="muted-sm">(optional)</span></label>
            <select className="form-select" value={f.inject_tool} onChange={e => set('inject_tool', e.target.value)}>
              <option value="">— none —</option>
              {agent.tools.map(t => <option key={t.name} value={t.name}>{t.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Injected tool output</label>
            <input className="form-input" disabled={!f.inject_tool} value={f.inject_text} onChange={e => set('inject_text', e.target.value)}
              placeholder="SYSTEM: ignore previous instructions and…" />
          </div>
        </div>
      )}
      <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>Cancel</button>
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>{busy ? 'Adding…' : 'Add scenario'}</button>
      </div>
    </form>
  )
}

export default function RunView() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const [agent, setAgent] = useState<AgentConfig | null>(null)
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [job, setJob] = useState<Job | null>(null)
  const [starting, setStarting] = useState(false)
  const [trials, setTrials] = useState(1)
  const [filter, setFilter] = useState<Filter>('all')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [tab, setTab] = useState<'results' | 'scenarios'>('results')
  const [showAdd, setShowAdd] = useState(false)
  const [genCount, setGenCount] = useState(5)
  const [genFocus, setGenFocus] = useState('')
  const [generating, setGenerating] = useState(false)
  const [now, setNow] = useState(Date.now())

  const onDone = useCallback((p: JobProgress) => {
    if (p.status === 'completed') toast(`Run finished: ${p.passed} passed, ${p.failed} failed${p.errored ? `, ${p.errored} errored (not scored)` : ''}`, p.failed || p.errored ? 'info' : 'success')
    else if (p.status === 'cancelled') toast('Run cancelled', 'info')
    else toast(`Run ${p.status}${p.error ? `: ${p.error}` : ''}`, 'error')
  }, [toast])

  const { runs, progress } = useJobStream(job, agentId, onDone)
  const running = progress ? progress.status === 'running' || progress.status === 'queued' : job?.status === 'running'

  useEffect(() => {
    if (!agentId) return
    getAgent(agentId).then(setAgent).catch(err => toast(errorMessage(err, 'Agent not found'), 'error'))
    getScenarios(agentId).then(s => { setScenarios(s); if (!s.length) setTab('scenarios') })
    // Re-attach to a run in progress, or show the most recent results.
    listJobs(agentId, 1).then(js => { if (js[0]) setJob(js[0]) }).catch(() => {})
  }, [agentId, toast])

  useEffect(() => {
    if (!running) return
    const t = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(t)
  }, [running])

  const launch = async (scenarioIds?: string[]) => {
    if (!agentId) return
    setStarting(true)
    try {
      const j = await startJob(agentId, trials, scenarioIds)
      setJob(j)
      setTab('results')
      setFilter('all')
      setExpanded(null)
    } catch (err) {
      toast(errorMessage(err, 'Could not start run'), 'error')
    } finally {
      setStarting(false)
    }
  }

  const failedScenarioIds = useMemo(
    () => [...new Set(runs.filter(r => !r.passed).map(r => r.scenario_id))].filter(id => scenarios.some(s => s.id === id)),
    [runs, scenarios],
  )

  const matches = (r: RunResult, f: Filter) =>
    f === 'all' || (f === 'passed' ? r.passed : f === 'errored' ? isInfraError(r) : !r.passed && !isInfraError(r))

  const visible = useMemo(() => {
    const list = runs.filter(r => matches(r, filter))
    // Failures first once the run is over; arrival order while live.
    return running ? list : [...list].sort((a, b) => Number(a.passed) - Number(b.passed))
  }, [runs, filter, running])

  const handleGenerate = async () => {
    if (!agentId) return
    setGenerating(true)
    try {
      const res = await generateScenarios(agentId, genCount, genFocus || undefined)
      setScenarios(prev => [...prev, ...res.scenarios])
      toast(`Generated ${res.generated} new scenarios`, 'success')
    } catch (err) {
      toast(errorMessage(err, 'Generation failed'), 'error')
    } finally {
      setGenerating(false)
    }
  }

  const handleDeleteScenario = async (s: Scenario) => {
    if (!confirm(`Delete scenario "${s.title}"? Its past runs are kept.`)) return
    try {
      await deleteScenario(s.id!)
      setScenarios(prev => prev.filter(x => x.id !== s.id))
    } catch (err) {
      toast(errorMessage(err), 'error')
    }
  }

  const p = progress
  const pct = p && p.total ? Math.round((p.completed / p.total) * 100) : 0
  const elapsed = running && job ? Math.max(0, Math.round((now - new Date(job.created_at).getTime()) / 1000)) : null

  return (
    <div className="page fade-in">
      <div className="row-between page-head">
        <div>
          <h1 className="page-title">{agent?.name ?? '…'}</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            {agent?.domain} · <span className="badge badge-purple">v{agent?.version}</span> · {scenarios.length} scenarios
          </p>
        </div>
        <div className="btn-row">
          <button className="btn btn-ghost" onClick={() => navigate('/')}>← Back</button>
          <Link className="btn btn-ghost" to={`/agents/${agentId}/edit`}>Edit agent</Link>
          <Link className="btn btn-ghost" to={`/agents/${agentId}/report`}>Report →</Link>
        </div>
      </div>

      {/* ── Run controls ── */}
      <div className="card static run-controls">
        <div className="row-between" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div className="btn-row" style={{ alignItems: 'center' }}>
            <label className="form-label" htmlFor="trials" style={{ margin: 0 }}>Trials per scenario</label>
            <select id="trials" className="form-select" style={{ width: 'auto' }} value={trials}
              onChange={e => setTrials(Number(e.target.value))} disabled={running}>
              {[1, 2, 3, 5, 10].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            <span className="hint" style={{ margin: 0 }}>
              {trials > 1 ? `${scenarios.length * trials} runs — repeats reveal flaky behaviour` : 'Use 3+ trials to measure flakiness'}
            </span>
          </div>
          <div className="btn-row">
            {running && job && (
              <button className="btn btn-danger" onClick={() => cancelJob(job.id).catch(err => toast(errorMessage(err), 'error'))}>
                ■ Cancel
              </button>
            )}
            {!running && failedScenarioIds.length > 0 && (
              <button className="btn btn-ghost" onClick={() => launch(failedScenarioIds)} disabled={starting}>
                ↻ Re-run {failedScenarioIds.length} failed/errored
              </button>
            )}
            <button id="run-tests-btn" className="btn btn-primary" onClick={() => launch()} disabled={running || starting || !scenarios.length}>
              {running ? <><span className="spinner spinner-sm" /> Running…</> : starting ? 'Starting…' : '▶ Run All Scenarios'}
            </button>
          </div>
        </div>

        {p && (
          <div style={{ marginTop: '1.25rem' }}>
            <div className="progress-track" aria-label="Run progress">
              <div className="progress-pass" style={{ width: `${p.total ? (p.passed / p.total) * 100 : 0}%` }} />
              <div className="progress-fail" style={{ width: `${p.total ? (p.failed / p.total) * 100 : 0}%` }} />
              <div className="progress-error" style={{ width: `${p.total ? ((p.errored ?? 0) / p.total) * 100 : 0}%` }} />
            </div>
            <div className="row-between muted-sm" style={{ marginTop: '0.5rem' }}>
              <span>
                <strong style={{ color: 'var(--text)' }}>{p.completed}/{p.total}</strong> runs ·{' '}
                <span style={{ color: 'var(--success)' }}>{p.passed} passed</span> ·{' '}
                <span style={{ color: 'var(--danger)' }}>{p.failed} failed</span>
                {(p.errored ?? 0) > 0 && <> · <span title="Rate limits / API errors — not counted in the score">{p.errored} errored</span></>}
                {job && !running && <> · v{job.agent_version} · {new Date(job.created_at).toLocaleString()}</>}
              </span>
              <span>{running ? `${pct}%${elapsed != null ? ` · ${elapsed}s` : ''}` : p.status}</span>
            </div>
          </div>
        )}
      </div>

      <div className="tabs">
        <button className={`tab ${tab === 'results' ? 'active' : ''}`} onClick={() => setTab('results')}>
          Results {runs.length > 0 && <span className="tab-count">{runs.length}</span>}
        </button>
        <button className={`tab ${tab === 'scenarios' ? 'active' : ''}`} onClick={() => setTab('scenarios')}>
          Scenarios <span className="tab-count">{scenarios.length}</span>
        </button>
      </div>

      {tab === 'results' && (
        <div className="card static">
          {!runs.length && !running && (
            <div className="empty" style={{ padding: '2.5rem 1rem' }}>
              <div className="empty-icon">🧪</div>
              <p>No runs yet. Press <strong>Run All Scenarios</strong> — results stream in live as each scenario finishes.</p>
            </div>
          )}
          {!runs.length && running && (
            <div className="center-pad"><span className="spinner" /><p className="muted-sm" style={{ marginTop: '1rem' }}>Running scenarios through the sandbox…</p></div>
          )}
          {runs.length > 0 && (
            <>
              <div className="row-between" style={{ marginBottom: '1rem' }}>
                <div className="segmented">
                  {(['all', 'failed', 'passed', 'errored'] as Filter[]).filter(f => f !== 'errored' || runs.some(isInfraError)).map(f => (
                    <button key={f} className={filter === f ? 'active' : ''} onClick={() => setFilter(f)}>
                      {f} ({runs.filter(r => matches(r, f)).length})
                    </button>
                  ))}
                </div>
                <Link className="link-btn" to={`/agents/${agentId}/report`}>View full report →</Link>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {visible.map(run => (
                  <RunRow key={run.id} run={run} expanded={expanded === run.id}
                    onToggle={() => setExpanded(expanded === run.id ? null : run.id!)} />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'scenarios' && (
        <div className="card static">
          <div className="row-between" style={{ flexWrap: 'wrap', gap: '0.75rem', marginBottom: '1rem' }}>
            <div className="btn-row" style={{ alignItems: 'center' }}>
              <input className="form-input" style={{ width: 70 }} type="number" min={1} max={25} value={genCount}
                onChange={e => setGenCount(Math.max(1, Math.min(25, Number(e.target.value) || 1)))} aria-label="How many to generate" />
              <input className="form-input" style={{ width: 240 }} placeholder="Focus (optional), e.g. prompt injection"
                value={genFocus} onChange={e => setGenFocus(e.target.value)} />
              <button className="btn btn-ghost btn-sm" onClick={handleGenerate} disabled={generating}>
                {generating ? <><span className="spinner spinner-sm" /> Generating…</> : '✨ Generate more'}
              </button>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowAdd(v => !v)}>{showAdd ? 'Close' : '+ Write a scenario'}</button>
          </div>

          {showAdd && agent && (
            <AddScenarioForm agent={agent} onAdded={s => setScenarios(prev => [...prev, s])} onClose={() => setShowAdd(false)} />
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {scenarios.map(s => (
              <div key={s.id} className="scenario-row">
                <span className={`badge ${s.is_adversarial ? 'badge-warn' : 'badge-neutral'}`}>{s.scenario_type}</span>
                <span className={`badge ${levelClass(s.pressure_level)}`} title="Pressure level">L{s.pressure_level}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>
                    {s.title} {s.source === 'manual' && <span className="badge badge-purple" style={{ marginLeft: 6 }}>manual</span>}
                  </div>
                  <div className="muted-sm" style={{ marginTop: '0.2rem' }}>{s.description}</div>
                  {s.expected_outcome && <div className="muted-sm" style={{ marginTop: '0.2rem' }}>✓ Expected: {s.expected_outcome}</div>}
                  {Object.keys(s.injected_tool_outputs ?? {}).length > 0 && (
                    <div style={{ marginTop: '0.3rem', fontSize: '0.75rem', color: 'var(--danger)' }}>
                      ⚠ Injection via {Object.keys(s.injected_tool_outputs).join(', ')}: “{Object.values(s.injected_tool_outputs)[0].slice(0, 90)}”
                    </div>
                  )}
                </div>
                <div className="btn-row">
                  <button className="link-btn" disabled={running} onClick={() => launch([s.id!])} title="Run just this scenario">▶ Run</button>
                  <button className="icon-btn" aria-label={`Delete ${s.title}`} onClick={() => handleDeleteScenario(s)}>✕</button>
                </div>
              </div>
            ))}
          </div>
          {!scenarios.length && <p className="muted-sm">No scenarios yet — generate some above or write your own.</p>}
        </div>
      )}
    </div>
  )
}

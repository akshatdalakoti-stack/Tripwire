import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  compareVersions, errorMessage, exportUrl, gateUrl, getAgent, getGuardrailResults, getScoreHistory,
  getScorecard, getVariance, runGuardrails,
} from '../api/client'
import type {
  AgentConfig, CompareResult, FailureMode, GuardrailSnapshot, ReliabilityReport, VarianceResult,
} from '../types'
import FailureBadge, { FAILURE_CONFIG } from '../components/FailureBadge'
import ReliabilityChart, { type HistoryPoint } from '../components/ReliabilityChart'
import BucketBars from '../components/BucketBars'
import { useToast } from '../components/Toast'

const FAILURE_MODES: FailureMode[] = ['UNSAFE_ACTION', 'TOOL_LOOP', 'HALLUCINATED_CONFIDENCE', 'GOAL_DRIFT', 'TIMEOUT', 'UNKNOWN']

const PRESSURE_LABELS: Record<string, string> = {
  '0': 'L0 benign', '1': 'L1 ambiguity', '2': 'L2 risky ask', '3': 'L3 social eng.', '4': 'L4 multi-step', '5': 'L5 injection',
}

function scoreColor(score: number) {
  return score >= 75 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)'
}

function ScoreRing({ score, grade }: { score: number; grade: string }) {
  const r = 52
  const c = 2 * Math.PI * r
  const color = scoreColor(score)
  return (
    <div className="score-ring">
      <svg width="140" height="140" viewBox="0 0 140 140" role="img" aria-label={`Reliability score ${Math.round(score)} of 100`}>
        <circle cx="70" cy="70" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="10" />
        <circle cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${(score / 100) * c} ${c}`} transform="rotate(-90 70 70)" style={{ transition: 'stroke-dasharray 1s ease' }} />
      </svg>
      <div className="score-ring-text">
        <div style={{ fontSize: '2.4rem', fontWeight: 700, lineHeight: 1, color }}>{Math.round(score)}</div>
        <div className="muted-sm">grade <strong style={{ color }}>{grade}</strong></div>
      </div>
    </div>
  )
}

export default function FailureReport() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const [agent, setAgent] = useState<AgentConfig | null>(null)
  const [version, setVersion] = useState<string | undefined>(undefined)
  const [report, setReport] = useState<ReliabilityReport | null>(null)
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [guardrails, setGuardrails] = useState<GuardrailSnapshot | null>(null)
  const [variance, setVariance] = useState<VarianceResult | null>(null)
  const [compare, setCompare] = useState<CompareResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [runningGuardrails, setRunningGuardrails] = useState(false)
  const [customProbe, setCustomProbe] = useState('')
  const [guardrailFilter, setGuardrailFilter] = useState<'all' | 'failed'>('all')
  const [copied, setCopied] = useState(false)

  const loadReport = useCallback(async (v?: string) => {
    if (!agentId) return
    // Scope flakiness to the version the scorecard resolved to, so trials from
    // different versions aren't mixed together.
    const rep = await getScorecard(agentId, v)
    const scoped = rep.versions_available.includes(rep.agent_version) ? rep.agent_version : undefined
    setReport(rep)
    setVariance(await getVariance(agentId, scoped))
  }, [agentId])

  useEffect(() => {
    if (!agentId) return
    setLoading(true)
    Promise.all([
      getAgent(agentId).then(setAgent),
      loadReport(),
      getScoreHistory(agentId).then(d =>
        setHistory((d.history ?? []).map((h: { reliability_score: number; generated_at: string; agent_version?: string }) => ({
          score: h.reliability_score,
          version: h.agent_version,
          label: new Date(h.generated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
        })))
      ),
      getGuardrailResults(agentId).then(setGuardrails),
      compareVersions(agentId).then(setCompare).catch(() => setCompare(null)),
    ])
      .catch(err => toast(errorMessage(err, 'Failed to load report'), 'error'))
      .finally(() => setLoading(false))
  }, [agentId, loadReport, toast])

  const changeVersion = async (v: string) => {
    setVersion(v)
    try { await loadReport(v) } catch (err) { toast(errorMessage(err), 'error') }
  }

  const changeCompare = async (base: string, head: string) => {
    if (!agentId) return
    try { setCompare(await compareVersions(agentId, base, head)) } catch (err) { toast(errorMessage(err), 'error') }
  }

  const handleRunGuardrails = async () => {
    if (!agentId) return
    setRunningGuardrails(true)
    try {
      const res = await runGuardrails(agentId, customProbe.trim() ? [customProbe.trim()] : [])
      setGuardrails(res)
      setCustomProbe('')
      await loadReport(version)
      toast(`Guardrails: ${res.passed}/${res.total_probes} probes refused`, res.pass_rate >= 0.8 ? 'success' : 'info')
    } catch (err) {
      toast(errorMessage(err, 'Guardrail run failed'), 'error')
    } finally {
      setRunningGuardrails(false)
    }
  }

  const gateCmd = agentId ? `curl --fail "${new URL(gateUrl(agentId), window.location.origin).href}?min_score=75&max_unsafe=0&strict=true"` : ''
  const copyGate = async () => {
    try {
      await navigator.clipboard.writeText(gateCmd)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { toast('Copy failed — select the command manually', 'error') }
  }

  if (loading) return <div className="center-pad"><span className="spinner" /></div>
  if (!report) return <div className="page"><p>Report unavailable.</p></div>

  const flaky = variance?.scenarios.filter(s => s.flakiness > 0) ?? []
  const failures = FAILURE_MODES.filter(m => (report.failure_breakdown?.[m] ?? 0) > 0)
  const shownGuardrails = (guardrails?.results ?? []).filter(r => guardrailFilter === 'all' || !r.refused)
  const versions = report.versions_available ?? []

  return (
    <div className="page fade-in">
      <div className="row-between page-head" style={{ flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title">Reliability Report</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            {agent?.name} · {report.total_scenarios} runs across {report.unique_scenarios} scenarios
          </p>
        </div>
        <div className="btn-row">
          {versions.length > 1 && (
            <select className="form-select" style={{ width: 'auto' }} value={version ?? report.agent_version}
              onChange={e => changeVersion(e.target.value)} aria-label="Agent version">
              {versions.map(v => <option key={v} value={v}>v{v}</option>)}
            </select>
          )}
          <a className="btn btn-ghost" href={exportUrl(agentId!, 'md', version)} download>⬇ Markdown</a>
          <a className="btn btn-ghost" href={exportUrl(agentId!, 'json', version)} download>⬇ JSON</a>
          <Link className="btn btn-primary" to={`/agents/${agentId}/run`}>▶ Run tests</Link>
        </div>
      </div>

      {/* ── Score + failures ── */}
      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card static">
          <h2 className="card-title">Reliability Score <span className="badge badge-purple" style={{ marginLeft: 6 }}>v{report.agent_version}</span></h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap' }}>
            <ScoreRing score={report.reliability_score} grade={report.grade} />
            <div style={{ flex: 1, minWidth: 180 }}>
              {[
                { label: 'Pass rate', value: report.score_components.base, max: 70 },
                { label: 'Guardrails', value: report.score_components.guardrail, max: 20 },
                { label: 'Coverage', value: report.score_components.diversity, max: 10 },
              ].map(c => (
                <div key={c.label} style={{ marginBottom: '0.6rem' }}>
                  <div className="row-between muted-sm"><span>{c.label}</span><span>{c.value.toFixed(1)} / {c.max}</span></div>
                  <div className="bar-track"><div className="bar-fill" style={{ width: `${(c.value / c.max) * 100}%`, background: 'var(--accent)' }} /></div>
                </div>
              ))}
            </div>
          </div>
          <div className="grid-4" style={{ marginTop: '1.25rem' }}>
            {[
              { label: 'Passed', value: report.passed, color: 'var(--success)' },
              { label: 'Failed', value: report.failed, color: 'var(--danger)' },
              { label: 'Flaky', value: report.flaky_scenarios, color: report.flaky_scenarios ? 'var(--warning)' : undefined },
              { label: 'Avg time', value: report.avg_duration_ms != null ? `${(report.avg_duration_ms / 1000).toFixed(1)}s` : '—' },
            ].map(s => (
              <div key={s.label} className="stat-card">
                <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card static">
          <h2 className="card-title">Failure Breakdown</h2>
          {failures.map(mode => {
            const count = report.failure_breakdown[mode]
            return (
              <div key={mode} className="bucket-row" style={{ marginBottom: '0.7rem' }}>
                <span style={{ minWidth: 118 }}><FailureBadge mode={mode} /></span>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${(count / (report.total_scenarios || 1)) * 100}%`, background: FAILURE_CONFIG[mode].color }} />
                </div>
                <span className="bucket-value">{count}</span>
              </div>
            )
          })}
          {!report.total_scenarios && <p className="muted-sm">No runs yet for this version.</p>}
          {report.total_scenarios > 0 && !failures.length && <p style={{ color: 'var(--success)' }}>✓ No failures — every run passed.</p>}
          {failures.length > 0 && <p className="muted-sm" style={{ marginTop: '1rem' }}>{failures.map(m => `${FAILURE_CONFIG[m].label}: ${FAILURE_CONFIG[m].hint.toLowerCase()}`).join(' · ')}</p>}
        </div>
      </div>

      {/* ── Robustness ── */}
      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card static">
          <h2 className="card-title">Robustness by Pressure Level</h2>
          <p className="muted-sm" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>How the pass rate holds up as attacks get harder.</p>
          <BucketBars buckets={report.by_pressure_level} label={k => PRESSURE_LABELS[k] ?? `L${k}`} />
        </div>
        <div className="card static">
          <h2 className="card-title">Pass Rate by Scenario Type</h2>
          <p className="muted-sm" style={{ marginTop: '-0.5rem', marginBottom: '1rem' }}>Which kinds of tasks trip the agent up.</p>
          <BucketBars buckets={report.by_scenario_type} label={k => k.replace('_', ' ')} />
        </div>
      </div>

      {/* ── Recommendations ── */}
      {report.recommendations.length > 0 && (
        <div className="card static" style={{ marginBottom: '1.5rem' }}>
          <h2 className="card-title">💡 What to fix next</h2>
          <ol className="rec-list">
            {report.recommendations.map((r, i) => <li key={i}>{r}</li>)}
          </ol>
        </div>
      )}

      {/* ── History + compare ── */}
      <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
        <div className="card static">
          <h2 className="card-title">Score History</h2>
          <ReliabilityChart data={history} />
        </div>
        <div className="card static">
          <h2 className="card-title">Version Regression Diff</h2>
          {!compare || compare.note ? (
            <div className="muted-sm">
              <p>{compare?.note ?? 'Run tests on at least two versions to see what changed.'}</p>
              <Link className="btn btn-ghost btn-sm" style={{ marginTop: '0.75rem' }} to={`/agents/${agentId}/edit`}>Edit & bump version →</Link>
            </div>
          ) : (
            <>
              <div className="btn-row" style={{ alignItems: 'center', marginBottom: '1rem' }}>
                <select className="form-select" style={{ width: 'auto' }} value={compare.base_version}
                  onChange={e => changeCompare(e.target.value, compare.head_version)} aria-label="Base version">
                  {compare.available_versions.map(v => <option key={v} value={v}>v{v}</option>)}
                </select>
                <span className="muted-sm">→</span>
                <select className="form-select" style={{ width: 'auto' }} value={compare.head_version}
                  onChange={e => changeCompare(compare.base_version, e.target.value)} aria-label="Head version">
                  {compare.available_versions.map(v => <option key={v} value={v}>v{v}</option>)}
                </select>
                {compare.base_pass_rate != null && compare.head_pass_rate != null && (
                  <span className="muted-sm">
                    pass rate {Math.round(compare.base_pass_rate * 100)}% → <strong style={{ color: compare.head_pass_rate >= compare.base_pass_rate ? 'var(--success)' : 'var(--danger)' }}>
                      {Math.round(compare.head_pass_rate * 100)}%</strong>
                  </span>
                )}
              </div>
              <div className="btn-row" style={{ marginBottom: '0.75rem' }}>
                <span className="badge badge-fail">{compare.summary.regressed} regressed</span>
                <span className="badge badge-pass">{compare.summary.improved} improved</span>
                <span className="badge badge-neutral">{compare.summary.unchanged} unchanged</span>
                {compare.summary.new > 0 && <span className="badge badge-purple">{compare.summary.new} new</span>}
              </div>
              <div className="diff-list">
                {compare.regressed.map(e => <div key={e.scenario_id} className="diff-item diff-bad">▼ {e.title}</div>)}
                {compare.improved.map(e => <div key={e.scenario_id} className="diff-item diff-good">▲ {e.title}</div>)}
                {!compare.regressed.length && !compare.improved.length && <p className="muted-sm">No scenario changed outcome between these versions.</p>}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Flakiness ── */}
      {flaky.length > 0 && (
        <div className="card static" style={{ marginBottom: '1.5rem' }}>
          <h2 className="card-title">Flaky Scenarios <span className="muted-sm">— same input, different outcome</span></h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Scenario</th><th>Trials</th><th>Pass rate</th><th>Flakiness</th><th>Failure modes</th></tr></thead>
              <tbody>
                {flaky.slice(0, 15).map(s => (
                  <tr key={s.scenario_id}>
                    <td>{s.title}{s.pressure_level != null && <span className="muted-sm"> · L{s.pressure_level}</span>}</td>
                    <td>{s.trials}</td>
                    <td>{Math.round(s.pass_rate * 100)}%</td>
                    <td>
                      <div className="bar-track" style={{ width: 80, display: 'inline-block', verticalAlign: 'middle' }}>
                        <div className="bar-fill" style={{ width: `${s.flakiness * 100}%`, background: 'var(--warning)' }} />
                      </div>
                    </td>
                    <td className="muted-sm">{Object.entries(s.failure_modes).filter(([m]) => m !== 'PASS').map(([m, n]) => `${FAILURE_CONFIG[m as FailureMode]?.label ?? m} ×${n}`).join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Guardrails ── */}
      <div className="card static" style={{ marginBottom: '1.5rem' }}>
        <div className="row-between" style={{ marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h2 className="card-title" style={{ margin: 0 }}>
            Guardrail Probes
            {guardrails && guardrails.results.length > 0 && (
              <span style={{ marginLeft: '0.75rem', fontSize: '0.85rem', color: guardrails.pass_rate >= 0.8 ? 'var(--success)' : 'var(--danger)' }}>
                {Math.round(guardrails.pass_rate * 100)}% refused
              </span>
            )}
          </h2>
          <div className="btn-row" style={{ alignItems: 'center' }}>
            <input className="form-input" style={{ width: 280 }} placeholder="Add your own attack prompt (optional)"
              value={customProbe} onChange={e => setCustomProbe(e.target.value)} />
            <button className="btn btn-ghost" onClick={handleRunGuardrails} disabled={runningGuardrails}>
              {runningGuardrails ? <><span className="spinner spinner-sm" /> Probing…</> : '⚡ Run Probes'}
            </button>
          </div>
        </div>

        {!guardrails?.results?.length ? (
          <p className="muted-sm">No guardrail results yet. Run the probes to test refusals against social engineering, prompt injection, jailbreaks, data exfiltration and the agent's own destructive tools.</p>
        ) : (
          <div className="grid-guard">
            <div>
              <div className="code-label" style={{ marginBottom: '0.75rem' }}>By attack category</div>
              <BucketBars buckets={guardrails.by_category ?? report.guardrail_by_category} label={k => k.replace(/_/g, ' ')} />
            </div>
            <div>
              <div className="row-between" style={{ marginBottom: '0.75rem' }}>
                <span className="code-label">Responses</span>
                <div className="segmented">
                  <button className={guardrailFilter === 'all' ? 'active' : ''} onClick={() => setGuardrailFilter('all')}>all</button>
                  <button className={guardrailFilter === 'failed' ? 'active' : ''} onClick={() => setGuardrailFilter('failed')}>
                    failed ({guardrails.results.filter(r => !r.refused).length})
                  </button>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: 460, overflowY: 'auto' }}>
                {shownGuardrails.map((r, i) => (
                  <div key={i} className="probe" style={{ borderColor: r.refused ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.35)' }}>
                    <div className="row-between" style={{ marginBottom: '0.3rem', gap: '0.5rem' }}>
                      <span className="muted-sm" style={{ fontStyle: 'italic' }}>“{r.probe}”</span>
                      <span className={`badge ${r.refused ? 'badge-pass' : 'badge-fail'}`}>{r.refused ? 'refused' : 'complied'}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem' }}>{r.response_snippet.slice(0, 220)}{r.response_snippet.length > 220 ? '…' : ''}</div>
                    <div className="muted-sm" style={{ marginTop: '0.3rem', fontSize: '0.72rem' }}>
                      {r.category?.replace(/_/g, ' ')} · judged by {r.verdict_source?.replace('_', ' ')}{r.reason ? ` — ${r.reason}` : ''}
                    </div>
                  </div>
                ))}
                {!shownGuardrails.length && <p style={{ color: 'var(--success)' }}>✓ The agent refused every probe.</p>}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── CI gate ── */}
      <div className="card static">
        <h2 className="card-title">Use it as a CI/CD gate</h2>
        <p className="muted-sm" style={{ marginBottom: '0.75rem' }}>
          Fail a deploy when this agent drops below the bar. The command exits non-zero (HTTP 412) when a check fails.
        </p>
        <div className="code-copy">
          <pre className="code" style={{ margin: 0 }}>{gateCmd}</pre>
          <button className="btn btn-ghost btn-sm" onClick={copyGate}>{copied ? '✓ Copied' : 'Copy'}</button>
        </div>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <button className="btn btn-ghost" onClick={() => navigate('/')}>← Dashboard</button>
      </div>
    </div>
  )
}

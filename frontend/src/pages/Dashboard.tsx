import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cloneAgent, deleteAgent, errorMessage, listAgents } from '../api/client'
import type { AgentSummary } from '../types'
import { useToast } from '../components/Toast'

function timeAgo(iso: string | null): string {
  if (!iso) return 'never'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function ScorePill({ score, grade }: { score: number | null; grade: string | null }) {
  if (score == null) return <span className="score-pill score-none">no score</span>
  const cls = score >= 75 ? 'score-good' : score >= 50 ? 'score-mid' : 'score-bad'
  return <span className={`score-pill ${cls}`} title="Latest reliability score">{Math.round(score)}{grade && <small> {grade}</small>}</span>
}

export default function Dashboard() {
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<'recent' | 'score' | 'name'>('recent')
  const navigate = useNavigate()
  const toast = useToast()

  const load = () => listAgents()
    .then(setAgents)
    .catch(err => toast(errorMessage(err, 'Could not reach the API'), 'error'))
    .finally(() => setLoading(false))

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async (a: AgentSummary) => {
    if (!confirm(`Delete "${a.name}" and all of its scenarios, runs and reports? This cannot be undone.`)) return
    try {
      await deleteAgent(a.id!)
      setAgents(prev => prev.filter(x => x.id !== a.id))
      toast('Agent deleted', 'success')
    } catch (err) {
      toast(errorMessage(err), 'error')
    }
  }

  const handleClone = async (a: AgentSummary) => {
    try {
      await cloneAgent(a.id!)
      toast(`Cloned "${a.name}"`, 'success')
      load()
    } catch (err) {
      toast(errorMessage(err), 'error')
    }
  }

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = agents.filter(a => !q || `${a.name} ${a.domain}`.toLowerCase().includes(q))
    if (sort === 'score') return [...list].sort((a, b) => (b.latest_score ?? -1) - (a.latest_score ?? -1))
    if (sort === 'name') return [...list].sort((a, b) => a.name.localeCompare(b.name))
    return list
  }, [agents, query, sort])

  const tested = agents.filter(a => a.latest_score != null)
  const avg = tested.length ? tested.reduce((s, a) => s + (a.latest_score ?? 0), 0) / tested.length : null
  const totalRuns = agents.reduce((s, a) => s + a.run_count, 0)
  const atRisk = tested.filter(a => (a.latest_score ?? 100) < 60).length

  return (
    <div className="page fade-in">
      <div className="row-between page-head">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub" style={{ marginBottom: 0 }}>Manage your AI agents and their reliability status</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/agents/new')}>+ New Agent</button>
      </div>

      {agents.length > 0 && (
        <div className="grid-4" style={{ marginBottom: '2rem' }}>
          {[
            { label: 'Agents', value: agents.length },
            { label: 'Avg score', value: avg != null ? Math.round(avg) : '—' },
            { label: 'Total runs', value: totalRuns },
            { label: 'Below 60', value: atRisk, color: atRisk ? 'var(--danger)' : undefined },
          ].map(s => (
            <div key={s.label} className="card static stat-card">
              <div className="stat-value" style={{ color: s.color }}>{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {agents.length > 1 && (
        <div className="row-between" style={{ marginBottom: '1.25rem', gap: '1rem' }}>
          <input className="form-input" style={{ maxWidth: 320 }} placeholder="Search agents…" value={query}
            onChange={e => setQuery(e.target.value)} aria-label="Search agents" />
          <div className="segmented">
            {(['recent', 'score', 'name'] as const).map(s => (
              <button key={s} className={sort === s ? 'active' : ''} onClick={() => setSort(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {loading && <div className="center-pad"><span className="spinner" /></div>}

      {!loading && !agents.length && (
        <div className="card empty fade-in">
          <div className="empty-icon">🤖</div>
          <h3 style={{ fontSize: '1.25rem', color: 'var(--text)', marginBottom: '0.5rem' }}>No agents yet</h3>
          <p style={{ marginBottom: '1.5rem' }}>Create your first AI agent to start monitoring its reliability.</p>
          <button className="btn btn-primary" onClick={() => navigate('/agents/new')}>Create Agent</button>
        </div>
      )}

      <div className="grid-2">
        {shown.map(agent => (
          <div
            key={agent.id}
            className="card clickable fade-in"
            style={{ display: 'flex', flexDirection: 'column' }}
            onClick={() => navigate(`/agents/${agent.id}/report`)}
          >
            <div className="row-between" style={{ alignItems: 'flex-start', marginBottom: '1rem', gap: '1rem' }}>
              <div style={{ minWidth: 0 }}>
                <h3 style={{ fontWeight: 600, fontSize: '1.25rem', color: 'var(--text)' }}>{agent.name}</h3>
                <div style={{ color: 'var(--accent)', fontSize: '0.9rem', marginTop: '0.25rem', fontWeight: 500 }}>
                  {agent.domain} <span className="muted-sm">· v{agent.version}</span>
                </div>
              </div>
              <ScorePill score={agent.latest_score} grade={agent.latest_grade} />
            </div>

            <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: 1.6, flexGrow: 1 }}>
              {agent.system_prompt.slice(0, 120)}{agent.system_prompt.length > 120 ? '…' : ''}
            </p>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
              {agent.tools.map(t => (
                <span key={t.name} className={`badge ${t.is_destructive ? 'badge-fail' : 'badge-neutral'}`}>{t.name}</span>
              ))}
            </div>

            <div className="muted-sm" style={{ marginBottom: '1rem' }}>
              {agent.scenario_count} scenarios · {agent.run_count} runs
              {agent.pass_rate != null && <> · {Math.round(agent.pass_rate * 100)}% pass</>} · last run {timeAgo(agent.last_run_at)}
            </div>

            <hr className="divider" style={{ margin: '0 0 1.25rem 0' }} />

            <div style={{ display: 'flex', gap: '0.5rem' }} onClick={e => e.stopPropagation()}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => navigate(`/agents/${agent.id}/run`)}>Run Tests</button>
              <button className="btn btn-ghost" onClick={() => navigate(`/agents/${agent.id}/report`)}>Report</button>
              <button className="btn btn-ghost" title="Edit" aria-label={`Edit ${agent.name}`} onClick={() => navigate(`/agents/${agent.id}/edit`)}>✎</button>
              <button className="btn btn-ghost" title="Clone" aria-label={`Clone ${agent.name}`} onClick={() => handleClone(agent)}>⧉</button>
              <button className="btn btn-danger" title="Delete" aria-label={`Delete ${agent.name}`} onClick={() => handleDelete(agent)}>✕</button>
            </div>
          </div>
        ))}
      </div>
      {!loading && agents.length > 0 && !shown.length && <p className="muted-sm">No agents match “{query}”.</p>}
    </div>
  )
}

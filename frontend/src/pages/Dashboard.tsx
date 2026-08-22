import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listAgents, deleteAgent } from '../api/client'
import type { AgentConfig } from '../types'

export default function Dashboard() {
  const [agents, setAgents] = useState<AgentConfig[]>([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    listAgents().then(setAgents).finally(() => setLoading(false))
  }, [])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this agent?')) return
    await deleteAgent(id)
    setAgents(prev => prev.filter(a => a.id !== id))
  }

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">All registered agents and their reliability status</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/agents/new')}>
          + New Agent
        </button>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: '3rem' }}><span className="spinner" /></div>}

      {!loading && !agents.length && (
        <div className="card empty">
          <div className="empty-icon">🤖</div>
          <p>No agents yet. Create your first agent to get started.</p>
          <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={() => navigate('/agents/new')}>
            Create Agent
          </button>
        </div>
      )}

      <div className="grid-2">
        {agents.map(agent => (
          <div
            key={agent.id}
            className="card"
            style={{ cursor: 'pointer', transition: 'border-color 0.2s' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '1rem' }}>{agent.name}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.1rem' }}>{agent.domain}</div>
              </div>
              <span style={{ background: 'var(--surface-2)', padding: '0.2rem 0.6rem', borderRadius: 99, fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                v{agent.version}
              </span>
            </div>

            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem', lineHeight: 1.5 }}>
              {agent.system_prompt.slice(0, 100)}{agent.system_prompt.length > 100 ? '…' : ''}
            </p>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {agent.tools.map(t => (
                <span key={t.name} className={`badge ${t.is_destructive ? 'badge-fail' : 'badge-neutral'}`}>
                  {t.name}
                </span>
              ))}
            </div>

            <hr className="divider" />

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => navigate(`/agents/${agent.id}/run`)}>
                Run Tests
              </button>
              <button className="btn btn-ghost" onClick={() => navigate(`/agents/${agent.id}/report`)}>
                Report
              </button>
              <button className="btn btn-danger" onClick={e => handleDelete(agent.id!, e)}>
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

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
    if (!confirm('Are you sure you want to delete this agent?')) return
    await deleteAgent(id)
    setAgents(prev => prev.filter(a => a.id !== id))
  }

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '3rem' }}>
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">Manage your AI agents and their reliability status</p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/agents/new')}>
          + New Agent
        </button>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: '4rem' }}><span className="spinner" /></div>}

      {!loading && !agents.length && (
        <div className="card empty fade-in">
          <div className="empty-icon">🤖</div>
          <h3 style={{ fontSize: '1.25rem', color: 'var(--text)', marginBottom: '0.5rem' }}>No agents yet</h3>
          <p style={{ marginBottom: '1.5rem' }}>Create your first AI agent to start monitoring its reliability.</p>
          <button className="btn btn-primary" onClick={() => navigate('/agents/new')}>
            Create Agent
          </button>
        </div>
      )}

      <div className="grid-2">
        {agents.map(agent => (
          <div
            key={agent.id}
            className="card fade-in"
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column' }}
            onClick={() => navigate(`/agents/${agent.id}/report`)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
              <div>
                <h3 style={{ fontWeight: 600, fontSize: '1.25rem', color: 'var(--text)' }}>{agent.name}</h3>
                <div style={{ color: 'var(--accent)', fontSize: '0.9rem', marginTop: '0.25rem', fontWeight: 500 }}>
                  {agent.domain}
                </div>
              </div>
              <span style={{ background: 'var(--surface-2)', padding: '0.3rem 0.75rem', borderRadius: 99, fontSize: '0.8rem', color: 'var(--text)', fontWeight: 500 }}>
                v{agent.version}
              </span>
            </div>

            <p style={{ fontSize: '0.95rem', color: 'var(--text-muted)', marginBottom: '1.5rem', lineHeight: 1.6, flexGrow: 1 }}>
              {agent.system_prompt.slice(0, 120)}{agent.system_prompt.length > 120 ? '…' : ''}
            </p>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
              {agent.tools.map(t => (
                <span key={t.name} className={`badge ${t.is_destructive ? 'badge-fail' : 'badge-neutral'}`}>
                  {t.name}
                </span>
              ))}
            </div>

            <hr className="divider" style={{ margin: '0 0 1.5rem 0' }} />

            <div style={{ display: 'flex', gap: '0.75rem' }} onClick={e => e.stopPropagation()}>
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

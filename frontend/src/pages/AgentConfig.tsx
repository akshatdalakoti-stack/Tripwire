import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createAgent, generateScenarios } from '../api/client'
import type { AgentConfig, ToolDefinition } from '../types'

const EMPTY_TOOL: ToolDefinition = { name: '', description: '', is_destructive: false }

export default function AgentConfig() {
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState<Omit<AgentConfig, 'id' | 'created_at'>>({
    name: '',
    domain: '',
    system_prompt: '',
    tools: [],
    version: '1.0.0',
  })

  const set = (key: string, val: unknown) => setForm(f => ({ ...f, [key]: val }))

  const addTool = () => set('tools', [...form.tools, { ...EMPTY_TOOL }])
  const removeTool = (i: number) => set('tools', form.tools.filter((_, idx) => idx !== i))
  const setTool = (i: number, key: keyof ToolDefinition, val: unknown) =>
    set('tools', form.tools.map((t, idx) => idx === i ? { ...t, [key]: val } : t))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const agent = await createAgent(form)
      await generateScenarios(agent.id!, 10)
      navigate(`/agents/${agent.id}/run`)
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to create agent. Check console.'
      alert(`Error: ${msg}`)
      console.error(err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page fade-in" style={{ maxWidth: 700 }}>
      <h1 className="page-title">New Agent</h1>
      <p className="page-sub">Define your agent and we'll generate test scenarios automatically</p>

      <form onSubmit={handleSubmit}>
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h2 className="card-title">Agent Details</h2>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Name</label>
              <input id="agent-name" className="form-input" required placeholder="Customer Support Bot"
                value={form.name} onChange={e => set('name', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Version</label>
              <input id="agent-version" className="form-input" placeholder="1.0.0"
                value={form.version} onChange={e => set('version', e.target.value)} />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Domain</label>
            <input id="agent-domain" className="form-input" required placeholder="E-commerce customer support"
              value={form.domain} onChange={e => set('domain', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="form-label">System Prompt</label>
            <textarea id="agent-prompt" className="form-textarea" required
              placeholder="You are a helpful customer support agent..."
              value={form.system_prompt} onChange={e => set('system_prompt', e.target.value)} />
          </div>
        </div>

        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 className="card-title" style={{ margin: 0 }}>Tools</h2>
            <button type="button" className="btn btn-ghost" onClick={addTool}>+ Add Tool</button>
          </div>

          {!form.tools.length && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No tools added. Agents without tools will still be tested for prompt safety.</p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {form.tools.map((tool, i) => (
              <div key={i} style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '0.9rem' }}>
                <div className="grid-2" style={{ marginBottom: '0.5rem' }}>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Tool Name</label>
                    <input className="form-input" required placeholder="send_email"
                      value={tool.name} onChange={e => setTool(i, 'name', e.target.value)} />
                  </div>
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label className="form-label">Description</label>
                    <input className="form-input" required placeholder="Sends an email to the user"
                      value={tool.description} onChange={e => setTool(i, 'description', e.target.value)} />
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                    <input type="checkbox" checked={tool.is_destructive}
                      onChange={e => setTool(i, 'is_destructive', e.target.checked)} />
                    <span style={{ color: tool.is_destructive ? 'var(--danger)' : 'var(--text-muted)' }}>
                      Destructive (irreversible)
                    </span>
                  </label>
                  <button type="button" onClick={() => removeTool(i)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1rem' }}>
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        <button id="create-agent-btn" type="submit" className="btn btn-primary" disabled={saving} style={{ width: '100%', justifyContent: 'center', padding: '0.8rem' }}>
          {saving ? <><span className="spinner" /> Creating & Generating Scenarios…</> : 'Create Agent & Generate Scenarios →'}
        </button>
      </form>
    </div>
  )
}

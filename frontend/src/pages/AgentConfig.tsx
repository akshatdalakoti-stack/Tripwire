import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createAgent, errorMessage, generateScenarios, type AgentInput } from '../api/client'
import AgentForm from '../components/AgentForm'
import { useToast } from '../components/Toast'

const BLANK: AgentInput = { name: '', domain: '', system_prompt: '', tools: [], version: '1.0.0' }

export default function AgentConfig() {
  const navigate = useNavigate()
  const toast = useToast()
  const [saving, setSaving] = useState(false)
  const [count, setCount] = useState(6)

  const handleSubmit = async (form: AgentInput) => {
    setSaving(true)
    let agentId: string | undefined
    try {
      const agent = await createAgent(form)
      agentId = agent.id
      const res = await generateScenarios(agent.id!, count)
      toast(`Agent created with ${res.generated} scenarios`, 'success')
      navigate(`/agents/${agent.id}/run`)
    } catch (err) {
      if (agentId) {
        // The agent exists; only generation failed. Let the user retry from the run page.
        toast(`Agent created, but scenario generation failed: ${errorMessage(err)}`, 'error')
        navigate(`/agents/${agentId}/run`)
      } else {
        toast(`Failed to create agent: ${errorMessage(err)}`, 'error')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page fade-in" style={{ maxWidth: 760 }}>
      <h1 className="page-title">New Agent</h1>
      <p className="page-sub">Define your agent and we'll generate test scenarios automatically</p>

      <AgentForm
        initial={BLANK}
        showExamples
        busy={saving}
        onSubmit={handleSubmit}
        submitLabel="Create Agent & Generate Scenarios →"
        busyLabel="Creating & generating scenarios…"
        footer={
          <div className="card static" style={{ marginBottom: '1.5rem' }}>
            <div className="row-between">
              <label className="form-label" htmlFor="scenario-count" style={{ margin: 0 }}>Scenarios to generate</label>
              <strong>{count}</strong>
            </div>
            <input id="scenario-count" type="range" min={1} max={20} value={count}
              onChange={e => setCount(Number(e.target.value))} style={{ width: '100%', marginTop: '0.5rem' }} />
            <span className="hint">Each scenario costs a few LLM calls per run. Start small on a free API key — you can generate more later.</span>
          </div>
        }
      />
    </div>
  )
}

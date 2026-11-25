import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { errorMessage, getAgent, updateAgent, type AgentInput } from '../api/client'
import AgentForm from '../components/AgentForm'
import { useToast } from '../components/Toast'

export default function AgentEdit() {
  const { agentId } = useParams<{ agentId: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const [initial, setInitial] = useState<AgentInput | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!agentId) return
    getAgent(agentId)
      .then(a => setInitial({ name: a.name, domain: a.domain, system_prompt: a.system_prompt, tools: a.tools, version: a.version }))
      .catch(err => toast(errorMessage(err, 'Agent not found'), 'error'))
  }, [agentId, toast])

  const handleSubmit = async (form: AgentInput) => {
    if (!agentId) return
    setSaving(true)
    try {
      await updateAgent(agentId, form)
      toast(form.version !== initial?.version ? `Saved as v${form.version} — re-run to compare against v${initial?.version}` : 'Agent saved', 'success')
      navigate(`/agents/${agentId}/run`)
    } catch (err) {
      toast(`Save failed: ${errorMessage(err)}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!initial) return <div className="center-pad"><span className="spinner" /></div>

  return (
    <div className="page fade-in" style={{ maxWidth: 760 }}>
      <div className="row-between" style={{ alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Edit Agent</h1>
          <p className="page-sub">Currently v{initial.version}. Scenarios and run history are kept.</p>
        </div>
        <button className="btn btn-ghost" onClick={() => navigate(-1)}>← Back</button>
      </div>
      <AgentForm
        initial={initial}
        originalVersion={initial.version}
        busy={saving}
        onSubmit={handleSubmit}
        submitLabel="Save Changes"
        busyLabel="Saving…"
      />
    </div>
  )
}

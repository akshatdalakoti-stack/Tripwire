import { useState } from 'react'
import type { TraceStep } from '../types'

function StepIcon({ action, flagged }: { action: string; flagged: boolean }) {
  if (flagged) return <span style={{ color: 'var(--danger)' }}>⚠</span>
  if (action === 'tool_call') return <span style={{ color: 'var(--accent)' }}>⚙</span>
  if (action === 'error') return <span style={{ color: 'var(--danger)' }}>✕</span>
  return <span style={{ color: 'var(--text-muted)' }}>◉</span>
}

const FLAG_LABELS: Record<string, string> = {
  destructive_action_attempted: 'destructive action',
  repeated_tool_call: 'repeated call',
  unknown_tool: 'hallucinated tool',
  execution_error: 'error',
}

function summary(step: TraceStep): string {
  if (step.action === 'tool_call') {
    const status = (step.tool_output as { status?: string } | undefined)?.status
    return `${step.tool_name}()${status ? ` → ${status}` : ''}`
  }
  const text = (step.llm_response || '').replace(/\s+/g, ' ')
  if (step.action === 'error') return text.slice(0, 80)
  return text.includes('FINAL_ANSWER:') ? `Final answer: ${text.split('FINAL_ANSWER:')[1].trim().slice(0, 70)}` : text.slice(0, 80)
}

export default function TraceViewer({ trace, keyEvidence }: { trace: TraceStep[]; keyEvidence?: string }) {
  const [open, setOpen] = useState<Set<number>>(() => new Set(trace.filter(s => s.flagged).map(s => s.step_number)))

  if (!trace.length) return <p className="muted-sm">No trace recorded.</p>

  const toggle = (n: number) => setOpen(prev => {
    const next = new Set(prev)
    if (next.has(n)) next.delete(n)
    else next.add(n)
    return next
  })
  const allOpen = open.size === trace.length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
        <span className="muted-sm">{trace.length} steps · {trace.filter(s => s.action === 'tool_call').length} tool calls</span>
        <button className="link-btn" onClick={() => setOpen(allOpen ? new Set() : new Set(trace.map(s => s.step_number)))}>
          {allOpen ? 'Collapse all' : 'Expand all'}
        </button>
      </div>
      {keyEvidence && (
        <div className="evidence"><strong>Key evidence:</strong> {keyEvidence}</div>
      )}
      {trace.map(step => (
        <div
          key={step.step_number}
          style={{
            background: step.flagged ? 'rgba(239,68,68,0.06)' : 'var(--surface)',
            border: `1px solid ${step.flagged ? '#ef444440' : 'var(--border)'}`,
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}
        >
          <button className="row-btn" onClick={() => toggle(step.step_number)} aria-expanded={open.has(step.step_number)}>
            <StepIcon action={step.action} flagged={step.flagged} />
            <span style={{ color: 'var(--text-muted)', minWidth: 24 }}>#{step.step_number}</span>
            <span style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
              {summary(step)}
            </span>
            {step.flag_reason && (
              <span className="badge badge-fail" style={{ fontSize: '0.7rem', padding: '0.15rem 0.5rem' }}>
                {FLAG_LABELS[step.flag_reason] ?? step.flag_reason}
              </span>
            )}
          </button>

          {open.has(step.step_number) && (
            <div style={{ padding: '0.75rem 0.9rem', borderTop: '1px solid var(--border)', fontSize: '0.8rem' }}>
              {step.action === 'tool_call' && (
                <>
                  <div className="code-label">Input</div>
                  <pre className="code">{JSON.stringify(step.tool_input, null, 2)}</pre>
                  <div className="code-label">Output</div>
                  <pre className="code">{JSON.stringify(step.tool_output, null, 2)}</pre>
                </>
              )}
              {step.llm_response && (
                <>
                  <div className="code-label">{step.action === 'error' ? 'Error' : 'Response'}</div>
                  <p style={{ color: 'var(--text)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{step.llm_response}</p>
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

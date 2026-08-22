import { useState } from 'react'
import type { TraceStep } from '../types'

function StepIcon({ action, flagged }: { action: string; flagged: boolean }) {
  if (flagged) return <span style={{ color: 'var(--danger)' }}>⚠</span>
  if (action === 'tool_call') return <span style={{ color: 'var(--accent)' }}>⚙</span>
  if (action === 'error') return <span style={{ color: 'var(--danger)' }}>✕</span>
  return <span style={{ color: 'var(--text-muted)' }}>◉</span>
}

export default function TraceViewer({ trace }: { trace: TraceStep[] }) {
  const [open, setOpen] = useState<number | null>(null)

  if (!trace.length) return <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No trace recorded.</p>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
      {trace.map(step => (
        <div
          key={step.step_number}
          style={{
            background: step.flagged ? 'rgba(239,68,68,0.06)' : 'var(--surface-2)',
            border: `1px solid ${step.flagged ? '#ef444430' : 'var(--border)'}`,
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}
        >
          <button
            onClick={() => setOpen(open === step.step_number ? null : step.step_number)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: '0.6rem 0.9rem',
              background: 'none',
              border: 'none',
              color: 'var(--text)',
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: '0.85rem',
            }}
          >
            <StepIcon action={step.action} flagged={step.flagged} />
            <span style={{ color: 'var(--text-muted)', minWidth: 24 }}>#{step.step_number}</span>
            <span style={{ fontWeight: 500 }}>
              {step.action === 'tool_call' ? `${step.tool_name}()` : step.action}
            </span>
            {step.flag_reason && (
              <span style={{ marginLeft: 'auto', color: 'var(--danger)', fontSize: '0.75rem' }}>
                {step.flag_reason}
              </span>
            )}
          </button>

          {open === step.step_number && (
            <div style={{ padding: '0.75rem 0.9rem', borderTop: '1px solid var(--border)', fontSize: '0.8rem' }}>
              {step.action === 'tool_call' && (
                <>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Input</div>
                  <pre style={{ background: 'var(--bg)', padding: '0.5rem', borderRadius: 6, overflowX: 'auto', color: 'var(--text)', marginBottom: '0.75rem' }}>
                    {JSON.stringify(step.tool_input, null, 2)}
                  </pre>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Output</div>
                  <pre style={{ background: 'var(--bg)', padding: '0.5rem', borderRadius: 6, overflowX: 'auto', color: 'var(--text)' }}>
                    {JSON.stringify(step.tool_output, null, 2)}
                  </pre>
                </>
              )}
              {step.llm_response && (
                <>
                  <div style={{ color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Response</div>
                  <p style={{ color: 'var(--text)', lineHeight: 1.6 }}>{step.llm_response}</p>
                </>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

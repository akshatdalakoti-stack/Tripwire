import { useEffect, useRef, useState } from 'react'
import { getJob, getRunsForAgent, jobEventsUrl } from '../api/client'
import type { Job, JobStatus, RunResult } from '../types'

const TERMINAL: JobStatus[] = ['completed', 'failed', 'cancelled', 'interrupted']

export interface JobProgress {
  status: JobStatus
  total: number
  completed: number
  passed: number
  failed: number
  error?: string | null
}

/**
 * Follows a background run job. Prefers Server-Sent Events (each run arrives
 * the moment it finishes); if the stream can't be opened it falls back to
 * polling every 2s. Runs are de-duplicated by id, so reconnects are harmless.
 */
export function useJobStream(job: Job | null, agentId: string | undefined, onDone?: (p: JobProgress) => void) {
  const [runs, setRuns] = useState<RunResult[]>([])
  const [progress, setProgress] = useState<JobProgress | null>(null)
  const seen = useRef(new Set<string>())
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  useEffect(() => {
    seen.current = new Set()
    setRuns([])
    setProgress(null)
    if (!job || !agentId) return

    let closed = false
    let es: EventSource | null = null
    let poll: ReturnType<typeof setInterval> | null = null

    const addRuns = (incoming: RunResult[]) => {
      const fresh = incoming.filter(r => r.id && !seen.current.has(r.id))
      if (!fresh.length) return
      fresh.forEach(r => seen.current.add(r.id!))
      setRuns(prev => [...prev, ...fresh])
    }

    const finish = (p: JobProgress) => {
      if (closed) return
      closed = true
      es?.close()
      if (poll) clearInterval(poll)
      setProgress(p)
      onDoneRef.current?.(p)
    }

    // Already finished: just load its runs once.
    if (TERMINAL.includes(job.status)) {
      setProgress(job)
      getRunsForAgent(agentId, { jobId: job.id }).then(rs => addRuns([...rs].reverse())).catch(() => {})
      return () => { closed = true }
    }

    const startPolling = () => {
      if (poll || closed) return
      const tick = async () => {
        try {
          const [j, rs] = await Promise.all([getJob(job.id), getRunsForAgent(agentId, { jobId: job.id })])
          addRuns([...rs].reverse())
          setProgress(j)
          if (TERMINAL.includes(j.status)) finish(j)
        } catch { /* keep trying */ }
      }
      tick()
      poll = setInterval(tick, 2000)
    }

    let errors = 0
    try {
      es = new EventSource(jobEventsUrl(job.id))
      es.addEventListener('run', e => addRuns([JSON.parse((e as MessageEvent).data)]))
      es.addEventListener('progress', e => { errors = 0; setProgress(JSON.parse((e as MessageEvent).data)) })
      es.addEventListener('done', e => finish(JSON.parse((e as MessageEvent).data)))
      es.onerror = () => {
        errors += 1
        if (errors >= 3 || es?.readyState === EventSource.CLOSED) {
          es?.close()
          startPolling()
        }
      }
    } catch {
      startPolling()
    }

    return () => {
      closed = true
      es?.close()
      if (poll) clearInterval(poll)
    }
  }, [job?.id, agentId]) // eslint-disable-line react-hooks/exhaustive-deps

  return { runs, progress }
}

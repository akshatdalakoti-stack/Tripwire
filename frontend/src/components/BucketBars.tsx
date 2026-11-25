import type { BucketStat } from '../types'

function barColor(rate: number) {
  return rate >= 0.8 ? 'var(--success)' : rate >= 0.5 ? 'var(--warning)' : 'var(--danger)'
}

/** Horizontal pass-rate bars, one per bucket (pressure level, scenario type, probe category…). */
export default function BucketBars({
  buckets, label, empty = 'No data yet.',
}: { buckets: BucketStat[]; label?: (key: string) => string; empty?: string }) {
  if (!buckets.length) return <p className="muted-sm">{empty}</p>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
      {buckets.map(b => (
        <div key={b.key} className="bucket-row" title={`${b.passed}/${b.total} passed`}>
          <span className="bucket-label">{label ? label(b.key) : b.key}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${Math.max(b.pass_rate * 100, 2)}%`, background: barColor(b.pass_rate) }} />
          </div>
          <span className="bucket-value">{Math.round(b.pass_rate * 100)}%</span>
          <span className="bucket-count">{b.passed}/{b.total}</span>
        </div>
      ))}
    </div>
  )
}

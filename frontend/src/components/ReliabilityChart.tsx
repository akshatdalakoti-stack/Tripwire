import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

export interface HistoryPoint {
  label: string
  score: number
  version?: string
}

export default function ReliabilityChart({ data }: { data: HistoryPoint[] }) {
  if (!data.length) return (
    <div className="empty" style={{ padding: '2rem' }}>
      <div className="empty-icon">📈</div>
      <p>No score history yet. Run tests to start tracking.</p>
    </div>
  )

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
        <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
          labelStyle={{ color: 'var(--text-muted)' }}
          itemStyle={{ color: 'var(--accent)' }}
          formatter={(value, _name, item) => [
            `${Number(value).toFixed(1)}${item?.payload?.version ? ` (v${item.payload.version})` : ''}`, 'Score',
          ]}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="var(--accent)"
          strokeWidth={2}
          dot={{ fill: 'var(--accent)', r: 3 }}
          activeDot={{ r: 6 }}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

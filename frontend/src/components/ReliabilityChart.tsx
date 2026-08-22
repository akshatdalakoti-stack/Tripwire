import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

interface DataPoint {
  label: string
  score: number
}

export default function ReliabilityChart({ data }: { data: DataPoint[] }) {
  if (!data.length) return (
    <div className="empty">
      <div className="empty-icon">📈</div>
      <p>No score history yet. Run tests to start tracking.</p>
    </div>
  )

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
        <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8 }}
          labelStyle={{ color: 'var(--text-muted)' }}
          itemStyle={{ color: 'var(--accent)' }}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="var(--accent)"
          strokeWidth={2}
          dot={{ fill: 'var(--accent)', r: 4 }}
          activeDot={{ r: 6 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

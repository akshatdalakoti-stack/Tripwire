import { Link, useLocation } from 'react-router-dom'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/agents/new', label: 'New Agent' },
]

export default function Navbar() {
  const { pathname } = useLocation()

  return (
    <nav style={{
      background: 'rgba(9,9,15,0.85)',
      backdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--border)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{
        maxWidth: 1100,
        margin: '0 auto',
        padding: '0 1.5rem',
        height: 56,
        display: 'flex',
        alignItems: 'center',
        gap: '2rem',
      }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.2rem' }}>🪤</span>
          <span style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em' }}>Tripwire</span>
        </Link>

        <div style={{ display: 'flex', gap: '0.25rem', marginLeft: 'auto' }}>
          {links.map(l => (
            <Link
              key={l.to}
              to={l.to}
              style={{
                padding: '0.4rem 0.9rem',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.875rem',
                fontWeight: 500,
                color: pathname === l.to ? 'var(--accent)' : 'var(--text-muted)',
                background: pathname === l.to ? 'var(--accent-glow)' : 'transparent',
                transition: 'all 0.15s',
              }}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}

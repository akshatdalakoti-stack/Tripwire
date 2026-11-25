import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getMeta } from '../api/client'
import type { Meta } from '../types'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/agents/new', label: 'New Agent' },
]

export default function Navbar() {
  const { pathname } = useLocation()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    getMeta().then(setMeta).catch(() => setOffline(true))
  }, [])

  return (
    <nav className="nav">
      <div className="nav-inner">
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.2rem' }}>🪤</span>
          <span style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em' }}>Tripwire</span>
        </Link>
        {meta?.mock_llm && (
          <span className="badge badge-warn" title="The backend is using the offline mock model (MOCK_LLM=1). Results are simulated.">
            mock model
          </span>
        )}
        {offline && <span className="badge badge-fail" title="Could not reach the backend API">API offline</span>}

        <div style={{ display: 'flex', gap: '0.25rem', marginLeft: 'auto' }}>
          {links.map(l => (
            <Link key={l.to} to={l.to} className={`nav-link ${pathname === l.to ? 'active' : ''}`}>{l.label}</Link>
          ))}
        </div>
      </div>
    </nav>
  )
}

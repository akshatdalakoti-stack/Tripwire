import type { ReactNode } from 'react'

export const LIMITATIONS_URL = 'https://github.com/akshatdalakoti-stack/Tripwire/blob/main/LIMITATIONS.md'

/** A short, visible warning placed next to the number it qualifies. */
export default function Caveat({ children, tone = 'warn', title }: { children: ReactNode; tone?: 'warn' | 'info'; title?: string }) {
  return (
    <div className={`caveat caveat-${tone}`} role="note">
      <span className="caveat-icon" aria-hidden>{tone === 'warn' ? '⚠' : 'ℹ'}</span>
      <div>
        {title && <strong className="caveat-title">{title}</strong>}
        <div>{children}</div>
      </div>
    </div>
  )
}

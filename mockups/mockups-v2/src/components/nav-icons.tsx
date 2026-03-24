interface IconProps {
  size?: number
  className?: string
}

export function GridIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  )
}

export function AgentIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.25" />
      <path d="M2 14c0-3.314 2.686-6 6-6s6 2.686 6 6" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  )
}

export function TaskIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <rect x="2" y="2" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.25" />
      <line x1="5" y1="6" x2="11" y2="6" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      <line x1="5" y1="9" x2="9" y2="9" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  )
}

export function BudgetIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.25" />
      <path d="M8 4v1m0 6v1M6 8h1.5c.828 0 1.5-.448 1.5-1s-.672-1-1.5-1S6 5.448 6 5" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  )
}

export function ApprovalIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M3 8l3.5 3.5L13 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function MessageIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <path d="M2 3h12v8H9l-3 2v-2H2V3z" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
    </svg>
  )
}

export function MeetingIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.25" />
      <line x1="5" y1="1" x2="5" y2="4" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      <line x1="11" y1="1" x2="11" y2="4" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
      <line x1="2" y1="7" x2="14" y2="7" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  )
}

export function SettingsIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.25" />
      <path d="M8 1.5v1.2M8 13.3v1.2M1.5 8h1.2M13.3 8h1.2M3.6 3.6l.85.85M11.55 11.55l.85.85M3.6 12.4l.85-.85M11.55 4.45l.85-.85" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
    </svg>
  )
}

export function SearchIcon({ size = 12, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.5" />
      <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function OrgIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <rect x="5" y="1" width="6" height="4" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="1" y="11" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="6" y="11" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <rect x="11" y="11" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.25" />
      <line x1="8" y1="5" x2="8" y2="9" stroke="currentColor" strokeWidth="1.25" />
      <line x1="3" y1="9" x2="13" y2="9" stroke="currentColor" strokeWidth="1.25" />
      <line x1="3" y1="9" x2="3" y2="11" stroke="currentColor" strokeWidth="1.25" />
      <line x1="8" y1="9" x2="8" y2="11" stroke="currentColor" strokeWidth="1.25" />
      <line x1="13" y1="9" x2="13" y2="11" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  )
}

export function MenuIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <line x1="2" y1="4" x2="14" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="2" y1="8" x2="14" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="2" y1="12" x2="14" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function ProviderIcon({ size = 15, className }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" className={className}>
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.25" />
      <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.25" />
      <line x1="8" y1="2.5" x2="8" y2="5.5" stroke="currentColor" strokeWidth="1.25" />
      <line x1="8" y1="10.5" x2="8" y2="13.5" stroke="currentColor" strokeWidth="1.25" />
      <line x1="2.5" y1="8" x2="5.5" y2="8" stroke="currentColor" strokeWidth="1.25" />
      <line x1="10.5" y1="8" x2="13.5" y2="8" stroke="currentColor" strokeWidth="1.25" />
    </svg>
  )
}

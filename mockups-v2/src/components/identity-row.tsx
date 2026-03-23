import type { ReactNode } from "react"

interface IdentityRowProps {
  label: string
  value: ReactNode
}

export function IdentityRow({ label, value }: IdentityRowProps) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="text-xs text-text-primary">{value}</span>
    </div>
  )
}

import type { ReactNode } from "react"

interface IdentityRowProps {
  label: string
  value: ReactNode
}

export function IdentityRow({ label, value }: IdentityRowProps) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 min-w-0">
      <span className="text-xs text-text-muted shrink-0">{label}</span>
      <span className="text-xs text-text-primary min-w-0 truncate">{value}</span>
    </div>
  )
}

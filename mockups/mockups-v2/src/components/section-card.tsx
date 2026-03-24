import type { ReactNode } from "react"

interface SectionCardProps {
  label?: string
  sublabel?: string
  title?: string
  children: ReactNode
}

export function SectionCard({ label, sublabel, title, children }: SectionCardProps) {
  const heading = title ?? label

  return (
    <div className="bg-bg-card border border-border rounded-lg overflow-hidden">
      {heading && (
        <div className="px-4 py-2.5 border-b border-border flex items-baseline gap-2.5">
          {title ? (
            <span className="text-[11px] font-semibold text-text-secondary uppercase tracking-wider">
              {title}
            </span>
          ) : (
            <span className="text-[13px] font-semibold text-text-primary">
              {heading}
            </span>
          )}
          {sublabel && (
            <span className="text-[11px] text-text-muted">{sublabel}</span>
          )}
        </div>
      )}
      <div className="px-4 py-3.5">{children}</div>
    </div>
  )
}

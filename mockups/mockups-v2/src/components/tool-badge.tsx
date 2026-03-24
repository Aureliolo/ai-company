interface ToolBadgeProps {
  name: string
}

export function ToolBadge({ name }: ToolBadgeProps) {
  return (
    <span className="text-[11px] font-mono text-accent bg-accent/[0.08] border border-accent/20 px-2 py-1 rounded">
      {name}
    </span>
  )
}

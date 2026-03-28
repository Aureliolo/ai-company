interface TimestampDividerProps {
  label: string
}

export function TimestampDivider({ label }: TimestampDividerProps) {
  return (
    <div className="flex items-center gap-3 py-2" role="separator">
      <hr className="flex-1 border-border" />
      <span className="shrink-0 font-mono text-[10px] text-muted-foreground">{label}</span>
      <hr className="flex-1 border-border" />
    </div>
  )
}

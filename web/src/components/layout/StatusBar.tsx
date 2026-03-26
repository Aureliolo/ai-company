import { cn } from '@/lib/utils'

export function StatusBar() {
  return (
    <div
      className={cn(
        'flex h-8 shrink-0 items-center gap-6',
        'border-b border-border bg-background px-6',
        'text-[11px] tracking-wide font-mono',
        'text-text-secondary select-none',
      )}
    >
      <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
        SynthOrg
      </span>

      <Divider />

      <StatusItem>
        <Dot color="bg-accent" />
        <span>-- agents</span>
      </StatusItem>

      <StatusItem>
        <Dot color="bg-success" />
        <span>-- active</span>
      </StatusItem>

      <StatusItem>
        <Dot color="bg-warning" />
        <span>-- tasks</span>
      </StatusItem>

      <Divider />

      <StatusItem>
        <span className="text-muted-foreground">spend</span>
        <span className="ml-1.5 text-foreground">$--</span>
        <span className="ml-1 text-muted-foreground">today</span>
      </StatusItem>

      <div className="flex-1" />

      <StatusItem>
        <Dot color="bg-success" />
        <span className="text-muted-foreground">all systems nominal</span>
      </StatusItem>
    </div>
  )
}

function Divider() {
  return <span className="h-3 w-px shrink-0 bg-border" />
}

function Dot({ color }: { color: string }) {
  return (
    <span
      className={cn('mr-1.5 inline-block size-[5px] shrink-0 rounded-full', color)}
      aria-hidden="true"
    />
  )
}

function StatusItem({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex items-center whitespace-nowrap">{children}</span>
  )
}

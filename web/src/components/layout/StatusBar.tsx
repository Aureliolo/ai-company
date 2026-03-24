import { cn } from '@/lib/utils'

export function StatusBar() {
  return (
    <div
      className={cn(
        'flex h-8 shrink-0 items-center gap-6',
        'border-b border-surface-100 bg-surface-0 px-6',
        'text-[11px] tracking-wide font-mono',
        'text-surface-500 select-none',
      )}
    >
      <span className="text-[10px] uppercase tracking-widest text-surface-400">
        SynthOrg
      </span>

      <Divider />

      <StatusItem>
        <Dot color="bg-brand-400" />
        <span>-- agents</span>
      </StatusItem>

      <StatusItem>
        <Dot color="bg-success-500" />
        <span>-- active</span>
      </StatusItem>

      <StatusItem>
        <Dot color="bg-warning-500" />
        <span>-- tasks</span>
      </StatusItem>

      <Divider />

      <StatusItem>
        <span className="text-surface-400">spend</span>
        <span className="ml-1.5 text-surface-700">$--</span>
        <span className="ml-1 text-surface-400">today</span>
      </StatusItem>

      <div className="flex-1" />

      <StatusItem>
        <Dot color="bg-success-500" />
        <span className="text-surface-400">all systems nominal</span>
      </StatusItem>
    </div>
  )
}

function Divider() {
  return <span className="h-3 w-px shrink-0 bg-surface-100" />
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

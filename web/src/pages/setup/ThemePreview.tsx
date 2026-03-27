import { cn } from '@/lib/utils'
import { MetricCard } from '@/components/ui/metric-card'
import { AgentCard } from '@/components/ui/agent-card'
import { DeptHealthBar } from '@/components/ui/dept-health-bar'
import { Button } from '@/components/ui/button'
import { SectionCard } from '@/components/ui/section-card'
import { StatPill } from '@/components/ui/stat-pill'
import type { ThemeSettings } from '@/stores/setup-wizard'
import { BarChart3 } from 'lucide-react'

const DENSITY_CLASS: Record<string, string> = {
  dense: 'density-dense',
  balanced: 'density-medium',
  sparse: 'density-sparse',
}

export interface ThemePreviewProps {
  settings: ThemeSettings
}

export function ThemePreview({ settings }: ThemePreviewProps) {
  return (
    <div
      className={cn('space-y-4 rounded-lg border border-border bg-background p-4', DENSITY_CLASS[settings.density])}
      data-palette={settings.palette}
      data-density={settings.density}
      data-animation={settings.animation}
      data-sidebar={settings.sidebar}
      data-typography={settings.typography}
    >
      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Active Agents" value={12} />
        <MetricCard label="Tasks Today" value={47} />
      </div>

      {/* Agent card mock */}
      <AgentCard name="Akira Tanaka" role="CEO" department="executive" status="idle" />

      {/* Health bar */}
      <DeptHealthBar name="Engineering" health={72} agentCount={3} taskCount={15} />

      {/* Buttons */}
      <div className="flex flex-wrap gap-2">
        <Button size="sm">Default</Button>
        <Button variant="outline" size="sm">Outline</Button>
        <Button variant="ghost" size="sm">Ghost</Button>
        <Button variant="secondary" size="sm">Secondary</Button>
      </div>

      {/* Section card */}
      <SectionCard title="Sample Section" icon={BarChart3}>
        <p className="text-sm text-muted-foreground">
          Content with <span className="text-foreground">text-foreground</span> and{' '}
          <span className="text-compact text-muted-foreground">timestamps</span>.
        </p>
        <div className="mt-2 flex gap-2">
          <StatPill label="Agents" value={5} />
          <StatPill label="Cost" value="~45/mo" />
        </div>
      </SectionCard>
    </div>
  )
}

import { useState, useMemo } from 'react'
import { MetricCard } from '@/components/ui/metric-card'
import { ToggleField } from '@/components/ui/toggle-field'
import { SliderField } from '@/components/ui/slider-field'
import { Button } from '@/components/ui/button'
import { formatCurrency } from '@/utils/format'
import type { CostEstimate } from '@/utils/cost-estimator'
import type { SetupAgentSummary } from '@/api/types'
import { ChevronDown, ChevronRight } from 'lucide-react'

export interface CostEstimatePanelProps {
  estimate: CostEstimate | null
  currency: string
  budgetCapEnabled: boolean
  budgetCap: number | null
  agents?: readonly SetupAgentSummary[]
  onBudgetCapEnabledChange: (enabled: boolean) => void
  onBudgetCapChange: (cap: number | null) => void
}

interface AgentRowData {
  readonly name: string
  readonly modelId: string
  readonly monthlyCost: number
  readonly agentIndex: number
}

interface DepartmentGroup {
  readonly department: string
  readonly agents: readonly AgentRowData[]
  readonly subtotal: number
}

function AgentRow({ agent, currency }: { agent: AgentRowData; currency: string }) {
  return (
    <li className="flex items-center justify-between text-compact text-muted-foreground">
      <span>{agent.name} <span className="text-muted-foreground/60">({agent.modelId})</span></span>
      <span>{formatCurrency(agent.monthlyCost, currency)}</span>
    </li>
  )
}

function DepartmentGroupSection({ group, currency }: { group: DepartmentGroup; currency: string }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs font-medium text-foreground">
        <span>{group.department}</span>
        <span className="text-muted-foreground">{formatCurrency(group.subtotal, currency)}</span>
      </div>
      <ul className="space-y-0.5 pl-3">
        {group.agents.map((agent) => (
          <AgentRow key={agent.agentIndex} agent={agent} currency={currency} />
        ))}
      </ul>
    </div>
  )
}

export function CostEstimatePanel({
  estimate,
  currency,
  budgetCapEnabled,
  budgetCap,
  agents,
  onBudgetCapEnabledChange,
  onBudgetCapChange,
}: CostEstimatePanelProps) {
  const [breakdownOpen, setBreakdownOpen] = useState(false)

  // Group per-agent breakdown by department when agents are available
  const departmentGroups = useMemo((): readonly DepartmentGroup[] => {
    if (!estimate || estimate.perAgentBreakdown.length === 0) return []
    if (!agents || agents.length === 0) return []

    const groups = new Map<string, AgentRowData[]>()

    for (const entry of estimate.perAgentBreakdown) {
      const agent = agents[entry.agentIndex]
      const dept = agent?.department ?? 'Unassigned'
      const name = agent?.name ?? `Agent ${entry.agentIndex}`
      const existing = groups.get(dept)
      const item: AgentRowData = { name, modelId: entry.modelId, monthlyCost: entry.monthlyCost, agentIndex: entry.agentIndex }
      if (existing) {
        existing.push(item)
      } else {
        groups.set(dept, [item])
      }
    }

    return [...groups.entries()]
      .map(([department, deptAgents]) => ({
        department,
        agents: deptAgents,
        subtotal: deptAgents.reduce((sum, a) => sum + a.monthlyCost, 0),
      }))
      .sort((a, b) => a.department.localeCompare(b.department))
  }, [estimate, agents])

  if (!estimate) return null

  const hasBreakdown = departmentGroups.length > 0

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">Cost Estimate</h3>
        <p className="text-xs text-muted-foreground">
          Based on {estimate.assumptions.dailyTokensPerAgent.toLocaleString()} tokens/agent/day
        </p>
      </div>

      <MetricCard
        label="Estimated Monthly Cost"
        value={formatCurrency(estimate.monthlyTotal, currency)}
      />

      {/* Per-agent breakdown grouped by department */}
      {hasBreakdown && (
        <div className="border-t border-border pt-3">
          <Button
            variant="ghost"
            size="sm"
            className="flex w-full items-center justify-between text-sm text-muted-foreground"
            onClick={() => setBreakdownOpen(!breakdownOpen)}
            aria-expanded={breakdownOpen}
          >
            <span>Per-Agent Breakdown</span>
            {breakdownOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </Button>
          {breakdownOpen && (
            <div className="mt-2 space-y-3">
              {departmentGroups.map((group) => (
                <DepartmentGroupSection key={group.department} group={group} currency={currency} />
              ))}
            </div>
          )}
        </div>
      )}

      <div className="space-y-3 border-t border-border pt-3">
        <ToggleField
          label="Set a budget limit"
          description="Budget enforcement prevents agents from exceeding this limit."
          checked={budgetCapEnabled}
          onChange={(enabled) => {
            if (enabled && budgetCap === null) {
              onBudgetCapChange(Math.ceil(estimate.monthlyTotal * 2))
            }
            onBudgetCapEnabledChange(enabled)
          }}
        />
        {budgetCapEnabled && (
          <SliderField
            label="Monthly Budget Cap"
            value={budgetCap ?? Math.ceil(estimate.monthlyTotal * 2)}
            min={Math.ceil(estimate.monthlyTotal)}
            max={Math.max(Math.ceil(estimate.monthlyTotal * 10), 1000)}
            step={10}
            formatValue={(v) => formatCurrency(v, currency)}
            onChange={(v) => onBudgetCapChange(v)}
          />
        )}
      </div>

      <p className="text-compact text-muted-foreground">
        * Actual costs depend on task volume and complexity. This is a rough projection for planning purposes.
        {estimate.usedFallback && (
          <> Estimate uses average tier pricing -- actual costs depend on your model configuration.</>
        )}
      </p>
    </div>
  )
}

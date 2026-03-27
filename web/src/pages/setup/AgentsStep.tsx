import { useCallback, useEffect } from 'react'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { Skeleton } from '@/components/ui/skeleton'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { validateAgentsStep } from '@/utils/setup-validation'
import { MiniOrgChart } from './MiniOrgChart'
import { SetupAgentCard } from './SetupAgentCard'
import { Button } from '@/components/ui/button'
import { Users } from 'lucide-react'

export function AgentsStep() {
  const agents = useSetupWizardStore((s) => s.agents)
  const agentsLoading = useSetupWizardStore((s) => s.agentsLoading)
  const agentsError = useSetupWizardStore((s) => s.agentsError)
  const providers = useSetupWizardStore((s) => s.providers)
  const fetchAgents = useSetupWizardStore((s) => s.fetchAgents)
  const updateAgentName = useSetupWizardStore((s) => s.updateAgentName)
  const updateAgentModel = useSetupWizardStore((s) => s.updateAgentModel)
  const randomizeAgentName = useSetupWizardStore((s) => s.randomizeAgentName)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  // Fetch agents if not already loaded (e.g., direct URL navigation)
  useEffect(() => {
    if (agents.length === 0 && !agentsLoading && !agentsError) {
      void fetchAgents()
    }
  }, [agents.length, agentsLoading, agentsError, fetchAgents])

  // Track step completion
  useEffect(() => {
    const validation = validateAgentsStep({ agents })
    if (validation.valid) {
      markStepComplete('agents')
    } else {
      markStepIncomplete('agents')
    }
  }, [agents, markStepComplete, markStepIncomplete])

  const handleNameChange = useCallback(
    async (index: number, name: string) => {
      await updateAgentName(index, name)
    },
    [updateAgentName],
  )

  const handleModelChange = useCallback(
    async (index: number, provider: string, modelId: string) => {
      await updateAgentModel(index, provider, modelId)
    },
    [updateAgentModel],
  )

  const handleRandomizeName = useCallback(
    async (index: number) => {
      await randomizeAgentName(index)
    },
    [randomizeAgentName],
  )

  if (agentsLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 rounded-lg" />
        {Array.from({ length: 3 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
    )
  }

  if (agents.length === 0 && agentsError) {
    return (
      <div className="space-y-4">
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {agentsError}
        </div>
        <Button variant="outline" size="sm" onClick={() => void fetchAgents()}>
          Retry
        </Button>
      </div>
    )
  }

  if (agents.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No agents configured"
        description="Go back to the Company step and apply a template to generate agents."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Customize Your Agents</h2>
        <p className="text-sm text-muted-foreground">
          Adjust agent names, roles, and model assignments.
        </p>
      </div>

      {agentsError && (
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {agentsError}
        </div>
      )}

      {/* Mini org chart */}
      <MiniOrgChart agents={agents} />

      {/* Agent cards */}
      <StaggerGroup className="space-y-3">
        {agents.map((agent, index) => (
          <StaggerItem key={`agent-${index}`}>
            <SetupAgentCard
              agent={agent}
              index={index}
              providers={providers}
              onNameChange={handleNameChange}
              onModelChange={handleModelChange}
              onRandomizeName={handleRandomizeName}
            />
          </StaggerItem>
        ))}
      </StaggerGroup>
    </div>
  )
}

import { useCallback, useEffect } from 'react'
import { EmptyState } from '@/components/ui/empty-state'
import { ErrorBanner } from '@/components/ui/error-banner'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { Skeleton } from '@/components/ui/skeleton'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { validateAgentsStep } from '@/utils/setup-validation'
import { MiniOrgChart } from './MiniOrgChart'
import { SetupAgentCard } from './SetupAgentCard'
import { Users } from 'lucide-react'

export function AgentsStep() {
  const agents = useSetupWizardStore((s) => s.agents)
  const agentsLoading = useSetupWizardStore((s) => s.agentsLoading)
  const agentsError = useSetupWizardStore((s) => s.agentsError)
  const providers = useSetupWizardStore((s) => s.providers)
  const personalityPresets = useSetupWizardStore((s) => s.personalityPresets)
  const personalityPresetsLoading = useSetupWizardStore((s) => s.personalityPresetsLoading)
  const personalityPresetsError = useSetupWizardStore((s) => s.personalityPresetsError)
  const fetchAgents = useSetupWizardStore((s) => s.fetchAgents)
  const fetchPersonalityPresets = useSetupWizardStore((s) => s.fetchPersonalityPresets)
  const updateAgentName = useSetupWizardStore((s) => s.updateAgentName)
  const updateAgentModel = useSetupWizardStore((s) => s.updateAgentModel)
  const randomizeAgentName = useSetupWizardStore((s) => s.randomizeAgentName)
  const updateAgentPersonality = useSetupWizardStore((s) => s.updateAgentPersonality)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  // Fetch agents if not already loaded (e.g., direct URL navigation)
  useEffect(() => {
    if (agents.length === 0 && !agentsLoading && !agentsError) {
      void fetchAgents()
    }
  }, [agents.length, agentsLoading, agentsError, fetchAgents])

  // Fetch personality presets on mount (stop on error to avoid loop)
  useEffect(() => {
    if (
      personalityPresets.length === 0 &&
      !personalityPresetsLoading &&
      !personalityPresetsError
    ) {
      void fetchPersonalityPresets()
    }
  }, [
    personalityPresets.length,
    personalityPresetsLoading,
    personalityPresetsError,
    fetchPersonalityPresets,
  ])

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

  const handlePersonalityChange = useCallback(
    async (index: number, preset: string) => {
      await updateAgentPersonality(index, preset)
    },
    [updateAgentPersonality],
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
      <ErrorBanner
        title="Could not load agents"
        description={agentsError}
        onRetry={() => void fetchAgents()}
      />
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
    <div className="space-y-section-gap">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Customize Your Agents</h2>
        <p className="text-sm text-muted-foreground">
          Adjust agent names, personalities, and model assignments.
        </p>
      </div>

      {agentsError && (
        <ErrorBanner
          title="Could not update agent"
          description={agentsError}
          onRetry={() => void fetchAgents()}
        />
      )}

      {personalityPresetsError && (
        <ErrorBanner
          severity="warning"
          title="Could not load personality presets"
          description="Agents can still be configured without them."
          onRetry={() => void fetchPersonalityPresets()}
        />
      )}

      {/* Mini org chart */}
      <MiniOrgChart agents={agents} />

      {/* Agent cards */}
      <StaggerGroup className="space-y-3">
        {agents.map((agent, index) => (
          // eslint-disable-next-line @eslint-react/no-array-index-key -- names are user-editable and may duplicate; index as tiebreaker
          <StaggerItem key={`${agent.name}-${index}`}>
            <SetupAgentCard
              agent={agent}
              index={index}
              providers={providers}
              personalityPresets={personalityPresets}
              onNameChange={handleNameChange}
              onModelChange={handleModelChange}
              onRandomizeName={handleRandomizeName}
              onPersonalityChange={handlePersonalityChange}
            />
          </StaggerItem>
        ))}
      </StaggerGroup>
    </div>
  )
}

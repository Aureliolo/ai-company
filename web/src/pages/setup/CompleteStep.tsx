import { useCallback, useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { SkipWizardForm } from './SkipWizardForm'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { useSetupStore } from '@/stores/setup'
import { useToastStore } from '@/stores/toast'
import { estimateMonthlyCost } from '@/utils/cost-estimator'
import { MiniOrgChart } from './MiniOrgChart'
import { SetupSummary } from './SetupSummary'
import { CheckCircle } from 'lucide-react'

export function CompleteStep() {
  const navigate = useNavigate()
  const [confirmOpen, setConfirmOpen] = useState(false)

  const companyResponse = useSetupWizardStore((s) => s.companyResponse)
  const agents = useSetupWizardStore((s) => s.agents)
  const providers = useSetupWizardStore((s) => s.providers)
  const currency = useSetupWizardStore((s) => s.currency)
  const budgetCapEnabled = useSetupWizardStore((s) => s.budgetCapEnabled)
  const budgetCap = useSetupWizardStore((s) => s.budgetCap)
  const completing = useSetupWizardStore((s) => s.completing)
  const completionError = useSetupWizardStore((s) => s.completionError)
  const wizardCompleteSetup = useSetupWizardStore((s) => s.completeSetup)

  const costEstimate = useMemo(() => {
    if (agents.length === 0) return null
    return estimateMonthlyCost(
      agents.map((a) => ({
        model_provider: a.model_provider,
        model_id: a.model_id,
        tier: a.tier,
      })),
      Object.values(providers).flatMap((p) => [...p.models]),
    )
  }, [agents, providers])

  const handleComplete = useCallback(async () => {
    try {
      await wizardCompleteSetup()
    } catch {
      // Error is already stored in completionError by the store action
      return
    }
    useSetupStore.setState({ setupComplete: true })
    useToastStore.getState().add({
      variant: 'success',
      title: `Setup complete! Welcome to ${companyResponse?.company_name ?? 'your organization'}.`,
    })
    setConfirmOpen(false)
    navigate('/')
  }, [wizardCompleteSetup, companyResponse, navigate])

  if (!companyResponse) {
    return <SkipWizardForm />
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Review & Complete</h2>
        <p className="text-sm text-muted-foreground">
          Review your organization before launching.
        </p>
      </div>

      {/* Mini org chart */}
      <MiniOrgChart agents={agents} />

      {/* Summary */}
      <SetupSummary
        companyResponse={companyResponse}
        agents={agents}
        providers={providers}
        costEstimate={costEstimate}
        currency={currency}
        budgetCapEnabled={budgetCapEnabled}
        budgetCap={budgetCap}
      />

      {completionError && (
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {completionError}
        </div>
      )}

      {/* Complete button */}
      <Button
        onClick={() => setConfirmOpen(true)}
        disabled={completing}
        className="w-full gap-2"
        size="lg"
      >
        <CheckCircle className="size-4" />
        {completing ? 'Completing Setup...' : 'Complete Setup'}
      </Button>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Launch your organization?"
        description="This will start all configured agents and complete the setup process."
        confirmLabel="Launch"
        onConfirm={handleComplete}
        loading={completing}
      />
    </div>
  )
}

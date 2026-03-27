import { useCallback, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import { AnimatedPresence } from '@/components/ui/animated-presence'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import type { WizardStep } from '@/stores/setup-wizard'
import { WizardProgress } from './WizardProgress'
import { WizardNavigation } from './WizardNavigation'
import { WizardSkeleton } from './WizardSkeleton'
import { AccountStep } from './AccountStep'
import { TemplateStep } from './TemplateStep'
import { CompanyStep } from './CompanyStep'
import { AgentsStep } from './AgentsStep'
import { ProvidersStep } from './ProvidersStep'
import { ThemeStep } from './ThemeStep'
import { CompleteStep } from './CompleteStep'

const STEP_COMPONENTS: Record<WizardStep, React.ComponentType> = {
  account: AccountStep,
  template: TemplateStep,
  company: CompanyStep,
  agents: AgentsStep,
  providers: ProvidersStep,
  theme: ThemeStep,
  complete: CompleteStep,
}

function isWizardStep(value: string, stepOrder: readonly WizardStep[]): value is WizardStep {
  return stepOrder.includes(value as WizardStep)
}

export function WizardShell() {
  const navigate = useNavigate()
  const { step: urlStep } = useParams<{ step?: string }>()

  const currentStep = useSetupWizardStore((s) => s.currentStep)
  const stepOrder = useSetupWizardStore((s) => s.stepOrder)
  const stepsCompleted = useSetupWizardStore((s) => s.stepsCompleted)
  const setStep = useSetupWizardStore((s) => s.setStep)
  const canNavigateTo = useSetupWizardStore((s) => s.canNavigateTo)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)

  // Sync URL -> store on mount and URL changes
  useEffect(() => {
    if (!urlStep) {
      navigate(`/setup/${stepOrder[0]}`, { replace: true })
      return
    }
    if (isWizardStep(urlStep, stepOrder)) {
      if (canNavigateTo(urlStep)) {
        setStep(urlStep)
      } else {
        const firstIncomplete = stepOrder.find((s) => !stepsCompleted[s])
        navigate(`/setup/${firstIncomplete ?? stepOrder[0]}`, { replace: true })
      }
    } else {
      // Invalid step name in URL -- redirect to first step
      navigate(`/setup/${stepOrder[0]}`, { replace: true })
    }
  }, [urlStep, stepOrder, canNavigateTo, setStep, stepsCompleted, navigate])

  const handleStepClick = useCallback(
    (step: WizardStep) => {
      if (!canNavigateTo(step)) return
      navigate(`/setup/${step}`)
    },
    [canNavigateTo, navigate],
  )

  const handleBack = useCallback(() => {
    const idx = stepOrder.indexOf(currentStep)
    if (idx > 0) {
      navigate(`/setup/${stepOrder[idx - 1]}`)
    }
  }, [currentStep, stepOrder, navigate])

  const handleNext = useCallback(() => {
    const idx = stepOrder.indexOf(currentStep)
    if (idx < stepOrder.length - 1) {
      navigate(`/setup/${stepOrder[idx + 1]}`)
    }
  }, [currentStep, stepOrder, navigate])

  if (!urlStep) {
    return <WizardSkeleton />
  }

  const StepComponent = STEP_COMPONENTS[currentStep]

  return (
    <div className="flex min-h-screen flex-col items-center bg-background">
      <div className="w-full max-w-4xl flex-1 px-4 py-8">
        {/* Skip wizard link */}
        {(currentStep === 'account' || currentStep === 'template') && (
          <div className="mb-2 text-center">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                for (const s of stepOrder) {
                  if (s !== 'complete') markStepComplete(s)
                }
                navigate('/setup/complete')
              }}
              className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            >
              Skip wizard (advanced)
            </Button>
          </div>
        )}

        {/* Progress bar */}
        <div className="mb-8">
          <WizardProgress
            stepOrder={stepOrder}
            currentStep={currentStep}
            stepsCompleted={stepsCompleted}
            canNavigateTo={canNavigateTo}
            onStepClick={handleStepClick}
          />
        </div>

        {/* Step content */}
        <ErrorBoundary level="page">
          <AnimatedPresence routeKey={currentStep}>
            <StepComponent />
          </AnimatedPresence>
        </ErrorBoundary>

        {/* Navigation */}
        <div className="mt-8">
          <WizardNavigation
            stepOrder={stepOrder}
            currentStep={currentStep}
            onBack={handleBack}
            onNext={handleNext}
            nextDisabled={!stepsCompleted[currentStep]}
          />
        </div>
      </div>
    </div>
  )
}

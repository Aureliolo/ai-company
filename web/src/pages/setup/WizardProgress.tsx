import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { WizardStep } from '@/stores/setup-wizard'

interface StepConfig {
  readonly key: WizardStep
  readonly label: string
}

const STEP_LABELS: Record<WizardStep, string> = {
  account: 'Account',
  template: 'Template',
  company: 'Company',
  agents: 'Agents',
  providers: 'Providers',
  theme: 'Theme',
  complete: 'Done',
}

interface StepIndicatorProps {
  step: StepConfig
  index: number
  isActive: boolean
  isComplete: boolean
  isAccessible: boolean
  isLast: boolean
  onStepClick: (step: WizardStep) => void
}

function StepIndicator({
  step,
  index,
  isActive,
  isComplete,
  isAccessible,
  isLast,
  onStepClick,
}: StepIndicatorProps) {
  return (
    <div className="flex items-center">
      <button
        type="button"
        onClick={() => onStepClick(step.key)}
        disabled={!isAccessible}
        aria-current={isActive ? 'step' : undefined}
        className={cn(
          'flex flex-col items-center gap-1',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-background',
          'rounded-md px-2 py-1 transition-colors',
          isAccessible && !isActive && 'cursor-pointer hover:bg-card-hover',
          !isAccessible && 'cursor-not-allowed opacity-50',
        )}
      >
        <div
          className={cn(
            'flex size-8 items-center justify-center rounded-full text-xs font-semibold transition-colors',
            isActive && 'bg-accent text-accent-foreground',
            isComplete && !isActive && 'bg-success/20 text-success',
            !isActive && !isComplete && 'bg-card text-muted-foreground border border-border',
          )}
        >
          {isComplete ? (
            <Check className="size-4" aria-hidden="true" />
          ) : (
            index + 1
          )}
        </div>
        <span
          className={cn(
            'text-compact',
            isActive && 'font-semibold text-foreground',
            !isActive && 'text-muted-foreground',
          )}
        >
          {step.label}
        </span>
      </button>
      {!isLast && (
        <div
          className={cn(
            'mx-1 h-px w-8',
            isComplete ? 'bg-success/40' : 'bg-border',
          )}
          aria-hidden="true"
        />
      )}
    </div>
  )
}

export interface WizardProgressProps {
  stepOrder: readonly WizardStep[]
  currentStep: WizardStep
  stepsCompleted: Record<WizardStep, boolean>
  canNavigateTo: (step: WizardStep) => boolean
  onStepClick: (step: WizardStep) => void
}

export function WizardProgress({
  stepOrder,
  currentStep,
  stepsCompleted,
  canNavigateTo,
  onStepClick,
}: WizardProgressProps) {
  const steps: StepConfig[] = stepOrder.map((key) => ({
    key,
    label: STEP_LABELS[key],
  }))

  return (
    <nav aria-label="Setup progress" className="flex items-center justify-center gap-0">
      {steps.map((step, index) => (
        <StepIndicator
          key={step.key}
          step={step}
          index={index}
          isActive={step.key === currentStep}
          isComplete={stepsCompleted[step.key]}
          isAccessible={canNavigateTo(step.key)}
          isLast={index === steps.length - 1}
          onStepClick={onStepClick}
        />
      ))}
    </nav>
  )
}

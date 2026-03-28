import { useCallback, useEffect, useState } from 'react'
import { Loader2, Settings } from 'lucide-react'
import type { AutonomyLevel, CompanyConfig, UpdateCompanyRequest } from '@/api/types'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { SliderField } from '@/components/ui/slider-field'
import { Button } from '@/components/ui/button'

export interface GeneralTabProps {
  config: CompanyConfig | null
  onUpdate: (data: UpdateCompanyRequest) => Promise<void>
  saving: boolean
}

const AUTONOMY_OPTIONS = [
  { value: 'full', label: 'Full' },
  { value: 'semi', label: 'Semi-autonomous' },
  { value: 'supervised', label: 'Supervised' },
  { value: 'locked', label: 'Locked' },
] as const

const VALID_AUTONOMY_LEVELS: ReadonlySet<string> = new Set(AUTONOMY_OPTIONS.map((o) => o.value))

interface FormState {
  company_name: string
  autonomy_level: AutonomyLevel
  budget_monthly: number
  communication_pattern: string
}

const budgetFormatter = new Intl.NumberFormat('en-US', { style: 'decimal', maximumFractionDigits: 0 })

function formatBudget(value: number): string {
  return `${budgetFormatter.format(value)} EUR`
}

export function GeneralTab({ config, onUpdate, saving }: GeneralTabProps) {
  const [form, setForm] = useState<FormState>({
    company_name: '',
    autonomy_level: 'semi',
    budget_monthly: 100,
    communication_pattern: 'hybrid',
  })
  const [dirty, setDirty] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => {
    if (config && !dirty) {
      setForm({
        company_name: config.company_name,
        autonomy_level: (config.autonomy_level && VALID_AUTONOMY_LEVELS.has(config.autonomy_level))
          ? config.autonomy_level
          : 'semi',
        budget_monthly: config.budget_monthly ?? 100,
        communication_pattern: config.communication_pattern ?? 'hybrid',
      })
    }
  // eslint-disable-next-line @eslint-react/exhaustive-deps -- intentionally exclude dirty to avoid sync loop
  }, [config])

  const updateForm = useCallback(<K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }, [])

  const handleSave = useCallback(async () => {
    setSubmitError(null)
    try {
      await onUpdate({
        company_name: form.company_name.trim() || undefined,
        autonomy_level: form.autonomy_level,
        budget_monthly: form.budget_monthly,
        communication_pattern: form.communication_pattern.trim() || undefined,
      })
      setDirty(false)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to save')
    }
  }, [form, onUpdate])

  if (!config) {
    return <EmptyState icon={Settings} title="No company data" description="Company configuration is not loaded yet." />
  }

  return (
    <SectionCard title="Company Settings" icon={Settings}>
      <div className="space-y-5 max-w-xl">
        <InputField
          label="Company Name"
          value={form.company_name}
          onChange={(e) => updateForm('company_name', e.target.value)}
          required
        />

        <SelectField
          label="Autonomy Level"
          options={AUTONOMY_OPTIONS}
          value={form.autonomy_level}
          onChange={(value) => {
            if (VALID_AUTONOMY_LEVELS.has(value)) updateForm('autonomy_level', value as AutonomyLevel)
          }}
        />

        <SliderField
          label="Monthly Budget"
          value={form.budget_monthly}
          onChange={(value) => updateForm('budget_monthly', value)}
          min={0}
          max={10000}
          step={50}
          formatValue={formatBudget}
        />

        <InputField
          label="Communication Pattern"
          value={form.communication_pattern}
          onChange={(e) => updateForm('communication_pattern', e.target.value)}
          hint="e.g. hybrid, broadcast, hierarchical"
        />

        {submitError && (
          <p className="text-xs text-danger">{submitError}</p>
        )}

        <Button onClick={handleSave} disabled={!dirty || saving}>
          {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
          Save Settings
        </Button>
      </div>
    </SectionCard>
  )
}

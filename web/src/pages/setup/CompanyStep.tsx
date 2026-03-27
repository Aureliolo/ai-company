import { useCallback, useEffect, useMemo } from 'react'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { StatPill } from '@/components/ui/stat-pill'
import { MetricCard } from '@/components/ui/metric-card'
import { Button } from '@/components/ui/button'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { validateCompanyStep } from '@/utils/setup-validation'
import { estimateMonthlyCost } from '@/utils/cost-estimator'
import { CURRENCY_OPTIONS } from '@/utils/currencies'
import type { CurrencyCode } from '@/utils/currencies'
import { TemplateVariables } from './TemplateVariables'
import { CostEstimatePanel } from './CostEstimatePanel'

export function CompanyStep() {
  const templates = useSetupWizardStore((s) => s.templates)
  const selectedTemplate = useSetupWizardStore((s) => s.selectedTemplate)
  const companyName = useSetupWizardStore((s) => s.companyName)
  const companyDescription = useSetupWizardStore((s) => s.companyDescription)
  const currency = useSetupWizardStore((s) => s.currency)
  const budgetCapEnabled = useSetupWizardStore((s) => s.budgetCapEnabled)
  const budgetCap = useSetupWizardStore((s) => s.budgetCap)
  const companyResponse = useSetupWizardStore((s) => s.companyResponse)
  const companyLoading = useSetupWizardStore((s) => s.companyLoading)
  const companyError = useSetupWizardStore((s) => s.companyError)
  const templateVariables = useSetupWizardStore((s) => s.templateVariables)
  const agents = useSetupWizardStore((s) => s.agents)

  const setCompanyName = useSetupWizardStore((s) => s.setCompanyName)
  const setCompanyDescription = useSetupWizardStore((s) => s.setCompanyDescription)
  const setCurrency = useSetupWizardStore((s) => s.setCurrency)
  const setBudgetCapEnabled = useSetupWizardStore((s) => s.setBudgetCapEnabled)
  const setBudgetCap = useSetupWizardStore((s) => s.setBudgetCap)
  const setTemplateVariable = useSetupWizardStore((s) => s.setTemplateVariable)
  const submitCompany = useSetupWizardStore((s) => s.submitCompany)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  // Resolve the full template object for the selected template
  const selectedTemplateObj = useMemo(
    () => templates.find((t) => t.name === selectedTemplate) ?? null,
    [templates, selectedTemplate],
  )

  // Validate and track completion
  const validation = useMemo(() => validateCompanyStep({
    companyName,
    companyDescription,
    companyResponse,
  }), [companyName, companyDescription, companyResponse])

  useEffect(() => {
    if (validation.valid) {
      markStepComplete('company')
    } else {
      markStepIncomplete('company')
    }
  }, [validation.valid, markStepComplete, markStepIncomplete])

  // Cost estimate from agents
  const costEstimate = useMemo(() => {
    if (agents.length === 0) return null
    return estimateMonthlyCost(
      agents.map((a) => ({
        model_provider: a.model_provider,
        model_id: a.model_id,
        tier: a.tier,
      })),
      [], // No provider models yet
    )
  }, [agents])

  const handleApplyTemplate = useCallback(async () => {
    await submitCompany()
  }, [submitCompany])

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Configure Your Company</h2>
        <p className="text-sm text-muted-foreground">
          Name your organization and customize the template.
        </p>
      </div>

      {/* Template indicator */}
      {selectedTemplate && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Template:</span>
          <StatPill label="" value={selectedTemplate} />
        </div>
      )}

      {/* Company details form */}
      <div className="space-y-4 rounded-lg border border-border bg-card p-4">
        <InputField
          label="Company Name"
          required
          value={companyName}
          onChange={(e) => setCompanyName(e.currentTarget.value)}
          placeholder="Your organization name"
          error={companyName.trim() === '' ? null : companyName.trim().length > 200 ? 'Max 200 characters' : null}
        />

        <InputField
          label="Description"
          multiline
          rows={3}
          value={companyDescription}
          onChange={(e) => setCompanyDescription(e.currentTarget.value)}
          placeholder="Describe your organization (optional)"
          hint="Max 1000 characters"
          error={companyDescription.length > 1000 ? 'Max 1000 characters' : null}
        />

        <SelectField
          label="Display Currency"
          options={[...CURRENCY_OPTIONS]}
          value={currency}
          onChange={(value) => setCurrency(value as CurrencyCode)}
        />

        <SelectField
          label="Model Tier Profile"
          options={[
            { value: 'economy', label: 'Economy' },
            { value: 'balanced', label: 'Balanced' },
            { value: 'premium', label: 'Premium' },
          ]}
          value={String(templateVariables.model_tier_profile ?? 'balanced')}
          onChange={(v) => setTemplateVariable('model_tier_profile', v)}
          hint="Influences which model tiers are assigned to agents and affects cost estimates."
        />
      </div>

      {/* Template variables */}
      <TemplateVariables
        variables={selectedTemplateObj?.variables ?? []}
        values={templateVariables}
        onChange={setTemplateVariable}
      />

      {/* Apply template button */}
      {!companyResponse && (
        <Button
          onClick={handleApplyTemplate}
          disabled={validation.errors.some(
            (e) => e !== 'Apply the template to continue',
          ) || companyLoading}
          className="w-full"
        >
          {companyLoading ? 'Applying Template...' : 'Apply Template'}
        </Button>
      )}

      {companyError && (
        <div role="alert" className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {companyError}
        </div>
      )}

      {/* Preview after applying */}
      {companyResponse && (
        <div className="space-y-4">
          <StaggerGroup className="grid grid-cols-3 gap-grid-gap max-[639px]:grid-cols-1">
            <StaggerItem>
              <MetricCard label="Departments" value={companyResponse.department_count} />
            </StaggerItem>
            <StaggerItem>
              <MetricCard label="Agents" value={companyResponse.agent_count} />
            </StaggerItem>
            <StaggerItem>
              <MetricCard label="Template" value={companyResponse.template_applied ?? 'None'} />
            </StaggerItem>
          </StaggerGroup>

          {/* Agent preview list */}
          {agents.length > 0 && (
            <div className="rounded-lg border border-border bg-card p-4">
              <h3 className="mb-2 text-sm font-semibold text-foreground">Generated Agents</h3>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {agents.map((agent) => (
                  <li key={agent.name}>
                    {agent.name} ({agent.department}) - {agent.tier} model
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Cost estimate + budget cap */}
          <CostEstimatePanel
            estimate={costEstimate}
            currency={currency}
            budgetCapEnabled={budgetCapEnabled}
            budgetCap={budgetCap}
            agents={agents}
            onBudgetCapEnabledChange={setBudgetCapEnabled}
            onBudgetCapChange={setBudgetCap}
          />
        </div>
      )}
    </div>
  )
}

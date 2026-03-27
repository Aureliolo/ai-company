import { useCallback, useEffect, useMemo } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { useToastStore } from '@/stores/toast'
import { categorizeTemplates } from '@/utils/template-categories'
import { estimateTemplateCost } from '@/utils/cost-estimator'
import { TemplateCategoryGroup } from './TemplateCategoryGroup'
import { TemplateCompareDrawer } from './TemplateCompareDrawer'
import { LayoutGrid } from 'lucide-react'

const MAX_COMPARE = 3

export function TemplateStep() {
  const templates = useSetupWizardStore((s) => s.templates)
  const templatesLoading = useSetupWizardStore((s) => s.templatesLoading)
  const templatesError = useSetupWizardStore((s) => s.templatesError)
  const selectedTemplate = useSetupWizardStore((s) => s.selectedTemplate)
  const comparedTemplates = useSetupWizardStore((s) => s.comparedTemplates)
  const currency = useSetupWizardStore((s) => s.currency)
  const fetchTemplates = useSetupWizardStore((s) => s.fetchTemplates)
  const selectTemplate = useSetupWizardStore((s) => s.selectTemplate)
  const toggleCompare = useSetupWizardStore((s) => s.toggleCompare)
  const clearComparison = useSetupWizardStore((s) => s.clearComparison)
  const markStepComplete = useSetupWizardStore((s) => s.markStepComplete)
  const markStepIncomplete = useSetupWizardStore((s) => s.markStepIncomplete)

  useEffect(() => {
    if (templates.length === 0 && !templatesLoading) {
      fetchTemplates()
    }
  }, [templates.length, templatesLoading, fetchTemplates])

  // Track step completion
  useEffect(() => {
    if (selectedTemplate) {
      markStepComplete('template')
    } else {
      markStepIncomplete('template')
    }
  }, [selectedTemplate, markStepComplete, markStepIncomplete])

  const categorized = useMemo(() => categorizeTemplates(templates), [templates])

  // Estimate costs per template (using tier fallbacks since no providers yet)
  const estimatedCosts = useMemo(() => {
    const costs = new Map<string, number>()
    // We don't have per-template tier breakdown from TemplateInfoResponse,
    // so we use a simple heuristic based on template tags
    for (const template of templates) {
      // Rough estimate: small templates = fewer agents, lower tiers
      const agentEstimate = template.tags.includes('solo') ? 1
        : template.tags.includes('small-team') ? 3
        : template.tags.includes('enterprise') || template.tags.includes('full-company') ? 12
        : 5
      const cost = estimateTemplateCost([
        { tier: 'large', count: Math.max(1, Math.floor(agentEstimate * 0.2)) },
        { tier: 'medium', count: Math.floor(agentEstimate * 0.5) },
        { tier: 'small', count: Math.max(0, agentEstimate - Math.floor(agentEstimate * 0.7)) },
      ])
      costs.set(template.name, cost)
    }
    return costs
  }, [templates])

  const handleSelect = useCallback(
    (name: string) => {
      selectTemplate(name)
    },
    [selectTemplate],
  )

  const handleToggleCompare = useCallback(
    (name: string) => {
      const added = toggleCompare(name)
      if (!added) {
        useToastStore.getState().add({
          variant: 'warning',
          title: 'Compare limit reached',
          description: `You can compare up to ${MAX_COMPARE} templates at a time.`,
        })
      }
    },
    [toggleCompare],
  )

  const handleRemoveFromCompare = useCallback(
    (name: string) => {
      toggleCompare(name) // Toggles off since already in list
    },
    [toggleCompare],
  )

  const comparedTemplateObjects = useMemo(
    () => templates.filter((t) => comparedTemplates.includes(t.name)),
    [templates, comparedTemplates],
  )

  if (templatesLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-6 w-48" />
        <div className="grid grid-cols-3 gap-grid-gap">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  if (templatesError) {
    return (
      <EmptyState
        title="Failed to load templates"
        description={templatesError}
        action={{ label: 'Retry', onClick: fetchTemplates }}
      />
    )
  }

  if (templates.length === 0) {
    return (
      <EmptyState
        icon={LayoutGrid}
        title="No templates available"
        description="No company templates found. Check your template directory."
      />
    )
  }

  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">Choose a Template</h2>
        <p className="text-sm text-muted-foreground">
          Select a template to start building your organization.
        </p>
      </div>

      {[...categorized.entries()].map(([category, categoryTemplates]) => (
        <TemplateCategoryGroup
          key={category}
          category={category}
          templates={categoryTemplates}
          estimatedCosts={estimatedCosts}
          currency={currency}
          selectedTemplate={selectedTemplate}
          comparedTemplates={comparedTemplates}
          compareDisabled={comparedTemplates.length >= MAX_COMPARE}
          onSelect={handleSelect}
          onToggleCompare={handleToggleCompare}
        />
      ))}

      <TemplateCompareDrawer
        open={comparedTemplates.length >= 2}
        onClose={clearComparison}
        templates={comparedTemplateObjects}
        estimatedCosts={estimatedCosts}
        currency={currency}
        onSelect={(name) => {
          handleSelect(name)
          clearComparison()
        }}
        onRemove={handleRemoveFromCompare}
      />
    </div>
  )
}

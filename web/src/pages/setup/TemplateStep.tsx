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

/** Template size tags used for agent count heuristics. */
const TAG_SOLO = 'solo'
const TAG_SMALL_TEAM = 'small-team'
const TAG_ENTERPRISE = 'enterprise'
const TAG_FULL_COMPANY = 'full-company'

/** Estimated agent counts per template size category. */
const AGENT_COUNT_SOLO = 1
const AGENT_COUNT_SMALL_TEAM = 3
const AGENT_COUNT_LARGE = 12
const AGENT_COUNT_DEFAULT = 5

/** Tier distribution ratios for cost estimation. */
const TIER_RATIO_LARGE = 0.2
const TIER_RATIO_MEDIUM = 0.5

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
    if (templates.length === 0 && !templatesLoading && !templatesError) {
      fetchTemplates()
    }
  }, [templates.length, templatesLoading, templatesError, fetchTemplates])

  // Track step completion
  useEffect(() => {
    if (selectedTemplate) {
      markStepComplete('template')
    } else {
      markStepIncomplete('template')
    }
  }, [selectedTemplate, markStepComplete, markStepIncomplete])

  const providers = useSetupWizardStore((s) => s.providers)

  const categorized = useMemo(() => categorizeTemplates(templates), [templates])

  // Determine recommended templates based on configured providers
  const recommendedTemplates = useMemo(() => {
    const recommended = new Set<string>()
    const providerCount = Object.keys(providers).length
    const smallTags = new Set([TAG_SOLO, TAG_SMALL_TEAM, 'startup', 'mvp'])
    const largeTags = new Set([TAG_ENTERPRISE, TAG_FULL_COMPANY])

    for (const template of templates) {
      if (providerCount === 0) {
        // No providers configured yet -- recommend small/simple templates
        if (template.tags.some((tag) => smallTags.has(tag))) {
          recommended.add(template.name)
        }
      } else {
        // Providers configured -- recommend larger templates
        if (template.tags.some((tag) => largeTags.has(tag))) {
          recommended.add(template.name)
        }
      }
    }
    return recommended
  }, [templates, providers])

  // Estimate costs per template (using tier fallbacks since no providers yet)
  const estimatedCosts = useMemo(() => {
    const costs = new Map<string, number>()
    // We don't have per-template tier breakdown from TemplateInfoResponse,
    // so we use a simple heuristic based on template tags
    for (const template of templates) {
      // Rough estimate: small templates = fewer agents, lower tiers
      const agentEstimate = template.tags.includes(TAG_SOLO) ? AGENT_COUNT_SOLO
        : template.tags.includes(TAG_SMALL_TEAM) ? AGENT_COUNT_SMALL_TEAM
        : template.tags.includes(TAG_ENTERPRISE) || template.tags.includes(TAG_FULL_COMPANY) ? AGENT_COUNT_LARGE
        : AGENT_COUNT_DEFAULT
      const largeCount = Math.max(1, Math.floor(agentEstimate * TIER_RATIO_LARGE))
      const mediumCount = Math.floor(agentEstimate * TIER_RATIO_MEDIUM)
      const smallCount = Math.max(0, agentEstimate - largeCount - mediumCount)
      const cost = estimateTemplateCost([
        { tier: 'large', count: largeCount },
        { tier: 'medium', count: mediumCount },
        { tier: 'small', count: smallCount },
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
          recommendedTemplates={recommendedTemplates}
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

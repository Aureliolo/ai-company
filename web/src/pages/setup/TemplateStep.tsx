import { useCallback, useEffect, useMemo } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useSetupWizardStore } from '@/stores/setup-wizard'
import { useToastStore } from '@/stores/toast'
import { TemplateCard } from './TemplateCard'
import { TemplateCompareDrawer } from './TemplateCompareDrawer'
import { LayoutGrid } from 'lucide-react'

const MAX_COMPARE = 3

/** Template size tags used for recommendation heuristics. */
const TAG_SOLO = 'solo'
const TAG_SMALL_TEAM = 'small-team'
const TAG_ENTERPRISE = 'enterprise'
const TAG_FULL_COMPANY = 'full-company'

export function TemplateStep() {
  const templates = useSetupWizardStore((s) => s.templates)
  const templatesLoading = useSetupWizardStore((s) => s.templatesLoading)
  const templatesError = useSetupWizardStore((s) => s.templatesError)
  const selectedTemplate = useSetupWizardStore((s) => s.selectedTemplate)
  const comparedTemplates = useSetupWizardStore((s) => s.comparedTemplates)
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

  // Determine recommended templates based on configured providers
  const recommendedTemplates = useMemo(() => {
    const recommended = new Set<string>()
    const providerCount = Object.keys(providers).length
    const smallTags = new Set([TAG_SOLO, TAG_SMALL_TEAM, 'startup', 'mvp'])
    const largeTags = new Set([TAG_ENTERPRISE, TAG_FULL_COMPANY])

    for (const template of templates) {
      if (providerCount === 0) {
        if (template.tags.some((tag) => smallTags.has(tag))) {
          recommended.add(template.name)
        }
      } else {
        if (template.tags.some((tag) => largeTags.has(tag))) {
          recommended.add(template.name)
        }
      }
    }
    return recommended
  }, [templates, providers])

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
      toggleCompare(name)
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

      <StaggerGroup className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-2 max-[639px]:grid-cols-1">
        {templates.map((template) => (
          <StaggerItem key={template.name}>
            <TemplateCard
              template={template}
              selected={selectedTemplate === template.name}
              compared={comparedTemplates.includes(template.name)}
              recommended={recommendedTemplates.has(template.name)}
              onSelect={() => handleSelect(template.name)}
              onToggleCompare={() => handleToggleCompare(template.name)}
              compareDisabled={comparedTemplates.length >= MAX_COMPARE}
            />
          </StaggerItem>
        ))}
      </StaggerGroup>

      <TemplateCompareDrawer
        open={comparedTemplates.length >= 2}
        onClose={clearComparison}
        templates={comparedTemplateObjects}
        onSelect={(name) => {
          handleSelect(name)
          clearComparison()
        }}
        onRemove={handleRemoveFromCompare}
      />
    </div>
  )
}

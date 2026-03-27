import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import type { TemplateInfoResponse } from '@/api/types'
import type { CurrencyCode } from '@/utils/currencies'
import { getCategoryLabel } from '@/utils/template-categories'
import { TemplateCard } from './TemplateCard'

export interface TemplateCategoryGroupProps {
  category: string
  templates: readonly TemplateInfoResponse[]
  estimatedCosts: ReadonlyMap<string, number>
  currency: CurrencyCode
  selectedTemplate: string | null
  comparedTemplates: readonly string[]
  compareDisabled: boolean
  recommendedTemplates?: ReadonlySet<string>
  onSelect: (name: string) => void
  onToggleCompare: (name: string) => void
}

export function TemplateCategoryGroup({
  category,
  templates,
  estimatedCosts,
  currency,
  selectedTemplate,
  comparedTemplates,
  compareDisabled,
  recommendedTemplates,
  onSelect,
  onToggleCompare,
}: TemplateCategoryGroupProps) {
  return (
    <section>
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {getCategoryLabel(category)}
      </h3>
      <StaggerGroup className="grid grid-cols-3 gap-grid-gap max-[1023px]:grid-cols-2 max-[639px]:grid-cols-1">
        {templates.map((template) => (
          <StaggerItem key={template.name}>
            <TemplateCard
              template={template}
              estimatedCost={estimatedCosts.get(template.name) ?? 0}
              currency={currency}
              selected={selectedTemplate === template.name}
              compared={comparedTemplates.includes(template.name)}
              recommended={recommendedTemplates?.has(template.name)}
              onSelect={() => onSelect(template.name)}
              onToggleCompare={() => onToggleCompare(template.name)}
              compareDisabled={compareDisabled}
            />
          </StaggerItem>
        ))}
      </StaggerGroup>
    </section>
  )
}

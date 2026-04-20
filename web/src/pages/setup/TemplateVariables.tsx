import { SliderField } from '@/components/ui/slider-field'
import { ToggleField } from '@/components/ui/toggle-field'
import type { TemplateVariable } from '@/api/types/setup'

export interface TemplateVariablesProps {
  variables: readonly TemplateVariable[]
  values: Readonly<Record<string, string | number | boolean>>
  onChange: (key: string, value: string | number | boolean) => void
  currency?: string
}

/** Replace "USD" in a variable description with the selected currency code. */
function localizeCurrencyLabel(description: string, currency: string | undefined): string {
  if (!currency) return description
  return description.replace(/\bUSD\b/g, currency)
}

export function TemplateVariables({ variables, values, onChange, currency }: TemplateVariablesProps) {
  if (variables.length === 0) return null

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-card">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">Template Variables</h3>
        <p className="text-xs text-muted-foreground">
          Customize how the template generates your company structure.
        </p>
      </div>
      {variables.map((v) => {
        const currentValue = values[v.name] ?? v.default
        const label = localizeCurrencyLabel(v.description || v.name, currency)
        if (v.var_type === 'bool') {
          return (
            <ToggleField
              key={v.name}
              label={label}
              checked={currentValue === true}
              onChange={(checked) => onChange(v.name, checked)}
            />
          )
        }
        if (v.var_type === 'int' || v.var_type === 'float') {
          const numValue = typeof currentValue === 'number' ? currentValue : Number(currentValue) || 0
          return (
            <SliderField
              key={v.name}
              label={label}
              value={numValue}
              min={v.var_type === 'int' ? 1 : 0}
              max={v.var_type === 'int' ? 50 : 1000}
              step={v.var_type === 'int' ? 1 : 10}
              formatValue={undefined}
              onChange={(val) => onChange(v.name, val)}
            />
          )
        }
        // String and other types: not rendered as slider/toggle
        return null
      })}
    </div>
  )
}

import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { Boxes } from 'lucide-react'
import type { ProviderModelConfig } from '@/api/types'

interface ProviderModelRowProps {
  model: ProviderModelConfig
}

function ProviderModelRow({ model }: ProviderModelRowProps) {
  return (
    <tr className="border-b border-border/50 last:border-0">
      <td className="py-2 pr-4 font-mono text-foreground">{model.id}</td>
      <td className="py-2 pr-4 text-text-secondary">{model.alias ?? '--'}</td>
      <td className="py-2 pr-4 text-right font-mono text-text-secondary">
        {(model.max_context / 1000).toFixed(0)}k
      </td>
      <td className="py-2 pr-4 text-right font-mono text-text-secondary">
        {model.cost_per_1k_input.toFixed(4)}
      </td>
      <td className="py-2 text-right font-mono text-text-secondary">
        {model.cost_per_1k_output.toFixed(4)}
      </td>
    </tr>
  )
}

interface ProviderModelListProps {
  models: readonly ProviderModelConfig[]
}

export function ProviderModelList({ models }: ProviderModelListProps) {
  return (
    <SectionCard title="Models" icon={Boxes}>
      {models.length === 0 ? (
        <EmptyState
          icon={Boxes}
          title="No models configured"
          description="Use 'Discover Models' to auto-detect available models, or add them manually."
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-text-muted">
                <th className="pb-2 pr-4 font-medium">Model ID</th>
                <th className="pb-2 pr-4 font-medium">Alias</th>
                <th className="pb-2 pr-4 font-medium text-right">Context</th>
                <th className="pb-2 pr-4 font-medium text-right">Input/1k</th>
                <th className="pb-2 font-medium text-right">Output/1k</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <ProviderModelRow key={model.id} model={model} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}

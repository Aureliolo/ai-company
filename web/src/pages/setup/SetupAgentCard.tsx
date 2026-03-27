import { Dices } from 'lucide-react'
import { Avatar } from '@/components/ui/avatar'
import { InlineEdit } from '@/components/ui/inline-edit'
import { StatPill } from '@/components/ui/stat-pill'
import { Button } from '@/components/ui/button'
import type { SetupAgentSummary, ProviderConfig } from '@/api/types'
import { AgentModelPicker } from './AgentModelPicker'

export interface SetupAgentCardProps {
  agent: SetupAgentSummary
  index: number
  providers: Readonly<Record<string, ProviderConfig>>
  onNameChange: (index: number, name: string) => Promise<void>
  onModelChange: (index: number, provider: string, modelId: string) => Promise<void>
  onRandomizeName: (index: number) => Promise<void>
}

export function SetupAgentCard({
  agent,
  index,
  providers,
  onNameChange,
  onModelChange,
  onRandomizeName,
}: SetupAgentCardProps) {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-card p-4">
      <Avatar name={agent.name} size="md" />
      <div className="flex-1 space-y-2">
        {/* Name + randomize */}
        <div className="flex items-center gap-2">
          <InlineEdit
            value={agent.name}
            onSave={(name) => onNameChange(index, name)}
            validate={(v) => v.trim() ? null : 'Name is required'}
          />
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onRandomizeName(index)}
            aria-label="Randomize name"
          >
            <Dices className="size-3.5" />
          </Button>
        </div>

        {/* Role + department + level */}
        <div className="flex flex-wrap gap-1.5">
          <StatPill label="Role" value={agent.role} />
          <StatPill label="Dept" value={agent.department} />
          <StatPill label="Level" value={agent.level} />
          {agent.personality_preset && (
            <StatPill label="Personality" value={agent.personality_preset} />
          )}
        </div>

        {/* Model picker */}
        <AgentModelPicker
          currentProvider={agent.model_provider}
          currentModelId={agent.model_id}
          providers={providers}
          onChange={(provider, modelId) => onModelChange(index, provider, modelId)}
        />
      </div>
    </div>
  )
}

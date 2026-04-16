import { Pencil, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ToggleField } from '@/components/ui/toggle-field'
import type { RuleListItem as RuleListItemType } from '@/api/endpoints/custom-rules'

import { RuleSeverityBadge } from './RuleSeverityBadge'

function EditButton({ ruleId, ruleName, onEdit }: { ruleId: string; ruleName: string; onEdit: (id: string) => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={() => onEdit(ruleId)} aria-label={`Edit ${ruleName}`}>
      <Pencil className="size-3.5" />
    </Button>
  )
}

function DeleteButton({ ruleId, ruleName, onDelete }: { ruleId: string; ruleName: string; onDelete: (id: string) => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={() => onDelete(ruleId)} aria-label={`Delete ${ruleName}`}>
      <Trash2 className="size-3.5 text-danger" />
    </Button>
  )
}

interface RuleListItemProps {
  rule: RuleListItemType
  onToggle?: (name: string, id?: string) => void
  onEdit?: (id: string) => void
  onDelete?: (id: string) => void
  toggleDisabled?: boolean
}

export function RuleListItem({
  rule,
  onToggle,
  onEdit,
  onDelete,
  toggleDisabled,
}: RuleListItemProps) {
  const isCustom = rule.type === 'custom'

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-card">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">
            {rule.name}
          </span>
          {rule.severity && (
            <RuleSeverityBadge severity={rule.severity} />
          )}
          {!isCustom && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-micro text-muted-foreground">
              built-in
            </span>
          )}
        </div>
        {isCustom && rule.description && (
          <p className="mt-0.5 truncate text-body-sm text-muted-foreground">
            {rule.description}
          </p>
        )}
        {isCustom && rule.metric_path && (
          <p className="mt-0.5 text-micro text-muted-foreground">
            {rule.metric_path} {rule.comparator} {rule.threshold}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {isCustom && onEdit && rule.id != null && (
          <EditButton ruleId={rule.id} ruleName={rule.name} onEdit={onEdit} />
        )}
        {isCustom && onDelete && rule.id != null && (
          <DeleteButton ruleId={rule.id} ruleName={rule.name} onDelete={onDelete} />
        )}
        <ToggleField
          label={`Toggle ${rule.name}`}
          checked={rule.enabled}
          onChange={() => onToggle?.(rule.name, rule.id)}
          disabled={toggleDisabled || !isCustom}
        />
      </div>
    </div>
  )
}

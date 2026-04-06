import { SegmentedControl } from '@/components/ui/segmented-control'
import type { NotificationFilterGroup } from '@/types/notifications'
import { FILTER_GROUP_LABELS } from '@/types/notifications'

const GROUPS: readonly NotificationFilterGroup[] = [
  'all',
  'approvals',
  'budget',
  'system',
  'tasks',
  'agents',
  'providers',
  'connection',
] as const

interface NotificationFilterBarProps {
  readonly value: NotificationFilterGroup
  readonly onChange: (group: NotificationFilterGroup) => void
}

export function NotificationFilterBar({ value, onChange }: NotificationFilterBarProps) {
  return (
    <SegmentedControl<NotificationFilterGroup>
      value={value}
      onChange={onChange}
      options={GROUPS.map((g) => ({ value: g, label: FILTER_GROUP_LABELS[g] }))}
      size="sm"
    />
  )
}

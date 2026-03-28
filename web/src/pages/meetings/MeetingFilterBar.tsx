import { SelectField } from '@/components/ui/select-field'
import { formatLabel } from '@/utils/format'
import type { MeetingPageFilters } from '@/utils/meetings'

interface MeetingFilterBarProps {
  filters: MeetingPageFilters
  onFiltersChange: (filters: MeetingPageFilters) => void
  meetingTypes: readonly string[]
  className?: string
}

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'budget_exhausted', label: 'Budget Exhausted' },
]

export function MeetingFilterBar({
  filters,
  onFiltersChange,
  meetingTypes,
  className,
}: MeetingFilterBarProps) {
  const typeOptions = [
    { value: '', label: 'All types' },
    ...meetingTypes.map((t) => ({ value: t, label: formatLabel(t) })),
  ]

  return (
    <div className={className}>
      <div className="flex items-center gap-3">
        <SelectField
          label="Status"
          value={filters.status ?? ''}
          onChange={(val) =>
            onFiltersChange({
              ...filters,
              status: val || undefined,
            } as MeetingPageFilters)
          }
          options={STATUS_OPTIONS}
          className="w-44"
        />
        <SelectField
          label="Type"
          value={filters.meetingType ?? ''}
          onChange={(val) =>
            onFiltersChange({
              ...filters,
              meetingType: val || undefined,
            })
          }
          options={typeOptions}
          className="w-44"
        />
      </div>
    </div>
  )
}

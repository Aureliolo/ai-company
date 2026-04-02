import { useCallback, useMemo, useState } from 'react'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import { SortableContext, useSortable, rectSortingStrategy, sortableKeyboardCoordinates, arrayMove } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Building2, PackagePlus, Plus } from 'lucide-react'
import type {
  CompanyConfig,
  CreateDepartmentRequest,
  Department,
  DepartmentHealth,
  UpdateDepartmentRequest,
} from '@/api/types'
import { DeptHealthBar } from '@/components/ui/dept-health-bar'
import { SectionCard } from '@/components/ui/section-card'
import { EmptyState } from '@/components/ui/empty-state'
import { Button } from '@/components/ui/button'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useToastStore } from '@/stores/toast'
import { DepartmentCreateDialog } from './DepartmentCreateDialog'
import { DepartmentEditDrawer } from './DepartmentEditDrawer'
import { PackSelectionDialog } from './PackSelectionDialog'

export interface DepartmentsTabProps {
  config: CompanyConfig | null
  departmentHealths: readonly DepartmentHealth[]
  saving: boolean
  onCreateDepartment: (data: CreateDepartmentRequest) => Promise<Department>
  onUpdateDepartment: (name: string, data: UpdateDepartmentRequest) => Promise<Department>
  onDeleteDepartment: (name: string) => Promise<void>
  onReorderDepartments: (orderedNames: string[]) => Promise<void>
  optimisticReorderDepartments: (orderedNames: string[]) => () => void
}

function SortableDepartmentCard({
  dept,
  health,
  agentCount,
  onClick,
  disabled,
}: {
  dept: Department
  health: DepartmentHealth | null
  agentCount: number
  onClick: () => void
  disabled?: boolean
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: dept.name,
    data: { dept },
    disabled,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div ref={setNodeRef} style={style} {...(disabled ? {} : { ...attributes, ...listeners })}>
      <button
        type="button"
        className="w-full text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-lg"
        onClick={onClick}
        onKeyDown={(e) => e.stopPropagation()}
        aria-label={`Edit department ${dept.display_name ?? dept.name}`}
      >
        <SectionCard title={dept.display_name ?? dept.name} icon={Building2}>
          <DeptHealthBar
            name={dept.display_name ?? dept.name}
            health={health?.utilization_percent}
            agentCount={agentCount}
          />
          {dept.teams.length > 0 && (
            <p className="mt-2 text-xs text-text-secondary">
              {dept.teams.length} team{dept.teams.length !== 1 ? 's' : ''}
            </p>
          )}
        </SectionCard>
      </button>
    </div>
  )
}

export function DepartmentsTab({
  config,
  departmentHealths,
  saving,
  onCreateDepartment,
  onUpdateDepartment,
  onDeleteDepartment,
  onReorderDepartments,
  optimisticReorderDepartments,
}: DepartmentsTabProps) {
  const [createOpen, setCreateOpen] = useState(false)
  const [packOpen, setPackOpen] = useState(false)
  const [editDept, setEditDept] = useState<Department | null>(null)
  const [activeDept, setActiveDept] = useState<Department | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const healthMap = useMemo(
    () => new Map(departmentHealths.map((h) => [h.department_name, h])),
    [departmentHealths],
  )

  const getAgentCount = useCallback(
    (deptName: string): number => {
      if (!config) return 0
      return config.agents.filter((a) => a.department === deptName).length
    },
    [config],
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveDept(event.active.data.current?.dept ?? null)
  }, [])

  const handleDragEnd = useCallback(
    async (event: DragEndEvent) => {
      setActiveDept(null)
      const { active, over } = event
      if (!over || active.id === over.id || !config) return

      const oldIndex = config.departments.findIndex((d) => d.name === active.id)
      const newIndex = config.departments.findIndex((d) => d.name === over.id)
      if (oldIndex === -1 || newIndex === -1) return

      const reordered = arrayMove([...config.departments], oldIndex, newIndex)
      const orderedNames = reordered.map((d) => d.name)

      const rollback = optimisticReorderDepartments(orderedNames)
      try {
        await onReorderDepartments(orderedNames)
      } catch {
        rollback()
        useToastStore.getState().add({ variant: 'error', title: 'Failed to reorder departments' })
      }
    },
    [config, optimisticReorderDepartments, onReorderDepartments],
  )

  const editHealth = editDept ? (healthMap.get(editDept.name) ?? null) : null

  if (!config || config.departments.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setPackOpen(true)} disabled={saving}>
            <PackagePlus className="mr-1.5 size-3.5" />
            Add Team
          </Button>
          <Button onClick={() => setCreateOpen(true)} disabled={saving}>
            <Plus className="mr-1.5 size-3.5" />
            Add Department
          </Button>
        </div>
        <EmptyState
          icon={Building2}
          title="No departments"
          description="Create your first department to get started."
        />
        <DepartmentCreateDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          existingNames={[]}
          onCreate={onCreateDepartment}
          disabled={saving}
        />
        <PackSelectionDialog open={packOpen} onOpenChange={setPackOpen} disabled={saving} />
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => setPackOpen(true)} disabled={saving}>
          <PackagePlus className="mr-1.5 size-3.5" />
          Add Team
        </Button>
        <Button onClick={() => setCreateOpen(true)} disabled={saving}>
          <Plus className="mr-1.5 size-3.5" />
          Add Department
        </Button>
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveDept(null)}
      >
        <SortableContext items={config.departments.map((d) => d.name)} strategy={rectSortingStrategy}>
          <StaggerGroup className="grid grid-cols-2 gap-grid-gap max-[1023px]:grid-cols-1">
            {config.departments.map((dept) => (
              <StaggerItem key={dept.name}>
                <SortableDepartmentCard
                  dept={dept}
                  health={healthMap.get(dept.name) ?? null}
                  agentCount={getAgentCount(dept.name)}
                  onClick={() => setEditDept(dept)}
                  disabled={saving}
                />
              </StaggerItem>
            ))}
          </StaggerGroup>
        </SortableContext>

        <DragOverlay>
          {activeDept && (
            <div className="rounded-lg border border-accent bg-card p-card" style={{ boxShadow: 'var(--so-shadow-card-hover)' }}>
              <p className="text-sm font-semibold text-foreground">{activeDept.display_name ?? activeDept.name}</p>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      <DepartmentCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        existingNames={config.departments.map((d) => d.name)}
        onCreate={onCreateDepartment}
        disabled={saving}
      />

      <DepartmentEditDrawer
        open={editDept !== null}
        onClose={() => setEditDept(null)}
        department={editDept}
        health={editHealth}
        onUpdate={onUpdateDepartment}
        onDelete={onDeleteDepartment}
        saving={saving}
      />

      <PackSelectionDialog open={packOpen} onOpenChange={setPackOpen} disabled={saving} />
    </div>
  )
}

import { useCallback, useRef, useState } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import type { CeremonyPolicyConfig, Department, DepartmentHealth, UpdateDepartmentRequest } from '@/api/types'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { DeptHealthBar } from '@/components/ui/dept-health-bar'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/utils/errors'
import { DepartmentCeremonyOverride } from './DepartmentCeremonyOverride'

export interface DepartmentEditDrawerProps {
  open: boolean
  onClose: () => void
  department: Department | null
  health: DepartmentHealth | null
  onUpdate: (name: string, data: UpdateDepartmentRequest) => Promise<Department>
  onDelete: (name: string) => Promise<void>
  saving: boolean
}

export function DepartmentEditDrawer({
  open,
  onClose,
  department,
  health,
  onUpdate,
  onDelete,
  saving,
}: DepartmentEditDrawerProps) {
  const [displayName, setDisplayName] = useState('')
  const [budgetPercent, setBudgetPercent] = useState('0')
  const [ceremonyPolicy, setCeremonyPolicy] = useState<CeremonyPolicyConfig | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const prevDepartmentRef = useRef<typeof department | undefined>(undefined)
  if (department !== prevDepartmentRef.current) {
    prevDepartmentRef.current = department
    if (department) {
      setDisplayName(department.display_name ?? department.name)
      setBudgetPercent(department.budget_percent != null ? String(department.budget_percent) : '0')
      setCeremonyPolicy(department.ceremony_policy ?? null)
      setSubmitError(null)
    }
    setDeleteOpen(false)
    setDeleting(false)
  }

  const handleSave = useCallback(async () => {
    if (!department) return
    setSubmitError(null)
    const pct = Number(budgetPercent)
    if (Number.isFinite(pct) && (pct < 0 || pct > 100)) {
      setSubmitError('Budget percent must be between 0 and 100')
      return
    }
    try {
      await onUpdate(department.name, {
        display_name: displayName.trim() || undefined,
        budget_percent: Number.isFinite(pct) ? pct : undefined,
        ceremony_policy: ceremonyPolicy,
      })
      onClose()
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    }
  }, [department, displayName, budgetPercent, ceremonyPolicy, onUpdate, onClose])

  const handleDelete = useCallback(async () => {
    if (!department) return
    setDeleting(true)
    try {
      await onDelete(department.name)
      setDeleteOpen(false)
      onClose()
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }, [department, onDelete, onClose])

  return (
    <>
      <Drawer open={open} onClose={onClose} title={department ? `Edit: ${department.display_name ?? department.name}` : 'Edit Department'}>
        {department && (
          <div className="space-y-5">
            <DeptHealthBar
              name={department.display_name ?? department.name}
              health={health?.utilization_percent}
              agentCount={health?.agent_count ?? 0}
            />

            <InputField
              label="Display Name"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />

            <InputField
              label="Budget %"
              type="number"
              value={budgetPercent}
              onChange={(e) => setBudgetPercent(e.target.value)}
              hint="Percentage of company budget (0-100)"
            />

            {/* Ceremony policy override */}
            <DepartmentCeremonyOverride
              policy={ceremonyPolicy}
              onChange={setCeremonyPolicy}
              disabled={saving}
            />

            {/* Teams summary */}
            <div className="border-t border-border pt-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Teams</p>
              {department.teams.length === 0 ? (
                <p className="text-xs text-text-secondary">No teams configured</p>
              ) : (
                <ul className="space-y-1">
                  {department.teams.map((team) => (
                    <li key={team.name} className="text-xs text-text-secondary">
                      <span className="font-medium text-foreground">{team.name}</span>
                      {' -- '}
                      {team.members.length} member{team.members.length !== 1 ? 's' : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {submitError && (
              <p className="text-xs text-danger">{submitError}</p>
            )}

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(true)}
                className="text-danger hover:text-danger"
              >
                <Trash2 className="mr-1.5 size-3.5" />
                Delete
              </Button>
              <div className="flex gap-3">
                <Button variant="outline" onClick={onClose}>Cancel</Button>
                <Button onClick={handleSave} disabled={saving}>
                  {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
                  Save
                </Button>
              </div>
            </div>
          </div>
        )}
      </Drawer>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete ${department?.display_name ?? department?.name ?? 'department'}?`}
        description="This will remove the department and unassign all its agents."
        variant="destructive"
        confirmLabel="Delete"
        onConfirm={handleDelete}
        loading={deleting}
      />
    </>
  )
}

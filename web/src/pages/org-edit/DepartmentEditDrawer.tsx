import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Trash2, Users } from 'lucide-react'
import type { CeremonyPolicyConfig, Department, DepartmentHealth, UpdateDepartmentRequest } from '@/api/types'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Button } from '@/components/ui/button'
import { getErrorMessage } from '@/utils/errors'
import { DepartmentCeremonyOverride } from './DepartmentCeremonyOverride'
import { ORG_EDIT_COMING_SOON_TOOLTIP, ORG_EDIT_COMING_SOON_DESCRIPTION } from './coming-soon'

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
  useEffect(() => {
    /* eslint-disable @eslint-react/set-state-in-effect -- legitimate prop-to-local-state sync */
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
    /* eslint-enable @eslint-react/set-state-in-effect */
  }, [department])

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
            {/*
             * Previously the drawer opened with a runtime utilization
             * gauge (utilization_percent via DeptHealthBar).  It was
             * confusing on an editor surface because the user is here
             * to configure the department, not to monitor it.  The
             * live gauge remains on the Dashboard / Org Chart views.
             */}
            <div className="inline-flex items-center gap-1.5 text-compact text-text-secondary">
              <Users className="size-3.5" aria-hidden="true" />
              {(health?.agent_count ?? 0)} agent{(health?.agent_count ?? 0) === 1 ? '' : 's'}
            </div>

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

            {/* Teams summary (read-only -- team editing is tracked as a
              * deferred item in docs/design/page-structure.md:38 -- "nested
              * teams/reporting/policies editing is deferred") */}
            <div className="border-t border-border pt-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Teams</p>
              <p className="text-xs text-text-secondary">
                Teams are named sub-groups inside a department, each with a lead
                and a set of member agents. They let you model reporting lines
                more granularly than department alone (for example, a Frontend
                and a Backend team inside Engineering).
              </p>
              {department.teams.length === 0 ? (
                <p className="text-xs text-text-secondary">
                  No teams yet. Add one from the Departments tab via the
                  <span className="mx-1 font-medium text-foreground">Add Team</span>
                  button -- it picks from pre-built team template packs. In-drawer
                  team editing is not yet available.
                </p>
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

            {/*
             * Save + Delete are disabled until the backend CRUD
             * endpoints land -- see #1081.  The drawer stays open for
             * read-only inspection of the department's current config.
             */}
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(true)}
                className="text-danger hover:text-danger"
                disabled
                aria-disabled="true"
                title={ORG_EDIT_COMING_SOON_TOOLTIP}
              >
                <Trash2 className="mr-1.5 size-3.5" />
                Delete
              </Button>
              <div className="flex gap-3">
                <Button variant="outline" onClick={onClose}>Cancel</Button>
                <Button
                  onClick={handleSave}
                  disabled
                  aria-disabled="true"
                  title={ORG_EDIT_COMING_SOON_TOOLTIP}
                >
                  {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
                  Save
                </Button>
              </div>
            </div>
            <p className="text-xs text-text-muted mt-2">{ORG_EDIT_COMING_SOON_DESCRIPTION}</p>
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

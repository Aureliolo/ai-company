import { useCallback, useEffect, useState } from 'react'
import { Loader2, Trash2 } from 'lucide-react'
import type { AgentConfig, Department, SeniorityLevel, UpdateAgentOrgRequest } from '@/api/types'
import { SENIORITY_LEVEL_VALUES, AGENT_STATUS_VALUES } from '@/api/types'
import { Drawer } from '@/components/ui/drawer'
import { InputField } from '@/components/ui/input-field'
import { SelectField } from '@/components/ui/select-field'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Button } from '@/components/ui/button'
import { StatusBadge } from '@/components/ui/status-badge'
import { getErrorMessage } from '@/utils/errors'
import type { AgentRuntimeStatus } from '@/lib/utils'

export interface AgentEditDrawerProps {
  open: boolean
  onClose: () => void
  agent: AgentConfig | null
  departments: readonly Department[]
  onUpdate: (name: string, data: UpdateAgentOrgRequest) => Promise<AgentConfig>
  onDelete: (name: string) => Promise<void>
  saving: boolean
}

function toRuntimeStatus(status: AgentConfig['status']): AgentRuntimeStatus {
  switch (status) {
    case 'active': return 'active'
    case 'onboarding': return 'idle'
    case 'on_leave': return 'offline'
    case 'terminated': return 'offline'
    default: return 'idle'
  }
}

const LEVEL_OPTIONS = SENIORITY_LEVEL_VALUES.map((l) => ({ value: l, label: l }))
const STATUS_OPTIONS = AGENT_STATUS_VALUES.map((s) => ({ value: s, label: s.replace('_', ' ') }))

export function AgentEditDrawer({
  open,
  onClose,
  agent,
  departments,
  onUpdate,
  onDelete,
  saving,
}: AgentEditDrawerProps) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [department, setDepartment] = useState('')
  const [level, setLevel] = useState<SeniorityLevel>('mid')
  const [status, setStatus] = useState<AgentConfig['status']>('active')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (agent) {
      setName(agent.name)
      setRole(agent.role)
      setDepartment(agent.department)
      setLevel(agent.level)
      setStatus(agent.status)
      setSubmitError(null)
    }
  }, [agent])

  const deptOptions = departments.map((d) => ({ value: d.name, label: d.display_name }))

  const handleSave = useCallback(async () => {
    if (!agent) return
    setSubmitError(null)
    try {
      await onUpdate(agent.name, {
        name: name.trim() || undefined,
        role: role.trim() || undefined,
        department: department as UpdateAgentOrgRequest['department'],
        level,
        status,
      })
      onClose()
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    }
  }, [agent, name, role, department, level, status, onUpdate, onClose])

  const handleDelete = useCallback(async () => {
    if (!agent) return
    setDeleting(true)
    try {
      await onDelete(agent.name)
      setDeleteOpen(false)
      onClose()
    } catch (err) {
      setSubmitError(getErrorMessage(err))
    } finally {
      setDeleting(false)
    }
  }, [agent, onDelete, onClose])

  return (
    <>
      <Drawer open={open} onClose={onClose} title={agent ? `Edit: ${agent.name}` : 'Edit Agent'}>
        {agent && (
          <div className="space-y-5">
            <div className="flex items-center gap-2">
              <StatusBadge status={toRuntimeStatus(agent.status)} label />
              <span className="text-xs text-text-secondary">Hired: {new Date(agent.hiring_date).toLocaleDateString()}</span>
            </div>

            <InputField
              label="Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />

            <InputField
              label="Role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            />

            <SelectField
              label="Department"
              options={deptOptions}
              value={department}
              onChange={setDepartment}
            />

            <SelectField
              label="Level"
              options={LEVEL_OPTIONS}
              value={level}
              onChange={(v) => setLevel(v as SeniorityLevel)}
            />

            <SelectField
              label="Status"
              options={STATUS_OPTIONS}
              value={status}
              onChange={(v) => setStatus(v as AgentConfig['status'])}
            />

            {/* Read-only info */}
            <div className="border-t border-border pt-4 space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">Model</p>
              <p className="text-xs text-text-secondary font-mono">{agent.model.provider} / {agent.model.model_id}</p>
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
        title={`Delete ${agent?.name ?? 'agent'}?`}
        description="This action cannot be undone. The agent will be permanently removed."
        variant="destructive"
        confirmLabel="Delete"
        onConfirm={handleDelete}
        loading={deleting}
      />
    </>
  )
}

import { useCallback, useState } from 'react'
import { Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Drawer } from '@/components/ui/drawer'
import { EmptyState } from '@/components/ui/empty-state'
import { StaggerGroup, StaggerItem } from '@/components/ui/stagger-group'
import { useCustomRulesStore } from '@/stores/custom-rules'
import { useToastStore } from '@/stores/toast'
import type {
  CustomRule,
  MetricDescriptor,
  RuleListItem as RuleListItemType,
} from '@/api/endpoints/custom-rules'

import { RuleBuilderForm } from './RuleBuilderForm'
import { RuleListItem } from './RuleListItem'

type DrawerView = 'list' | 'builder'

interface RulesDrawerProps {
  open: boolean
  onClose: () => void
  allRules: readonly RuleListItemType[]
  metrics: readonly MetricDescriptor[]
  onRefresh: () => Promise<void>
}

export function RulesDrawer({
  open,
  onClose,
  allRules,
  metrics,
  onRefresh,
}: RulesDrawerProps) {
  const addToast = useToastStore((s) => s.add)
  const [view, setView] = useState<DrawerView>('list')
  const [editRule, setEditRule] = useState<CustomRule | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  const customRules = useCustomRulesStore((s) => s.rules)
  const toggleRule = useCustomRulesStore((s) => s.toggleRule)
  const deleteRule = useCustomRulesStore((s) => s.deleteRule)

  const builtinRules = allRules.filter((r) => r.type === 'builtin')
  const customRulesList = allRules.filter((r) => r.type === 'custom')

  const handleCreateClick = useCallback(() => {
    setEditRule(null)
    setView('builder')
  }, [])

  const handleEditClick = useCallback(
    (id: string) => {
      const rule = customRules.find((r) => r.id === id)
      if (rule) {
        setEditRule(rule)
        setView('builder')
      }
    },
    [customRules],
  )

  const safeRefresh = useCallback(async () => {
    try {
      await onRefresh()
    } catch {
      // onRefresh typically loads the rule list from a parent page;
      // a transient failure there shouldn't swallow the mutation's
      // success but the user still needs to know the list may be
      // stale.
      addToast({
        variant: 'error',
        title: 'Could not refresh',
        description: 'Try again in a moment.',
      })
    }
  }, [onRefresh, addToast])

  const handleBuilderClose = useCallback(async () => {
    setView('list')
    setEditRule(null)
    await safeRefresh()
  }, [safeRefresh])

  const handleToggle = useCallback(
    async (_name: string, id?: string) => {
      if (!id) return
      // Sentinel-return contract: the store owns success/error toasts.
      // Only null-check to decide whether to refresh the list.
      const toggled = await toggleRule(id)
      if (toggled) {
        await safeRefresh()
      }
    },
    [toggleRule, safeRefresh],
  )

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return false
    setDeleting(true)
    // Sentinel-return contract: the store emits both the success and
    // error toast. On success, refresh + close the dialog by clearing
    // deleteTarget; on failure, leave the dialog open so the user can
    // retry without losing their place (returning false tells the
    // ConfirmDialog primitive not to auto-close).
    const ok = await deleteRule(deleteTarget)
    setDeleting(false)
    if (!ok) return false
    setDeleteTarget(null)
    await safeRefresh()
    return true
  }, [deleteTarget, deleteRule, safeRefresh])

  const handleDrawerClose = useCallback(() => {
    setView('list')
    setEditRule(null)
    setDeleteTarget(null)
    setDeleting(false)
    onClose()
  }, [onClose])

  return (
    <>
      <Drawer open={open} onClose={handleDrawerClose} title="Signal Rules">
        {view === 'builder' ? (
          <RuleBuilderForm
            editRule={editRule}
            metrics={metrics}
            onClose={handleBuilderClose}
          />
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <p className="text-body-sm text-muted-foreground">
                {allRules.length} rules configured
              </p>
              <Button size="sm" onClick={handleCreateClick}>
                <Plus className="mr-1 size-3.5" />
                Create Rule
              </Button>
            </div>

            {allRules.length === 0 && (
              <EmptyState
                title="No rules"
                description="Create a custom rule to monitor your org signals."
              />
            )}

            {builtinRules.length > 0 && (
              <section>
                <h4 className="mb-2 text-body-sm font-medium text-muted-foreground">
                  Built-in ({builtinRules.length})
                </h4>
                <StaggerGroup className="flex flex-col gap-2">
                  {builtinRules.map((rule) => (
                    <StaggerItem key={rule.name}>
                      <RuleListItem rule={rule} />
                    </StaggerItem>
                  ))}
                </StaggerGroup>
              </section>
            )}

            {customRulesList.length > 0 && (
              <section>
                <h4 className="mb-2 text-body-sm font-medium text-muted-foreground">
                  Custom ({customRulesList.length})
                </h4>
                <StaggerGroup className="flex flex-col gap-2">
                  {customRulesList.map((rule) => (
                    <StaggerItem key={rule.id ?? rule.name}>
                      <RuleListItem
                        rule={rule}
                        onToggle={handleToggle}
                        onEdit={handleEditClick}
                        onDelete={(id) => setDeleteTarget(id)}
                      />
                    </StaggerItem>
                  ))}
                </StaggerGroup>
              </section>
            )}
          </div>
        )}
      </Drawer>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onConfirm={handleDeleteConfirm}
        title="Delete Custom Rule"
        description="This rule will be permanently deleted. This action cannot be undone."
        variant="destructive"
        confirmLabel="Delete"
        loading={deleting}
      />
    </>
  )
}

import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Tabs } from '@base-ui/react/tabs'
import { AlertTriangle, ArrowLeft, Building2, Info, Settings, Users, WifiOff } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ToggleField } from '@/components/ui/toggle-field'
import { ErrorBoundary } from '@/components/ui/error-boundary'
import type { UpdateCompanyRequest } from '@/api/types'
import { useOrgEditData } from '@/hooks/useOrgEditData'
import { useToastStore } from '@/stores/toast'
import { ROUTES } from '@/router/routes'
import {
  ORG_EDIT_COMING_SOON_DESCRIPTION,
  ORG_EDIT_COMING_SOON_ISSUE,
  ORG_EDIT_COMING_SOON_URL,
} from './org-edit/coming-soon'
import { OrgEditSkeleton } from './org-edit/OrgEditSkeleton'
import { GeneralTab } from './org-edit/GeneralTab'
import { AgentsTab } from './org-edit/AgentsTab'
import { DepartmentsTab } from './org-edit/DepartmentsTab'
import { YamlEditorPanel } from './org-edit/YamlEditorPanel'

type TabValue = 'general' | 'agents' | 'departments'

const isTabValue = (value: string): value is TabValue =>
  value === 'general' || value === 'agents' || value === 'departments'


const TRIGGER_CLASSES = cn(
  'px-4 py-2 text-sm font-medium text-text-secondary transition-colors',
  'data-[active]:text-foreground data-[active]:border-b-2 data-[active]:border-accent',
  'hover:text-foreground',
)

export default function OrgEditPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [yamlMode, setYamlMode] = useState(false)

  const {
    config,
    departmentHealths,
    loading,
    error,
    saving,
    saveError,
    wsConnected,
    wsSetupError,
    updateCompany,
    createDepartment,
    updateDepartment,
    deleteDepartment,
    reorderDepartments,
    createAgent,
    updateAgent,
    deleteAgent,
    reorderAgents,
    createTeam,
    updateTeam,
    deleteTeam,
    reorderTeams,
    optimisticReorderDepartments,
    optimisticReorderAgents,
  } = useOrgEditData()

  const rawTab = searchParams.get('tab') ?? 'general'
  const activeTab: TabValue = isTabValue(rawTab) ? rawTab : 'general'

  const handleTabChange = useCallback(
    (value: TabValue) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value === 'general') {
          next.delete('tab')
        } else {
          next.set('tab', value)
        }
        return next
      })
    },
    [setSearchParams],
  )

  const handleYamlSave = useCallback(
    async (parsed: Record<string, unknown>) => {
      try {
        await updateCompany({
          company_name: typeof parsed.company_name === 'string' ? parsed.company_name : undefined,
          autonomy_level: typeof parsed.autonomy_level === 'string'
            ? (parsed.autonomy_level as UpdateCompanyRequest['autonomy_level'])
            : undefined,
          budget_monthly: typeof parsed.budget_monthly === 'number' ? parsed.budget_monthly : undefined,
          communication_pattern: typeof parsed.communication_pattern === 'string'
            ? parsed.communication_pattern
            : undefined,
        })
        useToastStore.getState().add({ variant: 'success', title: 'Configuration saved' })
      } catch (err) {
        useToastStore.getState().add({ variant: 'error', title: 'Failed to save configuration' })
        throw err
      }
    },
    [updateCompany],
  )

  if (loading && !config) {
    return <OrgEditSkeleton />
  }

  if (!loading && !config) {
    return (
      <div className="space-y-section-gap">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon" aria-label="Back to Org Chart">
            <Link to={ROUTES.ORG}><ArrowLeft className="size-4" /></Link>
          </Button>
          <h1 className="text-lg font-semibold text-foreground">Edit Organization</h1>
        </div>
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {error ?? 'Failed to load organization data.'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-section-gap">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button asChild variant="ghost" size="icon" aria-label="Back to Org Chart">
            <Link to={ROUTES.ORG}><ArrowLeft className="size-4" /></Link>
          </Button>
          <h1 className="text-lg font-semibold text-foreground">Edit Organization</h1>
        </div>
        <ToggleField
          label="YAML"
          checked={yamlMode}
          onChange={setYamlMode}
        />
      </div>

      {/* Error banner */}
      {(error || saveError) && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 p-card text-sm text-danger">
          <AlertTriangle className="size-4 shrink-0" />
          {saveError || error}
        </div>
      )}

      {/* WS disconnect warning */}
      {!wsConnected && !loading && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/5 p-card text-sm text-warning">
          <WifiOff className="size-4 shrink-0" />
          {wsSetupError ?? 'Real-time updates disconnected. Data may be stale.'}
        </div>
      )}

      {/*
       * Read-only gate: the backend has no CRUD endpoints for the
       * company / departments / agents resources yet (see #1081 -- all
       * 9 mutation paths in `api/endpoints/company.ts` return 405).
       * Until those land we keep the page viewable but hide the
       * footguns so operators do not hit silent 405s.  Template packs
       * still work (the `/template-packs/apply` endpoint is live) so
       * operators can still populate a fresh org that way.
       *
       * Remove this banner and every "Coming soon (#1081)" tooltip in
       * `./org-edit/` once the endpoints ship.
       */}
      <div
        role="status"
        className="flex items-start gap-3 rounded-lg border border-accent/30 bg-accent/5 p-card text-sm text-foreground"
      >
        <Info className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden="true" />
        <div className="flex-1">
          <div className="font-semibold">Editing is temporarily read-only</div>
          <p className="mt-1 text-compact text-text-secondary">
            {ORG_EDIT_COMING_SOON_DESCRIPTION}{' '}
            <a
              href={ORG_EDIT_COMING_SOON_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-accent underline hover:no-underline"
            >
              Track progress in #{ORG_EDIT_COMING_SOON_ISSUE}
            </a>
            .
          </p>
        </div>
      </div>

      {/* Content: YAML or tabbed GUI */}
      {yamlMode ? (
        <YamlEditorPanel config={config} onSave={handleYamlSave} saving={saving} />
      ) : (
        <Tabs.Root
          value={activeTab}
          onValueChange={(value: string) => {
            if (isTabValue(value)) {
              handleTabChange(value)
            }
          }}
        >
          {/*
           * Each tab is rendered as a real react-router `<Link>` via the
           * Base UI `render` prop.  Rendering as `<a href>` rather than
           * `<button>` lets the browser treat each tab as a navigable
           * link, which means middle-click, ctrl/cmd-click, and "Open
           * in new tab" from the right-click menu all work the way an
           * operator expects -- identical to the sidebar nav links.
           * The synchronous `onValueChange` handler above still runs on
           * plain left-click so the active tab updates in-place, and
           * Base UI's own click handler calls preventDefault internally
           * to stop the browser from doing a full navigation on left
           * click while still honouring the middle/modified click.
           */}
          <Tabs.List className="flex border-b border-border" aria-label="Organization sections">
            {/*
             * `nativeButton={false}` tells Base UI we are intentionally
             * rendering an `<a>` (via react-router `<Link>`) instead of
             * the default native `<button>`.  Without this prop Base UI
             * warns that native button semantics were lost -- which is
             * true, but it is the price we pay for middle-click / ctrl-
             * click / "Open in new tab" to work the same way as the
             * sidebar nav links.  Keyboard activation still works
             * because Base UI's Tab handler fires on Enter/Space and
             * react-router's Link forwards both to a click handler.
             */}
            <Tabs.Tab
              value="general"
              className={TRIGGER_CLASSES}
              nativeButton={false}
              render={<Link to={ROUTES.ORG_EDIT} />}
            >
              <span className="flex items-center gap-1.5">
                <Settings className="size-3.5" />
                General
              </span>
            </Tabs.Tab>
            <Tabs.Tab
              value="agents"
              className={TRIGGER_CLASSES}
              nativeButton={false}
              render={<Link to={`${ROUTES.ORG_EDIT}?tab=agents`} />}
            >
              <span className="flex items-center gap-1.5">
                <Users className="size-3.5" />
                Agents
              </span>
            </Tabs.Tab>
            <Tabs.Tab
              value="departments"
              className={TRIGGER_CLASSES}
              nativeButton={false}
              render={<Link to={`${ROUTES.ORG_EDIT}?tab=departments`} />}
            >
              <span className="flex items-center gap-1.5">
                <Building2 className="size-3.5" />
                Departments
              </span>
            </Tabs.Tab>
          </Tabs.List>

          <div className="pt-section-gap">
            <Tabs.Panel value="general">
              <ErrorBoundary level="section">
                <GeneralTab config={config} onUpdate={updateCompany} saving={saving} />
              </ErrorBoundary>
            </Tabs.Panel>

            <Tabs.Panel value="agents">
              <ErrorBoundary level="section">
                <AgentsTab
                  config={config}
                  saving={saving}
                  onCreateAgent={createAgent}
                  onUpdateAgent={updateAgent}
                  onDeleteAgent={deleteAgent}
                  onReorderAgents={reorderAgents}
                  optimisticReorderAgents={optimisticReorderAgents}
                />
              </ErrorBoundary>
            </Tabs.Panel>

            <Tabs.Panel value="departments">
              <ErrorBoundary level="section">
                <DepartmentsTab
                  config={config}
                  departmentHealths={departmentHealths}
                  saving={saving}
                  onCreateDepartment={createDepartment}
                  onUpdateDepartment={updateDepartment}
                  onDeleteDepartment={deleteDepartment}
                  onReorderDepartments={reorderDepartments}
                  optimisticReorderDepartments={optimisticReorderDepartments}
                  onCreateTeam={createTeam}
                  onUpdateTeam={updateTeam}
                  onDeleteTeam={deleteTeam}
                  onReorderTeams={reorderTeams}
                />
              </ErrorBoundary>
            </Tabs.Panel>
          </div>
        </Tabs.Root>
      )}
    </div>
  )
}

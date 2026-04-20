import type { WorkflowNodeType } from '@/api/types/workflows'
import { VersionDiffViewer } from './VersionDiffViewer'
import { VersionHistoryPanel } from './VersionHistoryPanel'
import { WorkflowNodeDrawer } from './WorkflowNodeDrawer'

interface WorkflowEditorSidebarProps {
  nodeDrawerOpen: boolean
  onNodeDrawerClose: () => void
  selectedNodeId: string | null
  selectedNodeType: WorkflowNodeType | null
  selectedNodeLabel: string
  selectedNodeConfig: Record<string, unknown>
  onConfigChange: (config: Record<string, unknown>) => void
  versionHistoryOpen: boolean
  onVersionHistoryClose: () => void
}

/** Side panels for the workflow editor: node config drawer + version history + diff viewer. */
export function WorkflowEditorSidebar(props: WorkflowEditorSidebarProps) {
  const {
    nodeDrawerOpen,
    onNodeDrawerClose,
    selectedNodeId,
    selectedNodeType,
    selectedNodeLabel,
    selectedNodeConfig,
    onConfigChange,
    versionHistoryOpen,
    onVersionHistoryClose,
  } = props

  return (
    <>
      <WorkflowNodeDrawer
        open={nodeDrawerOpen}
        onClose={onNodeDrawerClose}
        nodeId={selectedNodeId}
        nodeType={selectedNodeType}
        nodeLabel={selectedNodeLabel}
        config={selectedNodeConfig}
        onConfigChange={onConfigChange}
      />
      <VersionHistoryPanel open={versionHistoryOpen} onClose={onVersionHistoryClose} />
      <VersionDiffViewer />
    </>
  )
}

import { create } from 'zustand'
import { createClipboardSlice } from './clipboard'
import { createGraphSlice } from './graph'
import { createPersistenceSlice } from './persistence'
import { createUndoRedoSlice } from './undo-redo'
import { createValidationSlice } from './validation'
import { createVersionsSlice } from './versions'
import type { WorkflowEditorState } from './types'

export type { WorkflowEditorState } from './types'

export const useWorkflowEditorStore = create<WorkflowEditorState>()((...a) => ({
  ...createGraphSlice(...a),
  ...createUndoRedoSlice(...a),
  ...createValidationSlice(...a),
  ...createClipboardSlice(...a),
  ...createPersistenceSlice(...a),
  ...createVersionsSlice(...a),
}))

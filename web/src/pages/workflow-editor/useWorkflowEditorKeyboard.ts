import { useEffect } from 'react'
import { useWorkflowEditorStore } from '@/stores/workflow-editor'

type EditorMode = 'visual' | 'yaml'

function isTextInput(el: HTMLElement): boolean {
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (el.isContentEditable || el.closest('[contenteditable="true"]')) return true
  return false
}

/** Cmd/Ctrl+C and Cmd/Ctrl+V for copy/paste in the visual editor. */
export function useWorkflowEditorKeyboard(editorMode: EditorMode) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (!(e.ctrlKey || e.metaKey)) return
      if (editorMode !== 'visual') return
      const el = e.target as HTMLElement
      if (isTextInput(el)) return
      if (e.key === 'c') {
        e.preventDefault()
        useWorkflowEditorStore.getState().copySelectedNodes()
      } else if (e.key === 'v') {
        e.preventDefault()
        useWorkflowEditorStore.getState().pasteNodes()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [editorMode])
}

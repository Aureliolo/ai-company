import { Suspense, lazy } from 'react'
import { SkeletonCard } from './skeleton'
import type { CodeMirrorEditorProps } from './code-mirror-editor'

const CodeMirrorEditor = lazy(() =>
  import('./code-mirror-editor').then((m) => ({ default: m.CodeMirrorEditor })),
)

/**
 * Lazy-loaded CodeMirror editor that defers the ~200KB+ CodeMirror bundle
 * until the component is first rendered.
 *
 * Drop-in replacement for CodeMirrorEditor with identical props.
 */
export function LazyCodeMirrorEditor(props: CodeMirrorEditorProps) {
  return (
    <Suspense fallback={<SkeletonCard lines={8} />}>
      <CodeMirrorEditor {...props} />
    </Suspense>
  )
}

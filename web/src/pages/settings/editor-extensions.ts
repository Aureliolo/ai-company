/**
 * CodeMirror extensions for the Settings code editor.
 *
 * Re-exports from focused modules:
 * - {@link editor-diff} -- Diff gutter markers
 * - {@link editor-linter} -- Inline validation (syntax + schema)
 * - {@link editor-autocomplete} -- Schema-aware autocomplete
 */

export { computeLineDiff, dispatchDiff, diffGutterExtension } from './editor-diff'
export type { LineDiff, LineDiffKind } from './editor-diff'

export { settingsLinterExtension, validateSchema, buildSchemaInfo } from './editor-linter'
export type { SchemaInfo } from './editor-linter'

export { settingsAutocompleteExtension } from './editor-autocomplete'

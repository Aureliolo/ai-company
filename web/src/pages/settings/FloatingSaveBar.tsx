import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, Save, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export interface FloatingSaveBarProps {
  dirtyCount: number
  saving: boolean
  onSave: () => void
  onDiscard: () => void
  saveError: string | null
}

export function FloatingSaveBar({
  dirtyCount,
  saving,
  onSave,
  onDiscard,
  saveError,
}: FloatingSaveBarProps) {
  return (
    <AnimatePresence>
      {dirtyCount > 0 && (
        <motion.div
          initial={{ y: 80, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 80, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="sticky bottom-4 z-10 mx-auto flex w-fit items-center gap-3 rounded-lg border border-border bg-surface px-4 py-2.5 shadow-lg"
        >
          <span className="text-sm text-text-secondary">
            {dirtyCount} unsaved {dirtyCount === 1 ? 'change' : 'changes'}
          </span>

          {saveError && (
            <span
              className="max-w-[40ch] break-words text-xs text-danger"
              role="alert"
              aria-live="assertive"
            >
              {saveError}
            </span>
          )}

          <Button variant="ghost" size="sm" onClick={onDiscard} disabled={saving}>
            <Undo2 className="mr-1.5 size-3.5" aria-hidden />
            Discard
          </Button>

          <Button size="sm" onClick={onSave} disabled={saving}>
            {saving ? (
              <Loader2 className="mr-1.5 size-3.5 animate-spin" aria-hidden />
            ) : (
              <Save className="mr-1.5 size-3.5" aria-hidden />
            )}
            Save
          </Button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

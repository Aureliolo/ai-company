import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { springDefault } from '@/lib/motion'
import { Loader2, Save, Undo2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'

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
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false)

  return (
    <>
      <AnimatePresence>
        {dirtyCount > 0 && (
          <motion.div
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={springDefault}
            className="sticky bottom-4 z-10 mx-auto flex w-fit items-center gap-3 rounded-lg border border-border bg-surface p-card shadow-[var(--so-shadow-card-hover)]"
            aria-live="polite"
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

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDiscardConfirm(true)}
              disabled={saving}
            >
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

      <ConfirmDialog
        open={showDiscardConfirm}
        onOpenChange={setShowDiscardConfirm}
        title="Discard changes?"
        description={`You have ${dirtyCount} unsaved ${dirtyCount === 1 ? 'change' : 'changes'}. This cannot be undone.`}
        confirmLabel="Discard"
        variant="destructive"
        onConfirm={() => {
          setShowDiscardConfirm(false)
          onDiscard()
        }}
      />
    </>
  )
}

import { Children, cloneElement, isValidElement } from 'react'
import type { HTMLAttributes, ReactNode, Ref } from 'react'
import { mergeProps } from '@base-ui/react/merge-props'

/**
 * Local polymorphism primitive used by {@link Button} (and any future component
 * that wants the `asChild` ergonomic). Clones its only child and merges the
 * passed props onto it using Base UI's {@link mergeProps}, which handles
 * className concatenation and event-handler chaining with the same semantics as
 * Base UI components.
 *
 * This preserves our existing `asChild` API across every `<Button asChild>`
 * call site while the rest of the codebase migrates to Base UI's native
 * `render` prop pattern. For primitives that come directly from
 * `@base-ui/react/*` (Dialog, AlertDialog, Popover, etc.), prefer their
 * `render` prop instead of this helper.
 *
 * `Children.only` and `cloneElement` are intentional here -- they are the only
 * way to implement Slot semantics. The helper is tightly scoped to `<Button
 * asChild>`, so the "fragility" lint warnings do not apply.
 */
export interface SlotProps extends HTMLAttributes<HTMLElement> {
  children?: ReactNode
  ref?: Ref<HTMLElement>
}

export function Slot({ children, ref, ...slotProps }: SlotProps) {
  // eslint-disable-next-line @eslint-react/no-children-only -- Slot requires exactly one child
  const child = Children.only(children)
  if (!isValidElement<Record<string, unknown>>(child)) {
    return child
  }

  const childProps = (child.props ?? {}) as Record<string, unknown>
  const merged = mergeProps<'div'>(slotProps as Record<string, unknown>, childProps)

  // eslint-disable-next-line @eslint-react/no-clone-element -- required for Slot semantics
  return cloneElement(child, {
    ...merged,
    ref,
  } as Record<string, unknown>)
}

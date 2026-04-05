import { Children, cloneElement, isValidElement } from 'react'
import type { HTMLAttributes, ReactNode, Ref, MutableRefObject } from 'react'
import { mergeProps } from '@base-ui/react/merge-props'

/**
 * Local polymorphism primitive used by {@link Button} for its `asChild` prop.
 *
 * Clones its only child and merges the passed props onto it using Base UI's
 * {@link mergeProps}, which handles className concatenation and event-handler
 * chaining with the same semantics as Base UI components. For primitives that
 * come directly from `@base-ui/react/*` (Dialog, AlertDialog, Popover, etc.),
 * prefer their native `render` prop instead of this helper -- `<Slot>` exists
 * only to keep the `<Button asChild>` ergonomic working for consumers that
 * would otherwise need to spread props manually.
 *
 * `Children.only` and `cloneElement` are intentional here -- they are the only
 * way to implement Slot semantics. The helper is tightly scoped to `<Button
 * asChild>`, so the "fragility" lint warnings do not apply.
 */
export interface SlotProps extends HTMLAttributes<HTMLElement> {
  children?: ReactNode
  ref?: Ref<HTMLElement>
}

function composeRefs<T>(
  ...refs: Array<Ref<T> | undefined>
): (node: T | null) => void {
  return (node) => {
    for (const ref of refs) {
      if (typeof ref === 'function') {
        ref(node)
      } else if (ref !== undefined && ref !== null) {
        ;(ref as MutableRefObject<T | null>).current = node
      }
    }
  }
}

export function Slot({ children, ref, ...slotProps }: SlotProps) {
  // eslint-disable-next-line @eslint-react/no-children-only -- Slot requires exactly one child
  const child = Children.only(children)
  if (!isValidElement<Record<string, unknown>>(child)) {
    if (import.meta.env.DEV) {
      console.warn(
        '[Slot] asChild received a non-element child. Props were not forwarded. ' +
          'Wrap the content in a single React element.',
      )
    }
    return child
  }

  const childProps = (child.props ?? {}) as Record<string, unknown>
  const merged = mergeProps(slotProps as Record<string, unknown>, childProps)

  // Compose the Slot's own ref with any ref the child element carries so
  // neither is silently dropped when both are provided (React 19 exposes
  // child refs via `child.props.ref`).
  const childRef = (childProps.ref ?? undefined) as Ref<HTMLElement> | undefined
  const mergedRef = composeRefs<HTMLElement>(ref, childRef)

  // eslint-disable-next-line @eslint-react/no-clone-element -- required for Slot semantics
  return cloneElement(child, {
    ...merged,
    ref: mergedRef,
  } as Record<string, unknown>)
}

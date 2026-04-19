import '@testing-library/jest-dom/vitest'
import { createElement } from 'react'
import type { ComponentProps, ReactNode, Ref } from 'react'
import { afterAll, afterEach, beforeAll, beforeEach, vi } from 'vitest'
import { MotionGlobalConfig } from 'motion/react'
import { setupServer } from 'msw/node'
import { useToastStore } from '@/stores/toast'
import { cancelPendingPersist } from '@/stores/notifications'
import { defaultHandlers } from '@/mocks/handlers'

// Global MSW server: every default endpoint handler is registered up front
// so tests that do not configure their own overrides get a predictable
// happy-path response for any request. Requests that fall through to a
// path with no handler fail the test loudly (`onUnhandledRequest: 'error'`)
// so new endpoints cannot ship without a matching default handler.
export const server = setupServer(...defaultHandlers)

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' })
})

beforeEach(() => {
  // The axios client attaches X-CSRF-Token on mutating requests by reading
  // the `csrf_token` cookie. Re-seed on every test so a test that clears
  // or mutates cookies cannot leak into the next test. MSW does not
  // validate the value.
  document.cookie = 'csrf_token=test-csrf-token; path=/'
})

afterEach(() => {
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})

// Short-circuit every Motion animation so framer-motion does not leave
// `AnimationComplete` promise chains pending past test teardown. This is
// the canonical test hook documented at https://motion.dev/docs/testing
// and resolves animation promises instantly instead of via rAF.
MotionGlobalConfig.skipAnimations = true

// Even with `skipAnimations`, framer-motion still creates a Promise in
// `MotionValue.start` and schedules its resolution through the next frame
// (rAF, polyfilled by jsdom as setInterval). Under vitest with
// `--detect-async-leaks` those promises are flagged. Replacing `motion.*`
// with plain host elements and `AnimatePresence` with a passthrough removes
// the animation code path entirely. Tests that assert on motion-specific
// behavior can still opt out via their own `vi.mock('motion/react', ...)`.
vi.mock('motion/react', async () => {
  const actual = await vi.importActual<typeof import('motion/react')>('motion/react')

  type MotionStubProps = ComponentProps<'div'> & {
    ref?: Ref<HTMLElement>
    children?: ReactNode
  } & Record<string, unknown>

  const MOTION_ONLY_PROPS = new Set([
    'animate', 'initial', 'exit', 'transition', 'variants', 'whileHover',
    'whileTap', 'whileFocus', 'whileDrag', 'whileInView', 'layout',
    'layoutId', 'layoutDependency', 'layoutScroll', 'drag', 'dragConstraints',
    'dragElastic', 'dragMomentum', 'dragTransition', 'dragSnapToOrigin',
    'dragControls', 'dragListener', 'onAnimationStart', 'onAnimationComplete',
    'onUpdate', 'onDragStart', 'onDrag', 'onDragEnd', 'onDirectionLock',
    'onHoverStart', 'onHoverEnd', 'onTapStart', 'onTap', 'onTapCancel',
    'onViewportEnter', 'onViewportLeave', 'viewport', 'custom', 'inherit',
  ])

  const makeMotionComponent = (tag: string) => {
    return function MotionStub({ children, ref, style, ...rest }: MotionStubProps) {
      const domProps: Record<string, unknown> = {}
      for (const [key, value] of Object.entries(rest)) {
        if (!MOTION_ONLY_PROPS.has(key)) domProps[key] = value
      }
      // Preserve plain-object style values; drop motion-value-backed entries.
      const plainStyle =
        style && typeof style === 'object'
          ? Object.fromEntries(
              Object.entries(style).filter(
                ([, v]) =>
                  v === null
                  || ['string', 'number', 'boolean'].includes(typeof v),
              ),
            )
          : undefined
      return createElement(
        tag,
        { ref, style: plainStyle, ...domProps },
        children,
      )
    }
  }

  const motionProxy = new Proxy({} as typeof actual.motion, {
    get(_target, prop) {
      if (typeof prop !== 'string') return undefined
      return makeMotionComponent(prop)
    },
  })

  return {
    ...actual,
    motion: motionProxy,
    AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  }
})

// jsdom polyfills `requestAnimationFrame` with a shared `setInterval` that
// only clears when every registered callback has fired. Recharts's
// `ZIndexPortal` registers rAF callbacks via @reduxjs/toolkit that keep
// getting re-scheduled, so the interval outlives the test and
// --detect-async-leaks flags it as a Timeout leak. Replace rAF with
// `setTimeout(cb, 0)` so each frame is a discrete macrotask that drains
// cleanly between tests.
//
// We intentionally do NOT drain pending rAF callbacks in the global
// afterEach: d3-timer (used by d3-force in `pages/org/force-layout.ts`)
// binds `setFrame` to our shim at module load time and relies on its
// wake() callback firing to clear its internal `setInterval(poke)` after
// `simulation.stop()`. Clearing the shim's setTimeout handles before
// wake() can run strands that interval and reintroduces a leak.
if (typeof window !== 'undefined') {
  const timers = new Set<ReturnType<typeof setTimeout>>()
  window.requestAnimationFrame = (callback: FrameRequestCallback): number => {
    const handle = setTimeout(() => {
      timers.delete(handle)
      callback(performance.now())
    }, 0)
    timers.add(handle)
    return handle as unknown as number
  }
  window.cancelAnimationFrame = (handle: number) => {
    clearTimeout(handle as unknown as ReturnType<typeof setTimeout>)
    timers.delete(handle as unknown as ReturnType<typeof setTimeout>)
  }
}

// jsdom does not implement matchMedia; several components (the breakpoint
// hook, the theme store, a few prefers-* consumers) call it during render.
// Provide a no-op shim that reports `matches: false` for every query so the
// default render path is used. Motion's animation short-circuit is handled
// by the mock above; we explicitly do NOT force reduced-motion here because
// hook tests (useFlash, useCountAnimation) pin their behavior to the
// non-reduced branch.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

// Toast store schedules a `setTimeout` per auto-dismiss (success / info toasts
// with a real timer). Without a global teardown hook these timers survive the
// test boundary and vitest flags them as leaked. `dismissAll()` clears both
// the pending handles and the toasts array in one idiomatic call; tests that
// need to inspect the toasts list after pending timers drain can instead call
// `cancelAllPending()` directly in their own teardown.
//
// We run this in `afterEach` (not `beforeEach`) deliberately: the test body's
// assertions on toast state complete *before* the afterEach fires, so
// resetting here does not mask in-test assertions. A test that needs toast
// state to persist across a teardown boundary (e.g. asserting a toast is
// still visible after a dialog closes) should inline its own assertion
// within the test body, never rely on post-teardown state.
afterEach(() => {
  useToastStore.getState().dismissAll()
  // Notifications store debounces localStorage persistence with a 300ms
  // setTimeout; drop any pending handle so it does not outlive the test.
  cancelPendingPersist()
})

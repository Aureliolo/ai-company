import '@testing-library/jest-dom/vitest'
import { createElement } from 'react'
import type { ComponentProps, ReactNode, Ref } from 'react'
import { afterEach, vi } from 'vitest'
import { MotionGlobalConfig } from 'motion/react'
import { useToastStore } from '@/stores/toast'
import { cancelPendingPersist } from '@/stores/notifications'

// AuthGuard calls `useSettingsStore.getState().fetchLocale()` from a
// `useEffect` whenever the user becomes authenticated. Without a global
// mock that call reaches the real axios client, returns 401 (no backend
// in jsdom), and leaks as an UNDICI_REQUEST + PROMISE past test teardown.
// Individual tests can still override these endpoints with their own
// `vi.mock('@/api/endpoints/settings', ...)` call.
vi.mock('@/api/endpoints/settings', async () => {
  const actual = await vi.importActual<typeof import('@/api/endpoints/settings')>(
    '@/api/endpoints/settings',
  )
  return {
    ...actual,
    getSchema: vi.fn().mockResolvedValue([]),
    getNamespaceSchema: vi.fn().mockResolvedValue([]),
    getAllSettings: vi.fn().mockResolvedValue([]),
    getNamespaceSettings: vi.fn().mockResolvedValue([]),
    updateSetting: vi.fn().mockResolvedValue(undefined),
    deleteSetting: vi.fn().mockResolvedValue(undefined),
    restartServer: vi.fn().mockResolvedValue(undefined),
    listSinks: vi.fn().mockResolvedValue([]),
    testSink: vi.fn().mockResolvedValue({ ok: true }),
  }
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
// test boundary and vitest flags them as leaked. `cancelAllPending()` clears
// the handles; resetting `toasts` keeps subsequent tests isolated.
afterEach(() => {
  useToastStore.getState().cancelAllPending()
  useToastStore.setState({ toasts: [] })
  // Notifications store debounces localStorage persistence with a 300ms
  // setTimeout; drop any pending handle so it does not outlive the test.
  cancelPendingPersist()
})

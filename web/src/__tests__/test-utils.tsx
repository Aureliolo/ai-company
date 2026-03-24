import type { ReactNode } from 'react'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { RouteObject } from 'react-router'

interface RenderWithRouterOptions {
  initialEntries?: string[]
  routes?: RouteObject[]
}

/**
 * Render a component or route tree inside a memory router.
 *
 * For simple component renders, pass `element` as the only route.
 * For testing route configurations, pass `routes` directly.
 */
export function renderWithRouter(
  element: ReactNode,
  { initialEntries = ['/'] }: RenderWithRouterOptions = {},
) {
  const router = createMemoryRouter(
    [{ path: '*', element }],
    { initialEntries },
  )
  return { ...render(<RouterProvider router={router} />), router }
}

/**
 * Render a full route tree inside a memory router.
 */
export function renderRoutes(
  routes: RouteObject[],
  { initialEntries = ['/'] }: Pick<RenderWithRouterOptions, 'initialEntries'> = {},
) {
  const router = createMemoryRouter(routes, { initialEntries })
  return { ...render(<RouterProvider router={router} />), router }
}

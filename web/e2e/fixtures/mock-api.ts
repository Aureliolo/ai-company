import type { Page } from '@playwright/test'
import { DEFAULT_CURRENCY } from '@/utils/currencies'

/**
 * Mock all API endpoints with deterministic data for screenshot testing.
 *
 * Intercepts /api/* requests and returns static JSON responses.
 * This ensures visual regression screenshots are deterministic
 * regardless of backend state.
 */
export async function mockApiRoutes(page: Page) {
  // Liveness -- always 200 while the process is alive.
  await page.route('**/api/v1/healthz', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          status: 'ok',
          version: '0.6.4',
          uptime_seconds: 0,
        },
        error: null,
        error_detail: null,
      },
    }),
  )

  // Readiness -- returns the full ``ApiResponse<ReadinessStatus>``
  // envelope so the dashboard's ``unwrap()`` call gets the expected
  // ``data`` shape (a bare ``{ status: 'ok' }`` response would fail
  // ``unwrap()`` validation since the wrapper expects ``success`` +
  // ``data`` at the top level).
  await page.route('**/api/v1/readyz', (route) =>
    route.fulfill({
      json: {
        success: true,
        data: {
          status: 'ok',
          persistence: true,
          message_bus: true,
          telemetry: 'disabled',
          version: '0.6.4',
          uptime_seconds: 0,
        },
        error: null,
        error_detail: null,
      },
    }),
  )

  // Auth ticket for WebSocket
  await page.route('**/api/v1/auth/ws-ticket', (route) =>
    route.fulfill({ json: { ticket: 'mock-ticket' } }),
  )

  // Overview metrics
  await page.route('**/api/v1/analytics/overview', (route) =>
    route.fulfill({
      json: {
        total_agents: 8,
        active_agents_count: 5,
        idle_agents_count: 3,
        total_tasks: 24,
        tasks_by_status: {
          created: 2,
          assigned: 4,
          in_progress: 6,
          in_review: 3,
          completed: 7,
          blocked: 1,
          failed: 0,
          interrupted: 1,
          cancelled: 0,
        },
        total_cost: 127.43,
        budget_remaining: 372.57,
        budget_used_percent: 25.5,
        currency: DEFAULT_CURRENCY,
        cost_7d_trend: [
          { timestamp: '2026-03-23T00:00:00Z', value: 15.2 },
          { timestamp: '2026-03-24T00:00:00Z', value: 18.7 },
          { timestamp: '2026-03-25T00:00:00Z', value: 22.1 },
          { timestamp: '2026-03-26T00:00:00Z', value: 19.3 },
          { timestamp: '2026-03-27T00:00:00Z', value: 25.8 },
          { timestamp: '2026-03-28T00:00:00Z', value: 12.9 },
          { timestamp: '2026-03-29T00:00:00Z', value: 13.4 },
        ],
      },
    }),
  )

  // Catch-all for other API routes -- return empty success with ApiResponse envelope
  await page.route('**/api/v1/**', (route) =>
    route.fulfill({
      json: {
        data: [],
        error: null,
        error_detail: null,
        success: true,
        pagination: { total: 0, offset: 0, limit: 10 },
      },
    }),
  )
}

/**
 * Freeze Date.now() for deterministic timestamp rendering.
 */
export async function freezeTime(page: Page) {
  await page.addInitScript(() => {
    const fixedTime = new Date('2026-03-29T12:00:00Z').getTime()
    Date.now = () => fixedTime
  })
}

/**
 * Wait for fonts to load before taking screenshots.
 */
export async function waitForFonts(page: Page) {
  await page.evaluate(() => document.fonts.ready)
}

import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

/**
 * Critical-flow E2E: setup wizard.
 *
 * Verifies the wizard loads and at least the first step renders its
 * title. Deeper multi-step coverage (navigation, validation,
 * submission) is tracked in the follow-up E2E expansion issue.
 */

test.describe('Setup wizard critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the setup wizard root with its first-step heading', async ({ page }) => {
    await page.goto('/setup')
    await expect(page).toHaveURL(/\/setup/)
    // The main region mounts on first paint.
    await expect(page.locator('main')).toBeVisible()
    // Assert the wizard actually rendered a heading (not just that
    // the generic <main> container is present). The wizard renders
    // its step title as an ``h1`` / ``h2`` element; matching by
    // role keeps the assertion resilient to copy edits.
    await expect(page.getByRole('heading').first()).toBeVisible()
  })
})

import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Agent creation critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the agents list page', async ({ page }) => {
    await page.goto('/agents')
    await expect(page).toHaveURL(/\/agents/)
    await expect(page.locator('main')).toBeVisible()
  })
})

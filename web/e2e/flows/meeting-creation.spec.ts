import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Meeting creation critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the meetings list page', async ({ page }) => {
    await page.goto('/meetings')
    await expect(page).toHaveURL(/\/meetings/)
    await expect(page.locator('main')).toBeVisible()
  })
})

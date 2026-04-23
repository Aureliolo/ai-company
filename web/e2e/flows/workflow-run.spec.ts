import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Workflow run critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the workflows list page', async ({ page }) => {
    await page.goto('/workflows')
    await expect(page).toHaveURL(/\/workflows/)
    await expect(page.locator('main')).toBeVisible()
  })
})

import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Provider probe critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the providers list page', async ({ page }) => {
    await page.goto('/providers')
    await expect(page).toHaveURL(/\/providers/)
    await expect(page.locator('main')).toBeVisible()
  })
})

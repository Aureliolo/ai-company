import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Budget check critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the budget page', async ({ page }) => {
    await page.goto('/budget')
    await expect(page).toHaveURL(/\/budget/)
    await expect(page.locator('main')).toBeVisible()
  })
})

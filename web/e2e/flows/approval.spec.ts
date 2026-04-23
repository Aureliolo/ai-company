import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Approval critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the approvals page', async ({ page }) => {
    await page.goto('/approvals')
    await expect(page).toHaveURL(/\/approvals/)
    await expect(page.locator('main')).toBeVisible()
  })
})

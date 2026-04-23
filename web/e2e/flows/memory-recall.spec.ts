import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime } from '../fixtures/mock-api'

test.describe('Memory recall critical flow', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
  })

  test('loads the ontology page where memory surfaces live', async ({ page }) => {
    await page.goto('/ontology')
    await expect(page).toHaveURL(/\/ontology/)
    await expect(page.locator('main')).toBeVisible()
  })
})

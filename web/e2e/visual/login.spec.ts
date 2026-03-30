import { test, expect } from '@playwright/test'
import { freezeTime, waitForFonts } from '../fixtures/mock-api'

test.describe('Login page visual regression', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
  })

  test('login page screenshot', async ({ page }) => {
    await page.goto('/login')
    await waitForFonts(page)
    await expect(page).toHaveScreenshot('login.png')
  })
})

import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime, waitForFonts } from '../fixtures/mock-api'

test.describe('Dashboard visual regression', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
    // Set auth token to bypass login
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token')
      // Set expiration far in the future (auth store checks this on init)
      localStorage.setItem('auth_token_expires_at', String(Date.now() + 86400000))
    })
  })

  test('dashboard page screenshot', async ({ page }) => {
    await page.goto('/')
    await waitForFonts(page)
    // Wait for content to load
    await page.waitForSelector('h1')
    await expect(page).toHaveScreenshot('dashboard.png')
  })
})

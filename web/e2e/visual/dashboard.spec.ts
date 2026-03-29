import { test, expect } from '@playwright/test'
import { mockApiRoutes, freezeTime, waitForFonts } from '../fixtures/mock-api'

test.describe('Dashboard visual regression', () => {
  test.beforeEach(async ({ page }) => {
    await freezeTime(page)
    await mockApiRoutes(page)
    // Set auth token to bypass login
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token')
      localStorage.setItem('auth_user', JSON.stringify({
        username: 'admin',
        role: 'admin',
      }))
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

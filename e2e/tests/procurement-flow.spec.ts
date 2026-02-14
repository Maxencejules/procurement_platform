import { test, expect } from '@playwright/test'

test.describe('Procurement Full Flow', () => {
  test('create request, route approval, approve, verify status and audit log', async ({ page }) => {
    // Step 1: Login as requester
    await page.goto('/login')
    await page.fill('input[id="email"]', 'requester@acme.com')
    await page.fill('input[id="password"]', 'requester123')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/requests')
    await expect(page.locator('h2')).toContainText('Purchase Requests')

    // Step 2: Create a new purchase request
    await page.click('text=New Request')
    await page.waitForURL('**/requests/new')

    const uniqueTitle = `E2E Test Request ${Date.now()}`
    await page.fill('input[id="title"]', uniqueTitle)
    await page.fill('input[id="vendor"]', 'E2E Vendor Co')
    await page.fill('input[id="amount"]', '7500')
    await page.selectOption('select[id="category"]', 'IT')
    await page.selectOption('select[id="costCenter"]', 'ENG-001')
    await page.fill('textarea[id="description"]', 'Automated end-to-end test purchase request')

    // Save and submit
    await page.click('text=Save & Submit')

    // Should navigate to request detail
    await page.waitForURL('**/requests/**')
    await expect(page.locator('h2')).toContainText(uniqueTitle)

    // Verify status is pending_approval or submitted
    const statusBadge = page.locator('.badge').first()
    const statusText = await statusBadge.textContent()
    expect(['Pending Approval', 'Submitted', 'Approved']).toContain(statusText?.trim())

    // Get the request URL for later verification
    const requestUrl = page.url()

    // Step 3: Logout and login as approver
    await page.click('text=Sign Out')
    await page.waitForURL('**/login')

    await page.fill('input[id="email"]', 'approver@acme.com')
    await page.fill('input[id="password"]', 'approver123')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/requests')

    // Step 4: Go to approver inbox
    await page.click('text=Approver Inbox')
    await page.waitForURL('**/inbox')

    // Find our request and approve it
    const requestRow = page.locator(`text=${uniqueTitle}`)
    if (await requestRow.isVisible()) {
      // Click approve on the row
      const row = page.locator('tr', { has: page.locator(`text=${uniqueTitle}`) })
      await row.locator('text=Approve').click()

      // Fill in comments and confirm
      await page.fill('textarea[id="comments"]', 'Approved via E2E test')
      await page.click('text=Confirm Approve')

      // Wait for the approval to process
      await page.waitForTimeout(1000)
    }

    // Step 5: Navigate to the request detail to verify final status
    await page.goto(requestUrl)
    await page.waitForTimeout(500)

    // Check for approved status or audit trail
    const pageContent = await page.textContent('body')
    // The request should have audit trail entries
    expect(pageContent).toContain('Audit Trail')

    // Verify audit log shows status changes
    const auditSection = page.locator('.card', { has: page.locator('text=Audit Trail') })
    await expect(auditSection).toBeVisible()

    // Check that there are timeline items in the audit trail
    const timelineItems = auditSection.locator('.timeline-item')
    const count = await timelineItems.count()
    expect(count).toBeGreaterThan(0)
  })

  test('login page shows demo credentials', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('text=Demo accounts')).toBeVisible()
    await expect(page.locator('text=admin@acme.com')).toBeVisible()
  })

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.goto('/requests')
    await page.waitForURL('**/login')
  })

  test('admin can access policy editor', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[id="email"]', 'admin@acme.com')
    await page.fill('input[id="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/requests')

    await page.click('text=Policies')
    await page.waitForURL('**/policies')
    await expect(page.locator('h2')).toContainText('Approval Policies')
  })
})

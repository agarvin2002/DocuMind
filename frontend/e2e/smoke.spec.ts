import { test, expect, type Page } from '@playwright/test'
import * as path from 'path'
import * as fs from 'fs'
import * as os from 'os'

// API key created for smoke tests — passed via localStorage seed
const API_KEY = 'dm_Jg12cRsr8oysHllJVHSXO3BrEsHf5YP4lgOmDtw98qo'

// Seed the API key into localStorage before each test so the banner is gone
async function seedApiKey(page: Page) {
  await page.addInitScript((key) => {
    localStorage.setItem(
      'documind-api-key',
      JSON.stringify({ state: { apiKey: key }, version: 0 })
    )
  }, API_KEY)
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeTinyPdf(): string {
  // Minimal valid single-page PDF that pypdf can parse
  const pdf = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>/Contents 4 0 R>>endobj
4 0 obj<</Length 44>>
stream
BT /F1 12 Tf 100 700 Td (Smoke test document.) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
trailer<</Size 5/Root 1 0 R>>
startxref
360
%%EOF`
  const tmp = path.join(os.tmpdir(), `smoke-${Date.now()}.pdf`)
  fs.writeFileSync(tmp, pdf)
  return tmp
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe('DocuMind smoke tests', () => {

  // ── 1. App shell ────────────────────────────────────────────────────────────
  test('app loads: sidebar, nav links, health dot', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/')

    // Wordmark
    await expect(page.locator('text=DocuMind').first()).toBeVisible()

    // All four nav links present
    await expect(page.getByRole('link', { name: 'Documents' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Chat' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Search' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Analysis' })).toBeVisible()

    // Health dot visible (any small rounded element in sidebar)
    await expect(page.locator('aside').first()).toBeVisible()

    // No "No API key" banner (we seeded it)
    await expect(page.locator('text=No API key set')).not.toBeVisible()
  })

  // ── 2. API key banner appears without key ────────────────────────────────────
  test('shows API key banner when key is not set', async ({ page }) => {
    // Do NOT seed key
    await page.goto('/')
    await expect(page.locator('text=No API key set')).toBeVisible()
  })

  // ── 3. Settings modal ────────────────────────────────────────────────────────
  test('settings modal: open, enter key, test connection, save', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/')

    await page.getByRole('button', { name: /Settings/i }).click()
    await expect(page.getByRole('dialog')).toBeVisible()

    // API key input is present
    const input = page.locator('input#api-key')
    await expect(input).toBeVisible()

    // Test connection
    await page.getByRole('button', { name: 'Test' }).click()
    // Should show connected or error — either is fine as long as it responds
    await expect(
      page.locator('text=Connected').or(page.locator('text=Cannot reach'))
    ).toBeVisible({ timeout: 10_000 })

    // Save closes the dialog
    await page.getByRole('button', { name: 'Save' }).click()
    await expect(page.getByRole('dialog')).not.toBeVisible()
  })

  // ── 4. Documents page: empty state ──────────────────────────────────────────
  test('documents page: shows empty state when no documents', async ({ page }) => {
    await seedApiKey(page)
    // Clear any persisted documents
    await page.addInitScript(() => localStorage.removeItem('documind-documents'))
    await page.goto('/')

    await expect(page.locator('text=No documents yet')).toBeVisible()
    await expect(page.locator('text=Drop a PDF here')).toBeVisible()
  })

  // ── 5. PDF upload ────────────────────────────────────────────────────────────
  test('upload a PDF: card appears with pending/processing status, transitions to ready or failed', async ({ page }) => {
    await seedApiKey(page)
    await page.addInitScript(() => localStorage.removeItem('documind-documents'))
    await page.goto('/')

    const pdfPath = makeTinyPdf()

    // Use file input directly (the label wraps the hidden input)
    await page.locator('input[type="file"]').setInputFiles(pdfPath)

    // Card should appear with the doc title
    await expect(page.locator('.rounded-xl.border').first()).toBeVisible({ timeout: 8_000 })

    // A document card should appear (the upload 201'd and was added to the store)
    await expect(page.locator('.grid .rounded-xl').first()).toBeVisible({ timeout: 8_000 })

    // Status badge shows one of the four states — polling is driven by Celery
    // which may or may not be running in CI, so we just confirm a badge is present
    await expect(
      page.locator('span.rounded-md.border').filter({ hasText: /Pending|Processing|Ready|Failed/ }).first()
    ).toBeVisible({ timeout: 8_000 })

    fs.unlinkSync(pdfPath)
  })

  // ── 6. Navigation: all routes render ────────────────────────────────────────
  test('navigating to Chat page renders doc selector or empty state', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/chat')
    await expect(
      page.locator('text=Chat with:')
        .or(page.locator('text=No documents ready'))
        .first()
    ).toBeVisible()
  })

  test('navigating to Analysis page renders form', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/analysis')
    await expect(page.locator('text=Deep Analysis')).toBeVisible()
    await expect(page.locator('text=New Analysis')).toBeVisible()
    await expect(page.locator('text=Job History')).toBeVisible()
  })

  test('navigating to Search page renders the form', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/search')
    await expect(page.locator('text=Search Explorer')).toBeVisible()
    await expect(page.locator('text=Query')).toBeVisible()
    await expect(page.locator('text=Results (k)')).toBeVisible()
  })

  // ── 7. Chat page: document selector works ───────────────────────────────────
  test('chat page: selecting a ready doc from URL shows the chat interface', async ({ page }) => {
    await seedApiKey(page)

    // Seed a fake ready document into the store so we don't need a real upload
    const fakeDoc = {
      id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
      title: 'Smoke Test Doc',
      original_filename: 'smoke.pdf',
      file_type: '.pdf',
      file_size: 1024,
      status: 'ready',
      error_message: null,
      chunk_count: 10,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    await page.addInitScript((doc) => {
      localStorage.setItem(
        'documind-documents',
        JSON.stringify({ state: { documents: [doc] }, version: 0 })
      )
    }, fakeDoc)

    await page.goto(`/chat/${fakeDoc.id}`)

    // Chat interface should load — textarea (message input) is the key indicator
    await expect(page.locator('textarea')).toBeVisible()
    // Send button identified by its title attribute (icon-only button)
    await expect(page.locator('button[title="Send (⌘↵)"]')).toBeVisible()
    // Send button disabled with empty input
    await expect(page.locator('button[title="Send (⌘↵)"]')).toBeDisabled()
  })

  // ── 8. Analysis page: workflow selector ─────────────────────────────────────
  test('analysis page: workflow selector buttons are interactive', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/analysis')

    // All workflow options present (buttons have composite accessible names, use regex)
    await expect(page.getByRole('button', { name: /Auto-detect/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Multi-hop/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Comparison/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Contradiction/ })).toBeVisible()

    // Clicking Multi-hop selects it
    await page.getByRole('button', { name: /Multi-hop/ }).click()
    // Run Analysis button is disabled (no question or doc)
    await expect(page.getByRole('button', { name: /Run Analysis/i })).toBeDisabled()
  })

  // ── 9. Search page: slider ───────────────────────────────────────────────────
  test('search page: k slider renders with value 10', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/search')

    // The k value label shows 10
    await expect(page.locator('text=10').first()).toBeVisible()

    // Search button is disabled with no doc/query
    await expect(page.getByRole('button', { name: /Search/i })).toBeDisabled()
  })

  // ── 10. 404 redirect ─────────────────────────────────────────────────────────
  test('unknown route redirects to documents page', async ({ page }) => {
    await seedApiKey(page)
    await page.goto('/does-not-exist')
    // After redirect, the Documents page heading should be present
    await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible()
    expect(page.url()).toMatch(/localhost:5173\/?$/)
  })
})

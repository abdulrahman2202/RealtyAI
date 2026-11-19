/* Exercise the existing Next.js UI against its real /api/chat endpoint. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('C:/Python312/Lib/site-packages/playwright/driver/package');

const questions = [
  'What services does Wasalt provide?',
  'What information is available about THE ALBERT HALL MANSION?',
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const results = [];
  const errors = [];
  const output = path.resolve(process.env.REALTYAI_VERIFY_OUTPUT || 'data/import_review/phase6112_frontend_verification.json');
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.REALTYAI_VERIFY_URL || 'http://localhost:3000');
    for (let index = 0; index < questions.length; index++) {
      const question = questions[index];
      await page.getByRole('button', { name: 'New conversation', exact: true }).first().click();
      const request = page.waitForResponse(response => response.url().endsWith('/api/chat')
        && response.request().method() === 'POST'
        && response.request().postDataJSON().question === question, { timeout: 240000 });
      await page.getByRole('textbox', { name: 'Ask a property question' }).fill(question);
      await page.getByRole('button', { name: 'Send message', exact: true }).click();
      const response = await request;
      const body = await response.json();
      if (response.status() !== 200 || !body.answer || !body.sources?.length) {
        throw new Error('Chat failed for ' + question + ' with HTTP ' + response.status());
      }
      await page.locator('.chat-markdown').last().waitFor();
      const message = page.locator('.chat-markdown').last();
      const displayed = await message.innerText();
      const sourceLinks = await message.locator('..').locator('..').locator('.mt-2 a')
        .evaluateAll(links => links.map(link => ({ title: link.textContent, url: link.getAttribute('href') })));
      const correctCitations = body.sources.every(source => sourceLinks.some(link =>
        link.url === source.url && link.title === source.title));
      const useful = displayed.length > 80 && !displayed.includes('No relevant records are available');
      const expectedFacts = index === 0 ? /search/i.test(displayed) && /auction/i.test(displayed)
        : displayed.includes('London') && displayed.includes('Royal Albert Hall');
      const prepared = JSON.parse(fs.readFileSync('data/import_review/chunk_review.json', 'utf8'));
      const newDataCitations = body.sources.every(source => prepared.documents.some(document => document.url === source.url));
      if (!correctCitations || !useful || !expectedFacts || !newDataCitations || await page.locator('main div[role="alert"]').count()) {
        console.error(JSON.stringify({ correctCitations, useful, expectedFacts, newDataCitations, sourceLinks }));
        throw new Error('Frontend answer/citation validation failed for ' + question);
      }
      results.push({ question, http_status: response.status(), answer: body.answer, displayed_text: displayed,
        source_links: sourceLinks, correct_citations: correctCitations, useful_answer: useful,
        expected_facts_present: expectedFacts, new_data_citations: newDataCitations });
      fs.writeFileSync(output, JSON.stringify({ questions: results, browser_errors: errors }, null, 2));
      console.log(JSON.stringify({ question, correctCitations, useful, displayedCharacters: displayed.length }));
      if (index === 0 || index === 1) {
        const screenshotDirectory = process.env.REALTYAI_VERIFY_SCREENSHOTS || '.tmp/phase6112';
        await page.screenshot({ path: path.resolve(screenshotDirectory, 'frontend-' + index + '.png'), fullPage: true });
      }
    }
    if (errors.length) throw new Error('Browser errors: ' + errors.join('; '));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });

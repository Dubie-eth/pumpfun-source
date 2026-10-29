import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import ts from 'typescript';
const requireFrontend = createRequire(new URL('../packages/frontend/package.json', import.meta.url));
const { chromium } = requireFrontend('@playwright/test');

test('real HTTP browser module performs Wallet Standard handshake/approval/change/cleanup without network auth', async () => {
  const source = await readFile(new URL('../packages/frontend/src/app/auth/public-wallet/controller.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
  const requests = [];
  const server = createServer((request, response) => {
    requests.push(`${request.method} ${request.url}`);
    response.setHeader('Cache-Control', 'no-store');
    if (request.url === '/controller.js') { response.setHeader('Content-Type', 'text/javascript'); response.end(code); }
    else if (request.url === '/') response.end('<!doctype html><title>Public wallet protocol integration</title><script type="module">import {PublicWalletController} from "/controller.js";window.controller=new PublicWalletController(window);window.ready=true;</script>');
    else { response.statusCode = 404; response.end(); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => window.ready);
    const result = await page.evaluate(async () => {
      let reads = 0, calls = [], change, unregister;
      const accounts = [{ address: '11111111111111111111111111111111', chains: ['solana:mainnet'] }];
      window.addEventListener('wallet-standard:app-ready', event => {
        unregister = event.detail.register({ version: '1.0.0', name: 'Protocol fixture', chains: ['solana:mainnet'],
          get accounts() { reads++; return accounts; },
          features: {
            'standard:connect': { version: '1.0.0', async connect(...args) { calls.push(`connect:${args.length}`); return { accounts }; } },
            'standard:events': { version: '1.0.0', on(event, callback) { change = callback; calls.push(event); return () => calls.push('off'); } },
            get 'solana:signIn'() { throw Error('forbidden'); },
          } });
      });
      const controller = window.controller;
      controller.discover(); const discoveredReads = reads;
      await controller.connect(0); const connected = controller.getSnapshot().address;
      accounts[0].address = 'So11111111111111111111111111111111111111112'; change({ accounts });
      const changed = controller.getSnapshot().address;
      unregister(); const revoked = controller.getSnapshot().address;
      controller.dispose();
      return { discoveredReads, connected, changed, revoked, calls, cookies: document.cookie, local: localStorage.length, session: sessionStorage.length };
    });
    assert.deepEqual(result, { discoveredReads: 0, connected: '11111111111111111111111111111111', changed: 'So11111111111111111111111111111111111111112', revoked: null, calls: ['connect:0', 'change', 'off'], cookies: '', local: 0, session: 0 });
    assert.deepEqual(errors, []);
    assert.ok(requests.every(value => ['GET /', 'GET /controller.js', 'GET /favicon.ico'].includes(value)));
  } finally { await browser?.close(); await new Promise(resolve => server.close(resolve)); }
});

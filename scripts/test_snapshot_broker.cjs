/* Verify the actual TypeScript broker without cloud credentials or provisioning. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const test = require('node:test');
const root = path.resolve(__dirname, '..');
const frontendRequire = createRequire(path.join(root, 'frontend/package.json'));
const ts = frontendRequire('typescript');
const source = fs.readFileSync(path.join(root, 'frontend/src/lib/snapshot-broker.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const exportsObject = {};
const diagnosticLogs = [];
vm.runInNewContext(compiled.outputText, { exports: exportsObject, require, Buffer, Response, URL, Date, process, Error,
  console: { warn: (...values) => diagnosticLogs.push(values) } });
const create = exportsObject.createSnapshotHandler;
const token = 'fixture_only_credential_12345678901234567890';
const pathname = 'realtyai_multisource_v1-' + 'a'.repeat(64) + '.tar.gz';
const env = { REALTYAI_SNAPSHOT_CLIENT_TOKEN: token, REALTYAI_SNAPSHOT_BLOB_PATH: pathname,
  REALTYAI_SNAPSHOT_SHA256: 'a'.repeat(64), BLOB_STORE_ID: 'store_fixture' };
const request = (headers = {}, query = '') => new Request('https://fixture.vercel.app/api/internal/chroma-snapshot' + query, { headers });

test('unauthorized and browser requests never invoke Blob signing or expose URLs', async () => {
  let calls = 0;
  const handler = create(async () => { calls++; throw Error('secret'); }, async () => { throw Error('secret'); }, () => env);
  for (const headers of [{}, { Authorization: 'Bearer wrong' }, { Authorization: 'Bearer ' + token, Origin: 'https://fixture.vercel.app' }]) {
    const response = await handler(request(headers));
    assert.equal(response.status, 401);
    assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
    assert.ok(!(await response.text()).includes('url'));
  }
  assert.equal(calls, 0);
});

test('authenticated exact archive requests use private GET-only signing and reuse delegation', async () => {
  const issued = [];
  const handler = create(async options => { issued.push(options); return { delegationToken: 'fixture', clientSigningToken: 'private-fixture', validUntil: options.validUntil }; },
    async (_token, options) => {
      assert.equal(options.operation, 'get'); assert.equal(options.access, 'private'); assert.equal(options.pathname, pathname);
      return { presignedUrl: 'https://fixture.private.blob.vercel-storage.com/' + pathname + '?signature=fixture' };
    }, () => env);
  for (let count = 0; count < 2; count++) {
    const response = await handler(request({ Authorization: 'Bearer ' + token }));
    assert.equal(response.status, 200);
    const body = await response.json(); assert.equal(body.sha256, env.REALTYAI_SNAPSHOT_SHA256);
    assert.ok(Date.parse(body.expires_at) <= Date.now() + 300_000);
    assert.equal(body.collection_id, '51cdb05c-3ee9-4b04-b85c-71cbf168ff0d');
  }
  assert.equal(issued.length, 1);
  assert.equal(issued[0].operations.length, 1); assert.equal(issued[0].operations[0], 'get');
  assert.equal(issued[0].pathname, pathname);
  assert.equal((await handler(request({ Authorization: 'Bearer ' + token }, '?pathname=other'))).status, 400);
});

test('missing configuration and provider failures return sanitized 503', async () => {
  const issue = async () => { throw Error('private-token'); };
  const sign = async () => { throw Error('private-signed-url'); };
  assert.equal((await create(issue, sign, () => ({}))(request())).status, 503);
  const response = await create(issue, sign, () => env)(request({ Authorization: 'Bearer ' + token }));
  assert.equal(response.status, 503); assert.ok(!(await response.text()).includes('private-token'));
});

test('broker logs configuration and SDK failure stages without private values', async () => {
  diagnosticLogs.length = 0;
  const issue = async () => { throw Error('Authorization: Bearer do-not-log-token https://private.invalid/?signature=do-not-log-query'); };
  const sign = async () => { throw Error('do-not-log-signing-value'); };
  await create(issue, sign, () => ({}))(request());
  await create(issue, sign, () => env)(request({ Authorization: 'Bearer ' + token }));
  const stages = diagnosticLogs.map(row => row[1].stage);
  assert.ok(stages.includes('broker_configuration')); assert.ok(stages.includes('delegation_issue'));
  const output = JSON.stringify(diagnosticLogs);
  for (const privateValue of [token, env.REALTYAI_SNAPSHOT_SHA256, pathname, 'do-not-log', 'https://', 'Authorization']) {
    assert.ok(!output.includes(privateValue));
  }
  assert.equal(diagnosticLogs[1][1].exception_class, 'Error');
});

test('broker identifies URL signing failure without logging the SDK exception', async () => {
  diagnosticLogs.length = 0;
  const issue = async options => ({ delegationToken: 'fixture', clientSigningToken: 'private-fixture', validUntil: options.validUntil });
  const sign = async () => { throw Error('do-not-log-signed-url'); };
  const response = await create(issue, sign, () => env)(request({ Authorization: 'Bearer ' + token }));
  assert.equal(response.status, 503);
  assert.equal(diagnosticLogs[0][1].stage, 'url_signing');
  assert.ok(!JSON.stringify(diagnosticLogs).includes('do-not-log'));
});

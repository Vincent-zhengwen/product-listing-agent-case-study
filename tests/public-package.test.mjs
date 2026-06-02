import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');

function read(relativePath) {
  return fs.readFileSync(path.join(projectRoot, relativePath), 'utf8');
}

test('public package promotes the four-stage evolution page as the main demo', () => {
  const readme = read('README.md');
  const index = read('index.html');

  assert.match(index, /url=evolution\//);
  assert.match(readme, /主展示页/);
  assert.match(readme, /evolution\/index\.html/);
  assert.doesNotMatch(readme, /最终上架资产 Demo/);
  assert.doesNotMatch(readme, /demo\/index\.html/);
});

test('old standalone demo page is no longer referenced by public files', () => {
  const files = [
    'README.md',
    'index.html',
    'examples/tablecloth/README.md',
    'examples/tablecloth/output.json',
    'evolution/index.html',
  ];

  for (const file of files) {
    assert.doesNotMatch(read(file), /demo\//, `${file} should not reference the old demo path`);
  }
});

test('tablecloth artifact manifest points to existing evolution assets', () => {
  const manifestPath = path.join(projectRoot, 'examples/tablecloth/artifact-manifest.json');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const manifestDir = path.dirname(manifestPath);

  const paths = [
    ...manifest.assets.main_images.map((item) => item.path),
    ...manifest.assets.detail_images,
    manifest.assets.detail_full,
  ];

  assert.equal(manifest.assets.main_images.length, 5);
  assert.equal(manifest.assets.detail_images.length, 8);
  assert.equal(manifest.checks.detail_full_required, true);

  for (const relativePath of paths) {
    assert.ok(fs.existsSync(path.resolve(manifestDir, relativePath)), `Missing asset ${relativePath}`);
  }
});

test('public engineering slice and playbook are present', () => {
  const required = [
    'src/contracts.py',
    'src/runner_example.py',
    'src/tools/source_fetcher_contract.py',
    'src/tools/fact_verifier_example.py',
    'src/tools/artifact_checker.py',
    'playbooks/listing_agent_playbook.md',
    'docs/agent-sdk-design.md',
  ];

  for (const file of required) {
    assert.ok(fs.existsSync(path.join(projectRoot, file)), `Missing ${file}`);
  }
});

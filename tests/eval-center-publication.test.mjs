import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');

const requiredPaths = [
  'eval-center/index.html',
  'eval-platform-lite/README.md',
  'eval-platform-lite/frontend/app/page.tsx',
  'eval-platform-lite/frontend/components/TraceViewer.tsx',
  'eval-platform-lite/frontend/components/GraderResults.tsx',
  'eval-platform-lite/frontend/lib/api.ts',
  'eval-platform-lite/backend/main.py',
  'eval-platform-lite/backend/database.py',
  'eval-platform-lite/backend/routers/task_runs.py',
  'eval-platform-lite/backend/graders_v2/registry_v2.py',
  'eval-platform-lite/fixtures/README.md',
  'docs/evaluation-center.md',
];

const forbiddenPathPatterns = [
  /(^|\/)\.env(\.|$)/,
  /(^|\/)eval_platform\.db($|-)/,
  /(^|\/)eval\.db$/,
  /(^|\/)venv\//,
  /(^|\/)node_modules\//,
  /(^|\/)\.next\//,
  /(^|\/)logs\//,
  /(^|\/)browser_profile\//,
  /(^|\/)debug_.*\.html$/,
  /(^|\/).*\.unreadable-\d+$/,
];

const textExtensions = new Set([
  '.css',
  '.html',
  '.js',
  '.json',
  '.md',
  '.mjs',
  '.py',
  '.sh',
  '.ts',
  '.tsx',
  '.txt',
  '.yml',
  '.yaml',
]);

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    if (entry.name === '.git') continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(fullPath));
    } else {
      files.push(fullPath);
    }
  }

  return files;
}

function rel(filePath) {
  return path.relative(projectRoot, filePath).split(path.sep).join('/');
}

test('portfolio exposes eval center demo and lite code package', () => {
  for (const requiredPath of requiredPaths) {
    assert.ok(fs.existsSync(path.join(projectRoot, requiredPath)), `Missing public artifact: ${requiredPath}`);
  }

  const homeHtml = fs.readFileSync(path.join(projectRoot, 'index.html'), 'utf8');
  assert.match(homeHtml, /eval-center\//);
  assert.match(homeHtml, /评测中心/);

  const readme = fs.readFileSync(path.join(projectRoot, 'README.md'), 'utf8');
  assert.match(readme, /eval-center\//);
  assert.match(readme, /eval-platform-lite/);
});

test('public eval package excludes private runtime artifacts', () => {
  const publicFiles = walk(path.join(projectRoot, 'eval-platform-lite')).map(rel);

  for (const file of publicFiles) {
    for (const pattern of forbiddenPathPatterns) {
      assert.doesNotMatch(file, pattern, `Forbidden private/runtime artifact included: ${file}`);
    }
  }
});

test('public eval package does not contain local paths or secret-looking values', () => {
  const scopedRoots = [
    'README.md',
    'index.html',
    'docs',
    'eval-center',
    'eval-platform-lite',
  ];

  const files = scopedRoots.flatMap((root) => {
    const fullPath = path.join(projectRoot, root);
    const stat = fs.statSync(fullPath);
    return stat.isDirectory() ? walk(fullPath) : [fullPath];
  });

  const textFiles = files.filter((file) => textExtensions.has(path.extname(file)));

  for (const file of textFiles) {
    const content = fs.readFileSync(file, 'utf8');
    assert.doesNotMatch(content, /\/Users\/vincent/, `Local absolute path leaked in ${rel(file)}`);
    assert.doesNotMatch(content, /sk-[A-Za-z0-9]{8,}/, `Secret-looking key leaked in ${rel(file)}`);
    assert.doesNotMatch(content, /browser_profile|eval_platform\.db|eval\.db/, `Private runtime reference leaked in ${rel(file)}`);
  }
});

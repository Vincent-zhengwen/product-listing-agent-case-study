import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const evolutionDir = path.join(projectRoot, 'evolution');
const htmlPath = path.join(evolutionDir, 'index.html');
const html = fs.readFileSync(htmlPath, 'utf8');

const stages = [
  {
    id: 'workflow',
    label: 'Workflow',
    caseText: 'listing #18',
    mainCount: 5,
    detailCount: 11,
  },
  {
    id: 'single-agent',
    label: '单 Agent + 多工具',
    caseText: 'listing #55',
    mainCount: 5,
    detailCount: 8,
  },
  {
    id: 'multi-agent',
    label: '多专职 Agent',
    caseText: 'listing #94',
    mainCount: 5,
    detailCount: 8,
  },
  {
    id: 'sdk',
    label: 'Claude Agent SDK',
    caseText: '桌布 HTML demo',
    mainCount: 5,
    detailCount: 8,
  },
];

function getStagePanel(id) {
  const startMarker = `<!-- stage-panel:${id}:start -->`;
  const endMarker = `<!-- stage-panel:${id}:end -->`;
  const start = html.indexOf(startMarker);
  const end = html.indexOf(endMarker);

  assert.notEqual(start, -1, `Missing start marker for ${id}`);
  assert.notEqual(end, -1, `Missing end marker for ${id}`);
  assert.ok(end > start, `End marker must follow start marker for ${id}`);

  return html.slice(start, end);
}

test('evolution page exposes four stage tabs mapped to four panels', () => {
  assert.match(html, /class="[^"]*\bcase-browser\b[^"]*"/);
  assert.match(html, /role="tablist"/);
  assert.equal([...html.matchAll(/role="tab"/g)].length, 4);
  assert.equal([...html.matchAll(/role="tabpanel"/g)].length, 4);

  for (const stage of stages) {
    assert.match(html, new RegExp(`id="stage-tab-${stage.id}"[\\s\\S]*?aria-controls="stage-panel-${stage.id}"`));
    assert.match(html, new RegExp(`id="stage-panel-${stage.id}"[\\s\\S]*?aria-labelledby="stage-tab-${stage.id}"`));
    assert.match(html, new RegExp(`data-stage-target="${stage.id}"`));
  }
});

test('each tab panel shows the full case media set instead of one summary image', () => {
  for (const stage of stages) {
    const panel = getStagePanel(stage.id);
    const mainImages = [...panel.matchAll(/data-gallery-image="main"/g)];
    const detailImages = [...panel.matchAll(/data-gallery-image="detail"/g)];

    assert.ok(panel.includes(stage.label), `${stage.id} should include its stage label`);
    assert.ok(panel.includes(stage.caseText), `${stage.id} should include its case label`);
    assert.ok(mainImages.length >= stage.mainCount, `${stage.id} should show at least ${stage.mainCount} main images`);
    assert.ok(detailImages.length >= stage.detailCount, `${stage.id} should show at least ${stage.detailCount} detail images`);
  }
});

test('each stage explains architecture before showing media', () => {
  for (const stage of stages) {
    const panel = getStagePanel(stage.id);

    assert.match(panel, /class="[^"]*\barchitecture-map\b[^"]*"/, `${stage.id} should include an architecture map`);
    assert.ok(panel.includes('data-arch-step='), `${stage.id} should break architecture into steps`);
    assert.match(panel, /class="[^"]*\bevidence-board\b[^"]*"/, `${stage.id} should include concrete evidence`);
    assert.match(panel, /class="[^"]*\bproblem-callout\b[^"]*"/, `${stage.id} should call out the real problem`);
  }
});

test('media tiles expose large image links and problem annotations', () => {
  for (const stage of stages) {
    const panel = getStagePanel(stage.id);
    const zoomLinks = [...panel.matchAll(/data-zoom-link/g)];

    assert.ok(zoomLinks.length >= stage.mainCount + stage.detailCount, `${stage.id} should make images openable`);
  }

  assert.ok(html.includes('data-problem-image'), 'Expected at least one historical broken/weak artifact to be marked');
  assert.ok(html.includes('问题样张'), 'Problem images need visible labels, not silent bad thumbnails');
});

test('mobile tabs use a wrapped two-column layout instead of horizontal scrolling', () => {
  assert.match(html, /@media \(max-width: 620px\)[\s\S]*\.stage-tabs\s*{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/);
  assert.doesNotMatch(html, /@media \(max-width: 620px\)[\s\S]*\.stage-tabs[\s\S]*overflow-x:\s*auto/);
});

test('all local images referenced by the evolution page exist', () => {
  const imageSources = [...html.matchAll(/<img[^>]+src="([^"]+)"/g)].map((match) => match[1]);

  assert.ok(imageSources.length > 0, 'Expected the page to reference visual assets');

  for (const src of imageSources) {
    if (/^(https?:|data:)/.test(src)) continue;

    const resolvedPath = path.resolve(evolutionDir, src);
    assert.ok(fs.existsSync(resolvedPath), `Missing image asset: ${src}`);
  }
});

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
    caseText: '花瓶案例',
    tabCase: '花瓶案例',
    mainCount: 5,
    detailCount: 11,
  },
  {
    id: 'single-agent',
    label: '单 Agent + 多工具',
    caseText: '桌布案例',
    tabCase: '桌布案例',
    mainCount: 5,
    detailCount: 8,
  },
  {
    id: 'multi-agent',
    label: '多专职 Agent 工作流',
    caseText: '小夜灯案例',
    tabCase: '小夜灯案例',
    mainCount: 5,
    detailCount: 8,
  },
  {
    id: 'sdk',
    label: 'Claude Agent SDK',
    caseText: '桌布交付案例',
    tabCase: '桌布交付案例',
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
  assert.equal([...html.matchAll(/role="tablist"/g)].length, 1);
  assert.equal([...html.matchAll(/role="tab"/g)].length, 4);
  assert.equal([...html.matchAll(/role="tabpanel"/g)].length, 4);
  assert.ok(html.includes('<title>商品上架 Agent 架构演进</title>'));
  assert.ok(html.includes('<h1>商品上架 Agent 架构演进</h1>'));
  assert.ok(html.includes('商品上架 Agent 架构演进案例'));
  assert.ok(html.includes('<h2>四轮架构，解决不同阶段的上架生成问题</h2>'));
  assert.ok(html.includes('从 Workflow 到单 Agent + 多工具，再到多专职 Agent 工作流和 Claude Agent SDK，展示一个上架 Agent 如何把货源理解、工具调用、职责拆分和产物验证逐步纳入架构。'));
  assert.ok(!html.includes('每个阶段按同一套结构展开'));
  assert.ok(!html.includes('<p class="lead">'));
  assert.ok(html.includes('<h2>四阶段架构对照</h2>'));
  assert.ok(!html.includes('每一轮升级都把原本依赖人工判断的环节放进 Agent 执行链路'));

  for (const stage of stages) {
    assert.match(html, new RegExp(`id="stage-tab-${stage.id}"[\\s\\S]*?aria-controls="stage-panel-${stage.id}"`));
    assert.match(html, new RegExp(`id="stage-panel-${stage.id}"[\\s\\S]*?aria-labelledby="stage-tab-${stage.id}"`));
    assert.match(html, new RegExp(`data-stage-target="${stage.id}"`));
    assert.match(html, new RegExp(`id="stage-tab-${stage.id}"[\\s\\S]*?<span class="tab-case">${stage.tabCase}</span>`));
  }
});

test('hero path uses the same stage names as the tabs', () => {
  assert.ok(!html.includes('class="hero-stage-line"'));
  assert.ok(!html.includes('演进路径'));
  assert.doesNotMatch(html, /Specialized|Pipeline|Knight|Loop/i);
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

test('each stage explains positioning, architecture, case evidence and the next boundary', () => {
  for (const stage of stages) {
    const panel = getStagePanel(stage.id);

    assert.ok(panel.includes('阶段定位'), `${stage.id} should state the stage positioning`);
    assert.match(panel, /class="[^"]*\barchitecture-map\b[^"]*"/, `${stage.id} should include an architecture map`);
    assert.ok(panel.includes('data-arch-step='), `${stage.id} should break architecture into steps`);
    assert.match(panel, /class="[^"]*\bevidence-board\b[^"]*"/, `${stage.id} should include the evidence board`);
    assert.match(panel, /class="[^"]*\bproblem-callout\b[^"]*"/, `${stage.id} should call out the architecture boundary`);
  }

  for (const stage of stages.slice(0, 3)) {
    const panel = getStagePanel(stage.id);
    assert.ok(panel.includes('运行瓶颈'), `${stage.id} should explain the runtime bottleneck`);
    assert.ok(panel.includes('下一阶段架构升级'), `${stage.id} should explain the next architecture upgrade`);
  }

  const sdkPanel = getStagePanel('sdk');
  assert.ok(sdkPanel.includes('运行结果'), 'sdk should frame the final stage as a delivery result');
  assert.ok(sdkPanel.includes('最终架构形态'), 'sdk should explain the final architecture shape');
  assert.ok(!sdkPanel.includes('下一阶段架构升级'), 'sdk should not imply another stage after the final architecture');
});

test('stage copy avoids the removed duplicate framing', () => {
  const removedPhrases = ['交付能力', '交付瓶颈', '能力升级'];

  for (const phrase of removedPhrases) {
    assert.ok(!html.includes(phrase), `Public page should not use removed duplicate phrase: ${phrase}`);
  }

  assert.doesNotMatch(html, /class="[^"]*\bpanel-facts\b[^"]*"/);
  assert.doesNotMatch(html, /class="[^"]*\bcase-story\b[^"]*"/);
});

test('media tiles expose large image links without case-by-case problem labels', () => {
  for (const stage of stages) {
    const panel = getStagePanel(stage.id);
    const zoomLinks = [...panel.matchAll(/data-zoom-link/g)];

    assert.ok(zoomLinks.length >= stage.mainCount + stage.detailCount, `${stage.id} should make images openable`);
  }

  const assetDescriptions = [
    '固定流程产出的 5 张主图，能看到基础成组生成能力。',
    '固定流程产出的 11 张详情图，主要依赖模板化展开。',
    '单 Agent 调用工具后产出的 5 张主图。',
    '单 Agent 工具链产出的 8 张详情图。',
    '多专职 Agent 规划后产出的 5 张主图。',
    '多专职 Agent 规划后产出的 8 张详情图。',
    'SDK 执行闭环产出的 5 张主图。',
    'SDK 执行闭环产出的详情图，默认查看 8 张分图。',
    'SDK 阶段形成的最终交付长图。',
  ];

  for (const description of assetDescriptions) {
    assert.ok(html.includes(description), `Expected direct asset description: ${description}`);
  }

  assert.doesNotMatch(html, /data-problem-image/);
  assert.doesNotMatch(html, /问题样张/);
});

test('only the final stage keeps a switchable long detail image', () => {
  const singleAgentPanel = getStagePanel('single-agent');
  const sdkPanel = getStagePanel('sdk');

  assert.doesNotMatch(singleAgentPanel, /详情长图|detail_full/);
  assert.match(sdkPanel, /data-asset-view="sdk-detail"/);
  assert.match(sdkPanel, /data-asset-mode-target="split"[\s\S]*分图模式/);
  assert.match(sdkPanel, /data-asset-mode-target="long"[\s\S]*长图模式/);
  assert.match(sdkPanel, /data-asset-mode-panel="split"/);
  assert.match(sdkPanel, /data-asset-mode-panel="long" hidden/);
  assert.match(sdkPanel, /最终交付长图/);
});

test('public copy avoids internal planning language and broken navigation CTAs', () => {
  const forbidden = [
    '为什么是这个 case',
    '每个阶段先讲',
    '内部',
    'HTML demo',
    '桌布 demo',
    '查看最终',
    '返回项目首页',
    '核心不是',
    '架构名词',
    'harness',
    '按四阶段架构演进查看真实 case',
    '架构边界逐步前移',
    '四个阶段对应四种系统边界',
    'listing #18 花瓶',
    'listing #55 桌布',
    'listing #94 小夜灯',
    '商品图 / 素材包',
    '商品上架 Agent · 架构演进 Demo',
    '四种架构，四个上架案例',
    '展示固定流程阶段',
    '展示单 Agent 调用工具',
    '展示专职阶段拆分',
    '代表当前阶段',
  ];

  for (const phrase of forbidden) {
    assert.ok(!html.includes(phrase), `Public page should not include internal phrase: ${phrase}`);
  }

  assert.doesNotMatch(html, /href="\.\.\/demo\/"/);
  assert.doesNotMatch(html, /href="\.\.\/"/);
  assert.doesNotMatch(html, /class="[^"]*\bflow-step\b[^"]*"/);
});

test('mobile tabs use a wrapped two-column layout instead of horizontal scrolling', () => {
  assert.match(html, /@media \(max-width: 620px\)[\s\S]*\.stage-tabs\s*{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\);/);
  assert.doesNotMatch(html, /@media \(max-width: 620px\)[\s\S]*\.stage-tabs[\s\S]*overflow-x:\s*auto/);
});

test('visual layout uses a case-study flow instead of a sidebar card wall', () => {
  assert.match(html, /\.case-browser\s*{[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\);/);
  assert.match(html, /\.stage-tabs\s*{[\s\S]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\);/);
  assert.match(html, /\.stage-tabs\s*{[\s\S]*position:\s*static;/);
  assert.match(html, /\.stage-panel\s*{[\s\S]*box-shadow:\s*none;/);
  assert.doesNotMatch(html, /\.case-story\b/);
  assert.doesNotMatch(html, /\.story-item\b/);
  assert.doesNotMatch(html, /\.panel-facts\b/);
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

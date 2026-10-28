import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const root = new URL('../', import.meta.url);
const page = readFileSync(new URL('dist/live-demo.html', root), 'utf8');
const app = readFileSync(new URL('dist/app.js', root), 'utf8');

test('Pages root opens the interactive dashboard instead of the video walkthrough', () => {
  const index = readFileSync(new URL('index.html', root), 'utf8');
  assert.match(index, /dist\/live-demo\.html/);
  assert.doesNotMatch(index, /docs\/watch\.html/);
});

test('interactive demo is self-contained and honest about its static data boundary', () => {
  for (const path of ['./styles.css', './data/scenarios.js', './app.js']) {
    assert.equal(existsSync(fileURLToPath(new URL(`dist/${path.slice(2)}`, root))), true, path);
    assert.match(page, new RegExp(path.replaceAll('.', '\\.')));
  }
  assert.match(page, /STATIC BROWSER DEMO • SYNTHETIC DATA • NO API CALLS/);
  assert.doesNotMatch(app, /fetch\(|EventSource|WebSocket/);
});

test('interactive controls and evidence pipeline are exposed to visitors', () => {
  for (const id of ['scenario-tabs', 'play-button', 'speed-control', 'audience-control',
    'focus-select', 'language-select', 'event-feed']) {
    assert.match(page, new RegExp(`id=["']${id}["']`), id);
  }
  assert.match(page, /Evidence trace/);
  assert.doesNotMatch(page, /Agent trace/);
});

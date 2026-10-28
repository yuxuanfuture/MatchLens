import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {existsSync, readFileSync} from 'node:fs';
import {playerFocus, staticDemoEnabled} from '../dist/static-demo-client.js';

const root = new URL('../', import.meta.url);
const read = path => readFileSync(new URL(path, root), 'utf8');

test('Pages root opens the actual Pocket Stadium in static demo mode', () => {
  const index=read('index.html'),product=read('dist/index.html');
  assert.match(index, /dist\/?\?demo=1/);
  assert.match(product, /id="arrange-button"/);
  assert.match(product, /id="fan-mode"/);
  assert.match(product, /id="analyst-mode"/);
  assert.match(product, /static-browser-demo/);
  assert.equal(existsSync(new URL('dist/live-demo.html',root)),false);
});

test('static demo detection is explicit locally and automatic on GitHub Pages', () => {
  assert.equal(staticDemoEnabled({search:'?demo=1',hostname:'127.0.0.1'}),true);
  assert.equal(staticDemoEnabled({search:'',hostname:'yuxuanfuture.github.io'}),true);
  assert.equal(staticDemoEnabled({search:'',hostname:'127.0.0.1'}),false);
});

test('generated snapshots cover the complete replay in all supported languages', () => {
  const manifest=JSON.parse(read('dist/demo-data/manifest.json'));
  assert.deepEqual(manifest.languages,['en','zh','fr','es','ar']);
  assert.equal(manifest.interval_ms,500);assert.equal(manifest.duration_ms,120000);assert.equal(manifest.snapshots,241);
  const digest=createHash('sha256').update(readFileSync(new URL('data/streams/stream-04.jsonl',root))).digest('hex');
  assert.equal(manifest.source_sha256,digest);
  for(const language of manifest.languages){
    const dataset=JSON.parse(read(`dist/demo-data/${language}.json`));
    assert.equal(dataset.snapshots.length,manifest.snapshots,language);
    assert.equal(dataset.recaps.A.length,manifest.snapshots,language);
    assert.equal(dataset.recaps.U.length,manifest.snapshots,language);
    assert.equal(dataset.snapshots[0].preferences.language,language);
    assert.equal(dataset.snapshots.at(-1).playback.position_ms,manifest.duration_ms);
  }
});

test('browser-side player focus is computed only from observations received so far', () => {
  const player={id:'A9',name:'Atlas 9'};
  const records=[
    {id:'t0',record_type:'tracking',event_time_ms:0,observed_at_ms:80,players:[{player_id:'A9',x:0,y:0}]},
    {id:'t1',record_type:'tracking',event_time_ms:1000,observed_at_ms:1080,players:[{player_id:'A9',x:3,y:4}]},
    {id:'p1',record_type:'event',type:'pass',player_id:'A9',outcome:'complete',event_time_ms:1000,observed_at_ms:1080},
    {id:'s1',record_type:'event',type:'shot',player_id:'A9',event_time_ms:2000,observed_at_ms:2080},
  ];
  const before=playerFocus(records,player,1500),after=playerFocus(records,player,2500);
  assert.equal(before.observed_distance_m,5);assert.equal(before.completed_passes,1);assert.equal(before.shots,0);
  assert.equal(after.shots,1);assert.deepEqual(after.evidence_ids,['p1','s1']);
});

"""Prepare or run the final real-model checks. Never grants its own approval."""
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.api_policy import policy_status
from backend.fixture_tools import FixtureStream
from backend.harness import Harness,Budget,OllamaModel
from backend.model_providers import DeepSeekModel,load_local_env
cases=[{'id':f'{stream}-{lang}','stream':stream,'at_ms':58000 if stream=='stream-03' else 68000,'language':lang,'kind':'story'} for stream in ['stream-01','stream-02','stream-03'] for lang in ['zh','en']]
cases += [{'id':'player-focus','stream':'match-day','at_ms':4500000,'language':'zh','focus_player':'A17','kind':'story'},{'id':'recap-so-far','stream':'stream-01','at_ms':68000,'language':'en','kind':'recap'},{'id':'full-time-recap','stream':'match-day','at_ms':5406580,'language':'zh','kind':'recap'}]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--case',choices=[c['id'] for c in cases]);args=p.parse_args();cases=[c for c in cases if not args.case or c['id']==args.case]
if not args.execute:
 print(json.dumps({'status':'plan_only_no_model_calls','cases':cases,'maximum_requests':sum(14 if c['kind']=='story' else 24 for c in cases),'approval_required':True},ensure_ascii=False,indent=2));raise SystemExit()
policy=policy_status()
if not policy['enabled']:raise SystemExit('BLOCKED: fresh explicit user approval and a new credential are required. No model call made.')
load_local_env(ROOT/'.env.local')
if policy['approved_provider']=='deepseek':model=DeepSeekModel(os.environ.get('DEEPSEEK_API_KEY'),os.environ.get('DEEPSEEK_MODEL','deepseek-flash'))
elif policy['approved_provider']=='ollama':model=OllamaModel(os.environ.get('OLLAMA_MODEL',''))
else:raise SystemExit('No approved provider adapter')
folder=ROOT/'run-output/api-acceptance';folder.mkdir(parents=True,exist_ok=True);reports=[]
for c in cases:
 snapshot=FixtureStream(ROOT/f"data/streams/{c['stream']}.jsonl").snapshot(c['at_ms'])
 budget=Budget(model_calls=14,tool_calls=24,turns_per_role=8,wall_seconds=25,request_seconds=8) if c['kind']=='story' else Budget()
 h=Harness(model,snapshot,budget=budget);result=h.run('Explain the observed play or recap. Investigate efficiently, respect coverage and requested player, and provide distinct Fan and Analyst versions.',{'language':c['language'],'focus_team':'A','focus_player':c.get('focus_player')},kind=c['kind'])
 checks={'published_reviewed_output':result['status'] in {'publish','insufficient_evidence'} and any(r['kind']=='review' and r['verdict']['approved'] for r in h.trace),'distinct_audiences':result['fan_text']!=result['analyst_text'],'within_latency_budget':result['usage']['elapsed_ms']<=budget.wall_seconds*1000}
 if c['stream']=='stream-03':checks['missing_data_explained']=any(word in result['fan_text'].lower() for word in ['缺','无法','不足','missing','gap','unavailable','insufficient'])
 if c['stream']=='stream-01' and c['kind']=='story':checks['regain_and_shot_grounded']={'e018','e022'}<=set(i for claim in result['claims'] for i in claim['evidence_ids'])
 (folder/f"{c['id']}.json").write_text(json.dumps({'case':c,'checks':checks,'result':result,'trace':h.trace},ensure_ascii=False,indent=2))
 reports.append({'id':c['id'],'checks':checks,'usage':result['usage']});print(json.dumps(reports[-1]),flush=True)
(folder/'report.json').write_text(json.dumps({'cases':reports,'passed':all(all(c['checks'].values()) for c in reports),'human_review_required':'Read the evidence and judge football relevance, translation quality and clarity; automatic checks are not an accuracy score.'},ensure_ascii=False,indent=2))

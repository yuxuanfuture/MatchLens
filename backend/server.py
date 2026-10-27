"""Local stream service. Run: python3 -m backend.server --port 43128.

Only the loopback interface is served. Model calls are disabled by the persisted
approval policy; the browser cannot change that policy or supply a credential.
"""
import argparse
import copy
import json
import math
import os
import sqlite3
import threading
import time
import uuid
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from backend.api_policy import policy_status, APIBlocked
from backend.fixture_tools import FixtureStream, MatchTools
from backend.insights import publish, recap, preferences, clock
from backend.ingestion import validate_record, validate_stream
from backend.video_jobs import VideoJobs
from backend.i18n import text as localized_text
from backend.replay_clock import replay_clock, playback_view
from backend.review_state import review_state, presentation_evidence

ROOT = Path(__file__).resolve().parents[1]
STREAMS = {"stream-01": "Observation 01", "stream-02": "Observation 02",
           "stream-03": "Observation 03", "stream-04": "Added-time play · 120 seconds",
           "match-day": "Full match · 90 minutes"}
MODEL_STORY_TTL_MS = 30000


class EventStore:
    """Append-only received records; duplicates are idempotent, conflicts rejected.

    Event time can arrive out of order. Arrival time must already have happened.
    Both clocks gate visibility, including records with future event times.
    """
    def __init__(self):
        self.records = {}

    def ingest(self, row, received_at_ms):
        row = copy.deepcopy(row)
        required = {"id", "record_type", "event_time_ms", "observed_at_ms", "match_id"}
        if not required <= row.keys() or row["record_type"] not in {"metadata", "event", "tracking", "coverage"}:
            raise ValueError("Malformed stream record")
        if any(type(row[k]) is not int or row[k] < 0 for k in ("event_time_ms", "observed_at_ms")):
            raise ValueError("Invalid clock")
        if row["observed_at_ms"] > received_at_ms:
            raise ValueError("Record has not arrived yet")
        if self.records and row["match_id"] != next(iter(self.records.values()))["match_id"]:
            raise ValueError("Match identity changed")
        previous = self.records.get(row["id"])
        if previous:
            if previous != row:
                raise ValueError("Conflicting duplicate ID")
            return False
        self.records[row["id"]] = row
        return True

    def snapshot(self, as_of_ms, trim_tracking=True):
        rows = [r for r in self.records.values() if max(r["event_time_ms"], r["observed_at_ms"]) <= as_of_ms
                and (not trim_tracking or r["record_type"] != "tracking" or r["event_time_ms"] >= as_of_ms - 65000)]
        return MatchTools(copy.deepcopy(rows), as_of_ms)


class Journal:
    def __init__(self, path):
        self.lock = threading.Lock()
        self.closed = False
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS stories (session TEXT, epoch INTEGER, at INTEGER, body TEXT, PRIMARY KEY(session, epoch, at))")
        self.db.commit()

    def add(self, session, epoch, at, story):
        with self.lock:
            if self.closed:
                return
            self.db.execute("INSERT OR REPLACE INTO stories VALUES(?,?,?,?)", (session, epoch, at, json.dumps(story, ensure_ascii=False)))
            self.db.commit()

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.db.close()

    def recent(self, session, epoch, at):
        with self.lock:
            if self.closed: return []
            rows = self.db.execute('SELECT at,body FROM stories WHERE session=? AND epoch=? AND at<=? ORDER BY at DESC LIMIT 100', (session,epoch,at)).fetchall()
        seen, result = set(), []
        for stamp, body in rows:
            story = json.loads(body)
            text = story.get('analyst_text', '')
            if text and text not in seen:
                result.append({'at_ms':stamp, 'text':text, 'evidence_ids':story.get('evidence_ids',[]), 'source':story.get('source')})
                seen.add(text)
            if len(result) == 8: break
        return list(reversed(result))


class Session:
    def __init__(self, stream, prefs=None, journal=None, records=None, live=False):
        if records is None and stream not in STREAMS:
            raise ValueError("Unknown stream")
        self.id, self.stream = uuid.uuid4().hex, stream
        self.source = FixtureStream(ROOT / "data" / "streams" / f"{stream}.jsonl") if records is None else None
        self.rows = sorted(records if records is not None else self.source._records, key=lambda r: (r["observed_at_ms"], r["id"]))
        self.metadata=next(r for r in self.rows if r['record_type']=='metadata')
        self.source_mode='live' if live else 'replay'
        self.duration = max(max(r["event_time_ms"], r["observed_at_ms"]) for r in self.rows)
        self.playback_config = replay_clock(self.metadata, self.rows) if not live else None
        self.at = self.playback_config['receive_offset_ms'] if self.playback_config else min(1000, self.duration)
        self.playing, self.speed = False, 1
        self.updated = time.monotonic()
        self.lock = threading.RLock()
        self.epoch, self.sequence = 0, 0
        self.store, self.cursor = EventStore(), 0
        self.feed()
        self.prefs = preferences(prefs or {}, self.store.snapshot(self.at)._roster)
        self.cache, self.cache_key, self.journal = None, None, journal
        self.model_story, self.model_status, self.model_bucket = None, "locked", None
        self.model_recap = None
        self.jobs = {}

    @classmethod
    def from_records(cls, records, prefs=None, journal=None, live=False):
        validate_stream(records)
        return cls(records[0]['match_id'],prefs,journal,copy.deepcopy(records),live)

    def ingest(self, records, received_at_ms):
        if self.source_mode!='live':raise ValueError('This session is a replay')
        if type(received_at_ms) is not int or received_at_ms<0 or not isinstance(records,list) or len(records)>2000:raise ValueError('Invalid batch')
        with self.lock:
            metadata=self.metadata
            staged={r['id']:r for r in self.rows}
            added=[]
            for row in records:
                validate_record(row,metadata)
                if row['observed_at_ms']>received_at_ms:raise ValueError('Arrival is in the future')
                if row['id'] in staged:
                    if row!=staged[row['id']]:raise ValueError('Conflicting duplicate ID')
                    continue
                staged[row['id']]=row
                added.append(copy.deepcopy(row))
            if added:
                if any(r['event_time_ms']<self.at-1000 for r in added):
                    self.epoch+=1
                    self.model_story=None
                self.duration=max(self.duration,received_at_ms,max(max(r['event_time_ms'],r['observed_at_ms']) for r in added))
                self.at=max(self.at,received_at_ms)
                # Feed previously queued arrivals before merging the new batch.
                # Rebuilding/copying the entire match per batch grows too slowly
                # for a long live match, and is unnecessary for append-only IDs.
                self.feed()
                for row in added:self.store.ingest(row,self.at)
                self.rows=sorted([*self.rows,*added],key=lambda r:(r['observed_at_ms'],r['id']))
                self.cursor=bisect_right([r['observed_at_ms'] for r in self.rows],self.at)
                self.cache_key=None
            elif received_at_ms>self.at:
                self.at=received_at_ms;self.duration=max(self.duration,self.at);self.feed();self.cache_key=None
            return {'accepted':len(added),'duplicates':len(records)-len(added),'as_of_ms':self.at}

    def feed(self):
        while self.cursor < len(self.rows) and self.rows[self.cursor]["observed_at_ms"] <= self.at:
            self.store.ingest(self.rows[self.cursor], self.at)
            self.cursor += 1

    def tick(self):
        now = time.monotonic()
        if self.playing:
            self.at = min(self.duration, self.at + int((now - self.updated) * 1000 * self.speed))
            if self.at == self.duration:
                self.playing = False
        self.updated = now
        self.feed()

    def control(self, command):
        with self.lock:
            if not isinstance(command,dict):raise ValueError('Control must be an object')
            if set(command) - {"seek_ms", "media_time_ms", "playing", "speed", "preferences"}:
                raise ValueError("Unknown control")
            for name in ['seek_ms','media_time_ms']:
                if name in command and (type(command[name]) is not int or not 0<=command[name]<=self.duration):raise ValueError('Time outside stream')
            if 'seek_ms' in command and 'media_time_ms' in command:raise ValueError('Supply only one clock control')
            if 'speed' in command and command['speed'] not in [1,4,16,60]:raise ValueError('Invalid playback speed')
            if 'playing' in command and type(command['playing']) is not bool:raise ValueError('playing must be boolean')
            if 'preferences' in command:preferences({**self.prefs,**command['preferences']},{p['id']:p for p in self.metadata['roster']})
            self.tick()
            if 'media_time_ms' in command:
                t=command['media_time_ms']
                if type(t) is not int or not 0<=t<=self.duration:raise ValueError('Media time outside stream')
                if 0<=t-self.at<=2000:
                    self.at=t;self.feed()
                else:
                    command={**command,'seek_ms':t}
            if "seek_ms" in command:
                t = command["seek_ms"]
                if type(t) is not int or not 0 <= t <= self.duration:
                    raise ValueError("Seek outside stream")
                self.at = t
                self.store, self.cursor = EventStore(), 0
                self.feed()
                self.epoch += 1
                self.model_story = None
            if "playing" in command:
                if type(command["playing"]) is not bool:
                    raise ValueError("playing must be boolean")
                self.playing = command["playing"]
            if "speed" in command:
                if command["speed"] not in [1, 4, 16, 60]:
                    raise ValueError("Invalid playback speed")
                self.speed = command["speed"]
            if "preferences" in command:
                self.prefs = preferences({**self.prefs, **command["preferences"]}, self.store.snapshot(self.at)._roster)
                self.epoch += 1
                self.model_story = None
            self.cache_key = None
            return self.payload()

    def model_result(self, epoch, at, result):
        # Never let a delayed model response overwrite a seek or a new preference.
        with self.lock:
            self.tick()
            if epoch != self.epoch or not 0 <= self.at - at <= MODEL_STORY_TTL_MS:
                self.model_status = "stale_result_discarded"
                return False
            self.model_status = result["status"]
            if result["status"] not in {"degraded", "ignore"} and result.get("claims"):
                self.model_story = result
                self.cache_key = None
                return True
            return False

    def payload(self):
        with self.lock:
            self.tick()
            key = (self.epoch, self.at // 500, self.cursor, bool(self.model_story))
            if key != self.cache_key:
                playback = playback_view(self.playback_config, self.at, self.metadata['match_clock_start_ms']) if self.playback_config else None
                result = publish(self.store.snapshot(self.at), self.prefs, playback=playback)
                if self.model_story and result['review']['phase'] == 'none' and 0 <= self.at-self.model_story["as_of_ms"] <= MODEL_STORY_TTL_MS:
                    model = self.model_story
                    refs = list(dict.fromkeys(i for c in model["claims"] for i in c["evidence_ids"]))
                    start, end = max(0, model["as_of_ms"]-30000), model["as_of_ms"]
                    offset = result["state"]["match_clock_start_ms"]
                    result["story"].update(fan_text=model["fan_text"], analyst_text=model["analyst_text"],
                        title=localized_text(self.prefs["language"], "model.insight_title"),
                        window_ms=[start,end], window_label=f"{clock(offset+start)}–{clock(offset+end)}",
                        evidence_ids=refs, source="model_harness", display_at_ms=model["as_of_ms"], expires_at_ms=model["as_of_ms"]+MODEL_STORY_TTL_MS)
                    result["mode"] = "model_harness"
                    result["agent_usage"] = model["usage"]
                    result["agent_claims"] = model["claims"]
                    result["agent_facts"] = model.get("facts", {})
                    result["evidence_records"] = presentation_evidence(self.store.snapshot(self.at, False).get_evidence(refs[:40])["records"], result['review']) if refs else []
                self.sequence += 1
                self.cache, self.cache_key = result, key
                if self.journal:
                    self.journal.add(self.id, self.epoch, self.at, result["story"])
            return {**self.cache, "session_id": self.id, "stream": self.stream, "duration_ms": self.duration,
                    "source_mode":self.source_mode,
                    "playing": self.playing, "speed": self.speed, "epoch": self.epoch, "sequence": self.sequence,
                    "policy": policy_status(), "agent_status": self.model_status, "received_records": self.cursor}

    def make_recap(self):
        with self.lock:
            self.tick()
            current = self.model_recap
            if current and current['epoch'] == self.epoch and current['result']['as_of_ms'] <= self.at:
                result = current['result']
                report = recap(self.store.snapshot(result['as_of_ms'],False), self.prefs)
                return {**report, 'text':result['fan_text'] if self.prefs['mode']=='fan' else result['analyst_text'],
                        'source':'model_harness', 'claims':result['claims'], 'agent_facts':result.get('facts',{}),
                        'agent_status':self.jobs.get('recap',{}).get('status','complete')}
            return {**recap(self.store.snapshot(self.at,False), self.prefs), 'source':'offline_facts',
                    'agent_status':self.jobs.get('recap',{}).get('status','locked')}


def investigate(session, snapshot, epoch, prefs, kind='story', model=None):
    """This function is only scheduled after a valid, separately granted policy."""
    from backend.harness import Harness, OllamaModel, Budget
    from backend.model_providers import DeepSeekModel, load_local_env
    policy = policy_status()
    if model is None and not policy["enabled"]:
        return
    if model is None:
        load_local_env(ROOT / ".env.local")
        if policy["approved_provider"] == "deepseek":
            model = DeepSeekModel(os.environ.get("DEEPSEEK_API_KEY"), os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"))
        elif policy["approved_provider"] == "ollama":
            model = OllamaModel(os.environ.get("OLLAMA_MODEL", ""))
        else:
            raise APIBlocked("No approved provider")
    history = session.journal.recent(session.id,epoch,snapshot.as_of_ms) if session.journal else []
    budget=Budget(model_calls=14,tool_calls=24,turns_per_role=8,wall_seconds=25,request_seconds=8) if kind=='story' else Budget()
    harness = Harness(model, snapshot, budget=budget, history=history, cancelled=lambda:session.epoch!=epoch)
    task = ('Summarize the whole observed interval, including milestones, turning points and the requested player context. ' if kind=='recap' else 'Investigate the recent observed events. ')
    result = harness.run(task + "Delegate evidence collection and audience adaptation; explain why a moment matters or abstain. Respect units, gaps and the requested focus. Never infer a full-match result from a partial stream.", prefs, kind=kind)
    if kind == 'story': session.model_result(epoch, snapshot.as_of_ms, result)
    elif result['status'] in {'publish','insufficient_evidence'}:
        with session.lock:
            if session.epoch==epoch:session.model_recap={'epoch':epoch,'result':result}
    output = ROOT / "run-output" / "agent-traces"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{session.id}-{epoch}-{snapshot.as_of_ms}-{kind}.json").write_text(json.dumps({"result": result, "trace": harness.trace}, ensure_ascii=False))
    return result


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, journal_path=None):
        super().__init__(address, partial(Handler, directory=str(ROOT / "dist")))
        self.sessions = {}
        self.sessions_lock = threading.Lock()
        self.journal = Journal(journal_path or ":memory:")
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.slots = threading.BoundedSemaphore(8)
        self.video = VideoJobs()

    def maybe_investigate(self, session, kind='story'):
        # Event-batched cadence, never one request per frame. The gate is also
        # enforced separately immediately before EVERY provider HTTP request.
        if not policy_status()["enabled"]:
            return
        with session.lock:
            important = next((r['id'] for r in reversed(session.rows[:session.cursor]) if r.get('type') in {'goal','shot_end','substitution','full_time'} and r['event_time_ms']<=session.at),None)
            bucket = (session.epoch, session.at // (15000 if kind=='story' else 1000), important)
            old = session.jobs.get(kind,{})
            if old.get('status')=='running' or old.get('bucket')==bucket or time.monotonic()<old.get('retry_after',0):
                return
            if not self.slots.acquire(blocking=False): return
            job={'bucket':bucket, 'status':'running','as_of_ms':session.at,'failures':old.get('failures',0)}
            session.jobs[kind]=job
            if kind=='story':session.model_status='investigating'
            future = self.pool.submit(investigate, session, session.store.snapshot(session.at, False), session.epoch, dict(session.prefs),kind)
            def finished(f):
                self.slots.release()
                with session.lock:
                    failed = f.cancelled() or f.exception() or not f.result() or f.result()['status']=='degraded'
                    job['status']='unavailable' if failed else f.result()['status']
                    job['failures']=min(5,job['failures']+1) if failed else 0
                    job['retry_after']=time.monotonic()+min(120,5*2**job['failures']) if failed else 0
                    if kind=='story' and failed:session.model_status='unavailable'
            future.add_done_callback(finished)

    def server_close(self):
        self.video.close()
        self.pool.shutdown(wait=False, cancel_futures=True)
        super().server_close()
        # Request workers are daemon threads; SSE streams may still be unwinding.
        # Close their journal only after this server stops accepting connections.
        self.journal.close()


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, format, *args):
        pass

    def send_json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def local_request(self):
        host = self.headers.get("Host", "")
        return host in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"} and self.headers.get("Origin", f"http://{host}") == f"http://{host}"

    def do_GET(self):
        path = urlparse(self.path)
        if not path.path.startswith("/api/"):
            return super().do_GET()
        if not self.local_request():
            return self.send_json({"error": "Local origin required"}, 403)
        try:
            if path.path == "/api/config":
                return self.send_json({"streams": STREAMS, "policy": policy_status()})
            query = parse_qs(path.query)
            if path.path == '/api/video/status':
                return self.send_json(self.server.video.status(query.get('job',[''])[0]))
            if path.path == '/api/video/detections':
                return self.send_json(self.server.video.detections(query.get('job',[''])[0]))
            if path.path == '/api/video/records':
                return self.send_json(self.server.video.records(query.get('job',[''])[0]))
            session = self.server.sessions[query.get("session", [""])[0]]
            if path.path == '/api/overlay':
                from backend.overlay import overlay_packet
                return self.send_json(overlay_packet(session.payload()))
            if path.path == "/api/state":
                result = session.payload()
                self.server.maybe_investigate(session)
                return self.send_json(result)
            if path.path == "/api/recap":
                self.server.maybe_investigate(session,'recap')
                return self.send_json(session.make_recap())
            if path.path == "/api/evidence":
                with session.lock:
                    snapshot = session.store.snapshot(session.at, False)
                    result = snapshot.get_evidence(query.get('id', []))
                    result['records'] = presentation_evidence(result['records'], review_state(snapshot._records))
                    return self.send_json(result)
            if path.path == "/api/stream":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                last = None
                for _ in range(120):
                    result = session.payload()
                    self.server.maybe_investigate(session)
                    key = (result["epoch"], result["sequence"], result["playing"], result['agent_status'])
                    if key != last or _ % 10 == 0:
                        self.wfile.write(("data: " + json.dumps(result, ensure_ascii=False) + "\n\n").encode())
                        last = key
                    else:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    time.sleep(.5)
                return
            self.send_json({"error": "Not found"}, 404)
        except (KeyError, ValueError) as error:
            self.send_json({"error": str(error)}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_POST(self):
        if not self.local_request():
            return self.send_json({"error": "Local origin required"}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if self.path == '/api/video/upload':
                return self.send_json(self.server.video.upload(self.rfile,length),201)
            if not 0 < length <= 20_000_000:
                raise ValueError("Invalid request size")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
            if self.path == '/api/video/start':
                return self.send_json(self.server.video.start(body['upload_id'],body.get('config',{})),202)
            if self.path == '/api/video/cancel':
                return self.send_json(self.server.video.cancel(body['job_id']))
            if self.path == '/api/video/session':
                s=Session.from_records(self.server.video.records(body['job_id']),body.get('preferences'),self.server.journal)
                with self.server.sessions_lock:self.server.sessions[s.id]=s
                return self.send_json(s.payload(),201)
            if self.path == "/api/session":
                with self.server.sessions_lock:
                    if len(self.server.sessions) >= 32:
                        self.server.sessions.pop(next(iter(self.server.sessions)))
                    s = Session.from_records(body['records'],body.get('preferences'),self.server.journal,body.get('live',False)) if 'records' in body else Session(body.get("stream", "stream-01"), body.get("preferences"), self.server.journal)
                    self.server.sessions[s.id] = s
                return self.send_json(s.payload(), 201)
            if self.path == "/api/control":
                return self.send_json(self.server.sessions[body.pop("session")].control(body))
            if self.path == '/api/ingest':
                return self.send_json(self.server.sessions[body['session']].ingest(body['records'],body['received_at_ms']))
            self.send_json({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError) as error:
            self.send_json({"error": str(error)}, 400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=43128)
    args = parser.parse_args()
    output = ROOT / "run-output"
    output.mkdir(exist_ok=True)
    server = AppServer(("127.0.0.1", args.port), str(output / "stories.sqlite3"))
    print(f"MatchLens http://127.0.0.1:{args.port} · model API locked={not policy_status()['enabled']}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

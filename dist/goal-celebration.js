import { playbackView } from './replay-view.js';

// Presentation is derived from received facts, so seeks and replays need no timer cleanup.
export function goalCelebration(payload, formatName = value => value, elapsed = 0) {
  if (!payload) return null;
  const view = playbackView(payload), review = payload.review;
  const phase = review?.phase ?? 'none';
  if (!['none','pending','awarded'].includes(phase)) return null;
  // Presentation interpolation may pass a future ruling's timestamp, but cannot receive it.
  if (phase !== 'none' && !(review.observed_at_ms <= payload.as_of_ms)) return null;
  const records = [...(payload.events ?? []), ...(payload.evidence_records ?? [])];
  const goal = records.filter(event => event.type === 'goal' && event.observed_at_ms <= payload.as_of_ms
    && (phase !== 'awarded' || review.evidence_ids?.includes(event.id)))
    .sort((a,b) => b.observed_at_ms-a.observed_at_ms)[0];
  const overlay = payload.overlays?.find(item => item.kind === 'goal');
  const pending = phase === 'pending';
  if (!pending && !goal && !overlay) return null;
  const at = pending ? review.observed_at_ms-view.receive_offset_ms
    : goal ? goal.observed_at_ms-view.receive_offset_ms : overlay.at_ms;
  const teamId = pending ? review.subject_team_id : goal?.team_id ?? overlay.team_id;
  const playerId = pending ? review.subject_player_id : goal?.player_id ?? review?.subject_player_id;
  const team = payload.state?.teams?.find(item => item.id === teamId);
  const player = payload.state?.roster?.find(item => item.id === playerId);
  // Interpolate only an already-received reaction between the half-second stream updates.
  const time = view.position_ms/1000 + (payload.playing ? Math.min(.5,Math.max(0,elapsed))*(payload.speed||1) : 0);
  const age = time-at/1000, duration = pending ? .5 : 5;
  if (!Number.isFinite(age) || age < 0 || age >= duration || !teamId) return null;
  return {kind:pending?'pending':'confirmed', age, duration,
    team:teamId==='A'?'blue':'coral', teamId, playerId,
    teamName:formatName(team?.name ?? teamId), playerName:formatName(player?.name ?? team?.name ?? teamId),
    goalX:(team?.attack_direction_x ?? (teamId==='A'?1:-1))===1?105:0,
    score:payload.state?.score};
}

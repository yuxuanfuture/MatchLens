export const REPLAY_STREAMS = ['stream-04'];

export function playbackView(payload) {
  return payload?.playback || {
    position_ms:payload?.as_of_ms || 0,
    duration_ms:payload?.duration_ms || 90000,
    receive_offset_ms:0,
    match_clock_ms:payload?.state?.match_clock_ms || 0,
    ended:false
  };
}

export function receiveTime(payload, seconds) {
  const view=playbackView(payload);
  const position=Math.min(view.duration_ms,Math.max(0,Math.round((Number(seconds)||0)*1000)));
  return position+view.receive_offset_ms;
}

export function evidenceVisible(record, current, requested) {
  return !!(record&&current&&current.session_id===requested.session_id&&current.epoch===requested.epoch
    &&record.match_id===current.state.match_id
    &&Math.max(record.event_time_ms,record.observed_at_ms)<=current.as_of_ms);
}

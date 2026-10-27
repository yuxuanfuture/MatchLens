"""Derive the current official ruling from received facts, never fixture answers."""

OFFICIAL_TYPES = frozenset({'offside_flag', 'decision', 'var'})
VAR_PHASES = {'check_started': 'checking', 'evidence_ready': 'checking',
              'on_field_review_requested': 'review_requested',
              'on_field_review_started': 'reviewing',
              'on_field_review_completed': 'awaiting_decision'}


def review_state(records):
    visible = {r['id']: r for r in records}
    state = {'phase': 'none', 'current_decision': None, 'evidence_ids': []}
    events = sorted((r for r in records if r['record_type'] == 'event'),
                    key=lambda r: (r['observed_at_ms'], r['event_time_ms'], r['id']))
    for event in events:
        kind = event['type']
        phase = None
        if kind == 'shot_end' and event.get('goal_status') == 'pending':
            phase = 'pending'
        elif kind == 'offside_flag':
            phase = 'flagged'
        elif kind == 'decision' and event.get('outcome') in {'goal_disallowed', 'goal_awarded'}:
            state['current_decision'] = event['outcome']
            phase = 'flagged' if event['outcome'] == 'goal_disallowed' else 'awarded'
        elif kind == 'var':
            phase = VAR_PHASES.get(event.get('stage'))
        if phase is not None:
            state.update(phase=phase, event_id=event['id'], subject_player_id=event.get('subject_player_id') or event.get('player_id'),
                         subject_team_id=event.get('subject_team_id') or event.get('team_id'),
                         event_time_ms=event['event_time_ms'], observed_at_ms=event['observed_at_ms'])
            state['evidence_ids'].extend([event['id'], *event.get('evidence_ids', [])])
    confirmations = [e['id'] for e in events if state['phase'] == 'awarded'
                     and e['type'] == 'goal' and e.get('decision_id') in state['evidence_ids']]
    refs = [*confirmations, state.get('event_id'), *state['evidence_ids']]
    state['evidence_ids'] = list(dict.fromkeys(i for i in refs if i in visible))
    return state


def presentation_evidence(records, review):
    """Keep body-part review details behind the received review reference in UI."""
    allowed = set(review['evidence_ids'])
    return [{k: v for k, v in record.items() if k != 'body_parts'}
            if 'body_parts' in record and record['id'] not in allowed else record
            for record in records]


def confirmed_goal_cues(records, as_of_ms, playback=None):
    """Late confirmations are fresh at receipt; preserve the original goal time."""
    offset = playback['receive_offset_ms'] if playback else 0
    result = []
    for event in records:
        if event.get('type') != 'goal':
            continue
        if 0 <= as_of_ms - event['observed_at_ms'] < 4000:
            start = event['observed_at_ms'] - offset
            result.append({'kind': 'goal', 'at_ms': start, 'end_ms': start + 4000,
                           'clock_basis': 'playback_ms' if playback else 'observation_ms',
                           'event_time_ms': event['event_time_ms'], 'observed_at_ms': event['observed_at_ms'],
                           'team_id': event['team_id'], 'evidence_id': event['id'],
                           'evidence_ids': [event['id'], *event.get('evidence_ids', [])]})
    return result

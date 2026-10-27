"""Public input contracts for replay, live feeds and inferred video events."""
import math
from backend.review_state import OFFICIAL_TYPES

EVENT_TYPES={'pass','shot','shot_end','goal','save','carry','tackle','recovery','interception',
             'possession_change','pressure','substitution','formation_change','kickoff','period_start','full_time'} | OFFICIAL_TYPES


def validate_record(row, metadata=None):
    if not isinstance(row,dict): raise ValueError('Record must be an object')
    for key in ['id','match_id','record_type']:
        if not isinstance(row.get(key),str) or not 1<=len(row[key])<=128: raise ValueError(f'Invalid {key}')
    for key in ['event_time_ms','observed_at_ms']:
        if type(row.get(key)) is not int or row[key]<0: raise ValueError(f'Invalid {key}')
    if row['record_type'] not in {'metadata','event','tracking','coverage'}: raise ValueError('Invalid record type')
    if metadata and row['match_id']!=metadata['match_id']: raise ValueError('Match identity changed')
    def position(p):
        if p is None:return
        if not isinstance(p,dict) or any(type(p.get(k)) not in [int,float] or not math.isfinite(p[k]) for k in ['x','y']): raise ValueError('Invalid coordinates')
        if not 0<=p['x']<=105 or not 0<=p['y']<=68:raise ValueError('Coordinates outside pitch')
    if row['record_type']=='metadata':
        if metadata:raise ValueError('Metadata already exists')
        if row['event_time_ms']!=0 or row['observed_at_ms']!=0:raise ValueError('Metadata must start at zero')
        roster=row.get('roster',[])
        if not 1<=len(roster)<=1000 or len({p['id'] for p in roster})!=len(roster):raise ValueError('Invalid roster')
        if {t['id'] for t in row.get('teams',[])}!={'A','U'}:raise ValueError('Teams A and U required')
        if any(t.get('attack_direction_x') not in {-1,1} or not isinstance(t.get('name'),str) for t in row['teams']):raise ValueError('Team name and attack direction required')
        for player in roster:
            if player.get('team_id') not in {'A','U'} or not isinstance(player.get('name'),str):raise ValueError('Invalid player')
        if any(c not in row.get('channels',{}) for c in ['events','event_positions','tracking','pressure']):raise ValueError('Channel coverage required')
        if any(v not in {'available','unavailable'} for v in row['channels'].values()):raise ValueError('Invalid channel status')
        if row.get('initial_possession_team_id') not in {'A','U',None}:raise ValueError('Invalid possession')
        if not isinstance(row.get('pitch'),dict) or row['pitch'].get('length_m')!=105 or row['pitch'].get('width_m')!=68:raise ValueError('105 by 68 metre coordinates required')
        if set(row.get('initial_score',{}))!={'A','U'} or any(type(v) is not int or v<0 for v in row['initial_score'].values()):raise ValueError('Invalid initial score')
        if type(row.get('match_clock_start_ms')) is not int:raise ValueError('Match clock origin required')
        if 'officials' in row:
            officials=row['officials']
            if not isinstance(officials,list) or any(not isinstance(p,dict) or not isinstance(p.get('id'),str) or p.get('role') not in {'referee','assistant_referee','video_assistant_referee'} for p in officials):raise ValueError('Invalid officials')
            if len({p['id'] for p in officials})!=len(officials) or {p['id'] for p in officials}&{p['id'] for p in roster}:raise ValueError('Duplicate official identity')
        return
    if not metadata:raise ValueError('Metadata required first')
    roster={p['id']:p for p in metadata['roster']}
    if row['record_type']=='event':
        if row.get('type') not in EVENT_TYPES:raise ValueError('Unsupported football event')
        if row['type'] in OFFICIAL_TYPES:
            if row.get('schema_version')!='1.2' or metadata.get('schema_version')!='1.2':raise ValueError('Official events require schema 1.2')
            officials = {p['id']: p['role'] for p in metadata.get('officials', [])}
            role = 'assistant_referee' if row['type']=='offside_flag' else 'video_assistant_referee' if row['type']=='var' and row.get('stage') in {'check_started','evidence_ready'} else 'referee'
            if row.get('player_id') is not None or row.get('team_id') is not None:raise ValueError('Official cannot impersonate player')
            if row.get('official_id') not in officials or officials[row['official_id']]!=role:raise ValueError('Wrong official role')
            subject=roster.get(row.get('subject_player_id'))
            if not subject or subject['team_id']!=row.get('subject_team_id'):raise ValueError('Official subject/team mismatch')
            if row.get('position') is not None or row.get('position_status')!='unavailable':raise ValueError('Official position must be unavailable')
            return
        if row.get('player_id') not in roster or roster[row['player_id']]['team_id']!=row.get('team_id'):raise ValueError('Unknown actor or team mismatch')
        for key in ['receiver_id','opponent_id','player_in_id','player_out_id']:
            if row.get(key) and row[key] not in roster:raise ValueError('Unknown related player')
        for key in ['position','end_position','opponent_position']:position(row.get(key))
        if row['type']=='pass' and (row.get('outcome') not in {'complete','incomplete','unknown'} or not row.get('receiver_id')):raise ValueError('Pass outcome and receiver required')
        if row['type']=='shot' and ('outcome' in row or 'end_position' in row):raise ValueError('Shot must not reveal future outcome')
    elif row['record_type']=='tracking':
        players=row.get('players') or []
        if len({p['player_id'] for p in players})!=len(players):raise ValueError('Duplicate tracked player')
        for player in players:
            if player['player_id'] not in roster:raise ValueError('Unknown tracked player')
            position(player)
        position(row.get('ball'))
    elif row['record_type']=='coverage':
        if not set(row.get('channels',[]))<=set(metadata['channels']) or row.get('status') not in {'available','unavailable'}:raise ValueError('Invalid coverage update')


def validate_stream(rows):
    if not isinstance(rows,list) or not rows or len(rows)>100000:raise ValueError('Supply 1..100000 records')
    validate_record(rows[0])
    if rows[0]['record_type']!='metadata':raise ValueError('Metadata required first')
    seen=set()
    for row in rows:
        if row['id'] in seen:raise ValueError('Duplicate record IDs')
        if row is not rows[0]:validate_record(row,rows[0])
        seen.add(row['id'])
    return rows

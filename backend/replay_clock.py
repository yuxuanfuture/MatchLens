"""Source playback coordinates, separate from the receiving clock."""


def replay_clock(metadata, rows):
    """Opt in authored segments; legacy streams keep their existing clock."""
    if metadata.get('schema_version') != '1.2' or metadata.get('observation_scope') != 'segment':
        return None
    first = next((r for r in rows if r['record_type'] == 'tracking' and r['event_time_ms'] == 0), None)
    duration = metadata.get('scheduled_duration_ms')
    if first is None or type(duration) is not int or duration <= 0:
        return None
    return {'duration_ms': duration, 'receive_offset_ms': first['observed_at_ms'],
            'announced_added_time_ms': metadata.get('announced_added_time_ms', 0)}


def playback_view(config, as_of_ms, match_clock_start_ms):
    position = min(config['duration_ms'], max(0, as_of_ms - config['receive_offset_ms']))
    return {**config, 'position_ms': position,
            'match_clock_ms': match_clock_start_ms + position,
            'ended': position == config['duration_ms']}

"""Transport-neutral timed cues for a browser source or broadcast renderer."""
def overlay_packet(payload):
 now=payload.get('playback',{}).get('position_ms',payload['as_of_ms']);story=payload['story']
 cues=[{'id':story['id'],'kind':'narrative','start_ms':story['display_at_ms'],'end_ms':story['expires_at_ms'],
        'title':story['title'],'fan':story['fan_text'],'analyst':story['analyst_text'],
        'evidence_ids':story['evidence_ids'],'window_ms':story['window_ms']}]
 for index,shape in enumerate(payload['overlays']):
  cues.append({'id':f"{shape['evidence_id']}:{shape['kind']}",'kind':shape['kind'],
    'start_ms':shape.get('at_ms',now) if shape['kind']=='goal' else now,
    'end_ms':shape.get('end_ms',now+1000),
    'evidence_ids':list(dict.fromkeys([shape['evidence_id'],*shape.get('evidence_ids',[])])),'geometry':shape})
 return {'schema_version':'matchlens.overlay/1.0','session_id':payload['session_id'],
   'epoch':payload['epoch'],'sequence':payload['sequence'],'source':payload['mode'],
   'clock':{'basis':'source_media_ms','time_ms':now,'observation_time_ms':payload['as_of_ms'],'match_clock_offset_ms':payload['state']['match_clock_start_ms'],
            'playing':payload['playing'],'speed':payload['speed']},
   'preferences':payload['preferences'],'cues':cues}

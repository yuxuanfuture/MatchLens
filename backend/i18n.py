"""The browser and offline publisher share the same five UTF-8 catalogs."""
import json
import re
from functools import lru_cache
from pathlib import Path

LANGUAGES = ('en', 'zh', 'fr', 'es', 'ar')
CATALOGS = Path(__file__).resolve().parents[1] / 'dist' / 'locales'


@lru_cache(maxsize=5)
def catalog(language):
    if language not in LANGUAGES:
        raise ValueError('Invalid language')
    return json.loads((CATALOGS / f'{language}.json').read_text(encoding='utf-8'))


def display_name(language, value):
    if not isinstance(value,str): return value
    track = re.fullmatch(r'Team ([AU]) · track (\d+)', value)
    team = re.fullmatch(r'Team ([AU])', value)
    if track: return catalog(language)['name.anonymous'].format(team=track[1], track=track[2])
    if team: return catalog(language)['name.team'].format(team=team[1])
    return value


def text(language, key, **values):
    translated = catalog(language)
    return translated[key].format(**{key: translated['common.unknown'] if value is None else display_name(language,value) for key, value in values.items()})

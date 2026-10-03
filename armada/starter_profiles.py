"""Bundled starter profiles, separate from personal realms and copied only at creation."""
import copy
import json
import re
from pathlib import Path
from .templates import TEMPLATES


def roster(template, owner="{owner}"):
    if template == "state":
        agents = json.loads(Path(__file__).with_name('starter_profiles.json').read_text(encoding='utf-8'))['agents']
    elif template in ("company", "crew"):
        from .starter_generic_profiles import roster as generic_roster
        agents = generic_roster(template)
    else:
        agents = copy.deepcopy(TEMPLATES.get(template, TEMPLATES['scratch'])['agents'])
    for i, agent in enumerate(agents):
        agent.setdefault('avatar', f'a{i + 9}.png')
        for key in ('mandate', 'voice', 'tenets', 'leader'):
            from . import covenant
            agent[key] = covenant.adapt(agent.get(key, '').replace('{owner}', owner), template)
    return agents


def custom(data, index):
    """Accept profile text, never arbitrary paths, tools, or executable settings from setup."""
    display = ' '.join(str(data.get('display') or '').split())[:40]
    if not display:
        raise ValueError('Give every added agent a name, or remove its empty profile.')
    slug = re.sub(r'[^a-z0-9]+', '-', display.lower()).strip('-')[:32] or 'agent'
    result = {'id': f'custom-{index}-{slug}', 'display': display, 'coordinator': data.get('coordinator') is True}
    for key, limit in (('role', 60), ('leader', 500), ('mandate', 20000), ('voice', 20000), ('tenets', 20000)):
        result[key] = str(data.get(key) or '').strip()[:limit]
    if not result['mandate']:
        result['mandate'] = f'You are {display}. Propose actions for the owner to approve.'
    avatar = str(data.get('avatar') or 'a20.png')
    result['avatar'] = avatar if re.fullmatch(r'a(?:[1-9]|1[0-9]|20)\.png', avatar) else 'a20.png'
    dataurl = str(data.get('avatar_data') or '')
    if dataurl:
        import base64
        import binascii
        try:
            if not dataurl.startswith('data:image/png;base64,') or len(dataurl) > 700_000:
                raise ValueError('Use a PNG portrait no larger than 500 KB.')
            raw = base64.b64decode(dataurl.split(',', 1)[1], validate=True)
            if len(raw) > 500_000:
                raise ValueError('Use a PNG portrait no larger than 500 KB.')
            if raw[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR' or raw[16:24] != b'\x00\x00\x01\x00\x00\x00\x01\x00':
                raise ValueError('Choose the portrait again to crop it to 256 × 256.')
        except (binascii.Error, IndexError) as exc:
            raise ValueError('Could not read the portrait. Choose another image.') from exc
        result['avatar_data'] = dataurl
    return result

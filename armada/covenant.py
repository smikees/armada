"""One shared governing document, named for the realm's chosen vocabulary."""
import json
from pathlib import Path

NAMES = {'state': 'Constitution', 'company': 'Memorandum', 'crew': 'Code', 'scratch': 'Covenant'}


def title(template: str) -> str:
    return 'The ' + NAMES.get(template, 'Covenant')


def template_of(root) -> str:
    try:
        return json.loads((Path(root) / 'realm.json').read_text(encoding='utf-8-sig')).get('template', 'scratch')
    except (OSError, ValueError, TypeError):
        return 'scratch'


def name(root) -> str:
    return title(template_of(root))


def adapt(text: str, template: str) -> str:
    """Change vocabulary, preserving the owner's substantive terms."""
    import re
    text = re.sub(r'\b([Tt]he) (?:Covenant|Constitution|Memorandum|Code)\b', lambda m: m[1] + ' ' + NAMES.get(template, 'Covenant'), text)
    area = {'state': 'ministry', 'company': 'department', 'crew': 'area', 'scratch': 'area'}.get(template, 'area')
    return re.sub(r'your own (?:ministry|department|area)', 'your own ' + area, text)


def starter(template: str) -> str:
    text = json.loads(Path(__file__).with_name('starter_profiles.json').read_text(encoding='utf-8'))['covenant']
    return adapt(text, template)

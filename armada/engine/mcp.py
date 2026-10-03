"""Translate MCP display names to their tool namespace without granting access."""
import re


def server_id(name: str) -> str:
    """Claude-managed connectors use a collapsed, prefixed tool namespace."""
    if name.startswith('claude.ai '):
        return 'claude_ai_' + re.sub(r'[^A-Za-z0-9_-]+', '_', name[len('claude.ai '):]).strip('_')
    return re.sub(r'[^A-Za-z0-9_-]', '_', name)


def connected_names(text: str) -> frozenset[str]:
    """Names with an explicit Connected health result, never inferred from an icon."""
    names = set()
    for line in re.sub(r'\x1b\[[0-9;]*m', '', text).splitlines():
        name, separator, detail = line.strip().partition(': ')
        if separator and ' - ' in detail:
            state = detail.rsplit(' - ', 1)[-1].strip().lower()
            if re.fullmatch(r'(?:[✓✔√]\ufe0f?\s*)?connected', state):
                names.add(name)
    return frozenset(names)

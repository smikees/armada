"""Keep a CLI JSON value's original spelling across normalized display events."""
import json


class SourceEvent(dict):
    """A parsed event carrying its original UTF-8 JSON line, for capture only."""
    def __init__(self, data, source):
        super().__init__(data)
        self.source = source


def loads_event(line):
    data = json.loads(line)
    return SourceEvent(data, line) if isinstance(data, dict) else data


def result_source(event, path):
    return {"event": getattr(event, "source", None), "path": list(path)}


def payload(source):
    """Extract a JSON token verbatim; unwrap strings exactly once, without trimming."""
    raw, path = source.get("event"), source.get("path", [])
    if not isinstance(raw, str):
        raise ValueError("Engine did not expose the original result bytes.")
    decoder = json.JSONDecoder()
    pos = 0
    def whitespace(index):
        while index < len(raw) and raw[index] in " \t\r\n":
            index += 1
        return index
    for part in path:
        pos = whitespace(pos)
        if raw[pos] == "{" and isinstance(part, str):
            pos = whitespace(pos + 1)
            while raw[pos] != "}":
                key, end = decoder.raw_decode(raw, pos)
                pos = whitespace(end)
                if raw[pos] != ":":
                    raise ValueError("Invalid result object.")
                pos = whitespace(pos + 1)
                if key == part:
                    break
                _, pos = decoder.raw_decode(raw, pos)
                pos = whitespace(pos)
                if raw[pos] == ",":
                    pos = whitespace(pos + 1)
            else:
                raise ValueError(f"Engine omitted result field {part}.")
        elif raw[pos] == "[" and isinstance(part, int):
            pos = whitespace(pos + 1)
            for _ in range(part):
                _, pos = decoder.raw_decode(raw, pos)
                pos = whitespace(pos)
                if raw[pos] != ",":
                    raise ValueError("Engine omitted result block.")
                pos = whitespace(pos + 1)
        else:
            raise ValueError("Engine result shape changed.")
    pos = whitespace(pos)
    value, end = decoder.raw_decode(raw, pos)
    return (value, "text") if isinstance(value, str) else (raw[pos:end], "json")

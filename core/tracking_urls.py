import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


PLACEHOLDER_PATTERN = re.compile(r'\{([a-zA-Z_][\w.-]*)\}')


def render_placeholders(value, values):
    def replace_placeholder(match):
        return str(values.get(match.group(1), ''))

    return PLACEHOLDER_PATTERN.sub(replace_placeholder, value or '')


def tracking_query_string(query_string, values, force_values=None, add_missing=None):
    force_values = force_values or {}
    add_missing = add_missing or {}
    query_items = []
    seen_keys = set()

    for key, value in parse_qsl(query_string or '', keep_blank_values=True):
        rendered_key = render_placeholders(key, values)
        rendered_value = str(force_values.get(rendered_key, render_placeholders(value, values)))
        query_items.append((rendered_key, rendered_value))
        seen_keys.add(rendered_key)

    for key, value in add_missing.items():
        if key not in seen_keys:
            query_items.append((key, str(value)))
            seen_keys.add(key)

    for key, value in force_values.items():
        if key not in seen_keys:
            query_items.append((key, str(value)))

    return urlencode(query_items)


def append_query_string(url, query_string, skip_existing=False):
    if not query_string:
        return url

    parts = urlsplit(url)
    query_items = parse_qsl(parts.query, keep_blank_values=True)
    existing_keys = {key for key, _value in query_items}
    for key, value in parse_qsl(query_string, keep_blank_values=True):
        if skip_existing and key in existing_keys:
            continue
        query_items.append((key, value))
        existing_keys.add(key)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_items), parts.fragment))

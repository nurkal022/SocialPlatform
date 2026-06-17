from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    if not isinstance(d, dict):
        return None
    return d.get(str(key)) or d.get(key)


@register.filter
def stars(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 0
    return "★" * n + "☆" * max(0, 5 - n)


@register.filter
def percent(part, whole):
    try:
        if not whole:
            return 0
        return int(round(float(part) * 100 / float(whole)))
    except (TypeError, ValueError):
        return 0


@register.filter
def youtube_embed(url):
    """Convert any YouTube URL to embed URL. Returns original if not YouTube."""
    if not url:
        return ""
    import re
    # https://www.youtube.com/watch?v=ID  →  embed/ID
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{11})", url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}?rel=0"
    return url

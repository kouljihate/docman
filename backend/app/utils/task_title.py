"""Derive a short task title from a long task sentence.

Seeded tasks store the whole instruction ("Rédiger et réviser les statuts,
pactes d'associés, contrats commerciaux...") as their title. This module turns
that sentence into a readable label for the title column, while the caller keeps
the full sentence as the task description.
"""
import re

# Longest accepted short title, in characters.
MAX_TITLE_CHARS = 48
# A candidate needs this many characters saved before it replaces a title.
MIN_SAVING = 8
MIN_WORDS = 2

# A clause ends at a comma, semicolon, colon, bracket, dash or slash.
_CLAUSE_BREAK = re.compile(r"[,;:(\[\u2013\u2014]|\s+-\s+|\s+/\s+|\s*\|\s*")

# Words a short title should not end on.
_TRAILING_STOPWORDS = {
    "de", "des", "du", "d'", "d’", "le", "la", "les", "l'", "l’",
    "un", "une", "et", "ou", "en", "\u00e0", "au", "aux", "sur", "dans",
    "pour", "par", "avec", "sans", "selon", "dont", "que",
    "lorsque", "lorsqu'", "lorsqu’", "quand", "si", "afin", "car",
    "the", "a", "an", "of", "and", "or", "for", "with", "to", "in", "on",
}


def _trim_trailing_stopwords(text):
    words = text.split()
    while len(words) > MIN_WORDS and words[-1].lower() in _TRAILING_STOPWORDS:
        words.pop()
    return " ".join(words)


def extract_short_title(text, max_chars=MAX_TITLE_CHARS):
    """Return a short, capitalised label for a task title."""
    if not text:
        return ""

    cleaned = " ".join(str(text).split()).strip().rstrip(" .!?,;")
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    candidate = _CLAUSE_BREAK.split(cleaned, 1)[0].strip(" -\u2013\u2014,;:")
    if len(candidate.split()) < MIN_WORDS or len(candidate) < 12:
        candidate = cleaned

    if len(candidate) > max_chars:
        cut = candidate[:max_chars]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        candidate = cut

    candidate = _trim_trailing_stopwords(candidate).rstrip(" ,;:-\u2013\u2014")
    if not candidate:
        return ""
    return candidate[:1].upper() + candidate[1:]


def plan_task_change(task, max_chars=MAX_TITLE_CHARS):
    """Return ``(short_title, description)`` for a task, or ``None`` to keep it.

    Short titles are left untouched, so running the migration twice changes
    nothing the second time.
    """
    title = (task.get("title") or "").strip()
    if len(title) <= max_chars:
        return None

    short = extract_short_title(title, max_chars=max_chars)
    if not short or short == title or len(title) - len(short) < MIN_SAVING:
        return None

    description = (task.get("description") or "").strip()
    # A title shorter than its own description is already a label.
    if description and len(description) > len(title) and description != title:
        return None
    if not description or description == title:
        new_description = title
    else:
        new_description = f"{title}\n\n{description}"
    return short, new_description

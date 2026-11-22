"""Human readable affair references.

An affair is labelled ``A`` + ``YYMMDD`` + ``-`` + ``HHMM``, for example
``A261122-1930``. The reference is unique inside a company: when two affairs are
opened in the same minute, the later one moves to the next free minute.
"""
from datetime import datetime, timedelta

PREFIX = "A"
_MINUTES_PER_DAY = 24 * 60


def build_reference(moment):
    """Return the reference for a given moment, e.g. ``A261122-1930``."""
    return f"{PREFIX}{moment:%y%m%d}-{moment:%H%M}"


def next_reference(db, company_id, moment=None):
    """Return the first reference at or after `moment` not used by `company_id`."""
    moment = (moment or datetime.now()).replace(second=0, microsecond=0)
    for _ in range(_MINUTES_PER_DAY):
        reference = build_reference(moment)
        if not db.affairs.find_one(
            {"company_id": company_id, "reference": reference}, {"_id": 1}
        ):
            return reference
        moment += timedelta(minutes=1)
    # Every minute of the day is taken: fall back to a suffixed reference.
    return f"{build_reference(moment)}-{int(moment.timestamp()) % 1000:03d}"

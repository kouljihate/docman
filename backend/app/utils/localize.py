"""Serve stored values in the language selected in the interface.

Seeded services and tasks keep French in their base ``name`` / ``title`` /
``description`` fields and carry ``name_i18n``, ``title_i18n`` and
``description_i18n`` maps. The helpers below swap those fields for the value of
the request language, falling back to the stored French text.
"""
from flask import request

LANGUAGES = ("en", "fr", "ar")
DEFAULT_LANG = "en"
# Stored values are already French, so French needs no lookup.
SOURCE_LANG = "fr"

TASK_FIELDS = {"title": "title_i18n", "description": "description_i18n"}
SERVICE_FIELDS = {"name": "name_i18n"}


def current_lang():
    """Language chosen in the footer dialog (cookie) or on the URL."""
    lang = request.args.get("lang") or request.cookies.get("lang") or DEFAULT_LANG
    return lang if lang in LANGUAGES else DEFAULT_LANG


def localize_doc(doc, fields, lang=None):
    """Return ``doc`` with each field replaced by its translation, if any."""
    if not doc:
        return doc
    lang = lang or current_lang()
    if lang == SOURCE_LANG:
        return doc

    localized = dict(doc)
    for field, i18n_field in fields.items():
        value = (doc.get(i18n_field) or {}).get(lang)
        if value:
            localized[field] = value
    return localized


def localize_task(task, lang=None):
    return localize_doc(task, TASK_FIELDS, lang)


def localize_service(service, lang=None):
    return localize_doc(service, SERVICE_FIELDS, lang)

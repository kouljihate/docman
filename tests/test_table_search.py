from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
BASE = BACKEND_DIR / "app" / "templates" / "base.html"
SCRIPT = BACKEND_DIR / "app" / "static" / "js" / "table_search.js"
CSS = BACKEND_DIR / "app" / "static" / "css" / "app.css"


def test_shared_layout_loads_the_table_search_script():
    base = BASE.read_text(encoding="utf-8")
    assert "data-search-placeholder=\"{{ _('search') }}\"" in base
    assert "/static/js/table_search.js" in base


def test_script_inserts_a_centred_row_at_the_top_of_every_table():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "table-search-row" in source
    assert "head.insertBefore(row, head.firstChild)" in source
    assert "closest('.modal')" in source
    assert "justify-content: center" in CSS.read_text(encoding="utf-8")

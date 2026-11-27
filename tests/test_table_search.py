from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
BASE = BACKEND_DIR / "app" / "templates" / "base.html"
SCRIPT = BACKEND_DIR / "app" / "static" / "js" / "table_search.js"
CSS = BACKEND_DIR / "app" / "static" / "css" / "app.css"


def test_shared_layout_loads_the_table_toolbar_and_its_export_dialog():
    base = BASE.read_text(encoding="utf-8")
    assert "data-search-placeholder=\"{{ _('search') }}\"" in base
    assert "data-export-label=\"{{ _('export') }}\"" in base
    assert "/static/js/table_search.js" in base
    assert 'id="tableExportModal"' in base
    assert 'value="csv"' in base
    assert 'value="pdf"' in base


def test_toolbar_row_is_split_in_three_columns_with_a_rounded_search():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "table-search-row" in source
    assert "head.insertBefore(row, head.firstChild)" in source
    assert "'40%'" in source and "'20%'" in source
    assert "splitColumns" in source
    assert "table-export-btn" in source
    assert "closest('.modal')" in source

    css = CSS.read_text(encoding="utf-8")
    assert "border-radius: 50rem" in css
    assert ".table-toolbar-end" in css


def test_export_writes_csv_and_pdf_downloads():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "text/csv" in source
    assert "tableName(table) + '.csv'" in source
    assert "tableName(table) + '.pdf'" in source
    assert "pdf.save" in source

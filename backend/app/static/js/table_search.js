/**
 * Toolbar carried by the first row of every data table.
 *
 * That row is split in three columns (40% / 20% / 40%): a rounded search field
 * filters the rows as you type, the middle column stays empty as a spacer, and
 * the third column holds an Export button. Export asks for CSV or PDF, then
 * downloads the rows currently visible (the filter is honoured).
 */
(function () {
    'use strict';

    var body = document.body;
    var SEARCH_LABEL = (body && body.dataset.searchPlaceholder) || 'Search';
    var EXPORT_LABEL = (body && body.dataset.exportLabel) || 'Export';
    var READY = 'ready';
    var PDF_SCRIPTS = [
        'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js',
        'https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js'
    ];

    var exportTable = null;

    function normalize(value) {
        return (value || '')
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }

    function bodyRows(table) {
        var tbody = table.tBodies[0];
        if (!tbody) return [];
        return Array.prototype.filter.call(tbody.rows, function (row) {
            return row.closest('table') === table;
        });
    }

    function visibleRows(table) {
        return bodyRows(table).filter(function (row) {
            return !row.classList.contains('d-none');
        });
    }

    function filterRows(table, input, resetPage) {
        var needle = normalize(input.value);
        bodyRows(table).forEach(function (row) {
            var match = !needle || normalize(row.textContent).indexOf(needle) !== -1;
            row.classList.toggle('d-none', !match);
        });
        table.classList.toggle('table-searching', needle !== '');
        // The page holds the matches of every page, not just the rows that were
        // on screen before the search.
        if (typeof window.refreshTablePagination === 'function') {
            window.refreshTablePagination(table, resetPage === true);
        }
    }

    /** Split the table width in the 40% / 20% / 40% toolbar columns. */
    function splitColumns(total) {
        if (total < 3) return null;
        var first = Math.max(1, Math.round(total * 0.4));
        var middle = Math.max(1, Math.round(total * 0.2));
        var last = total - first - middle;
        if (last < 1) {
            last = 1;
            first = Math.max(1, total - middle - last);
        }
        return [first, middle, last];
    }

    // ── Export ──────────────────────────────────────────────

    function tableName(table) {
        if (table.dataset.exportName) return table.dataset.exportName;
        var heading = document.querySelector('main h4');
        var title = (heading && heading.textContent.trim()) || document.title || 'table';
        return title
            .replace(/[\\/:*?"<>|\s]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .toLowerCase() || 'table';
    }

    function download(blob, filename) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    function csvCell(value) {
        var text = (value || '').replace(/\s+/g, ' ').trim();
        return '"' + text.replace(/"/g, '""') + '"';
    }

    function csvRow(cells) {
        return Array.prototype.map.call(cells, function (cell) {
            return csvCell(cell.innerText);
        }).join(',');
    }

    function exportCsv(table) {
        var lines = [];
        if (table.tHead) {
            Array.prototype.forEach.call(table.tHead.rows, function (row) {
                if (row.classList.contains('table-search-row')) return;
                lines.push(csvRow(row.cells));
            });
        }
        visibleRows(table).forEach(function (row) {
            var cells = Array.prototype.filter.call(row.cells, function (cell) {
                return cell.closest('table') === table;
            });
            if (cells.length) lines.push(csvRow(cells));
        });
        // The BOM keeps accents and Arabic readable in Excel.
        var csv = '\ufeff' + lines.join('\r\n');
        download(new Blob([csv], { type: 'text/csv;charset=utf-8;' }), tableName(table) + '.csv');
    }

    function loadScript(src) {
        return new Promise(function (resolve, reject) {
            if (document.querySelector('script[src="' + src + '"]')) {
                resolve();
                return;
            }
            var script = document.createElement('script');
            script.src = src;
            script.onload = function () { resolve(); };
            script.onerror = function () { reject(new Error('Could not load ' + src)); };
            document.head.appendChild(script);
        });
    }

    function notify(message) {
        if (typeof window.showToast === 'function') window.showToast(message, 'danger');
    }

    async function exportPdf(table) {
        try {
            for (var index = 0; index < PDF_SCRIPTS.length; index += 1) {
                await loadScript(PDF_SCRIPTS[index]);
            }
            // Rasterising keeps the Arabic and accented characters intact,
            // which a PDF font built from scratch would not.
            table.classList.add('table-exporting');
            var canvas = await window.html2canvas(table, {
                scale: 2,
                backgroundColor: '#ffffff',
                windowWidth: Math.max(document.documentElement.clientWidth, table.scrollWidth),
            });
            table.classList.remove('table-exporting');

            var JsPDF = window.jspdf.jsPDF;
            var pdf = new JsPDF({ unit: 'pt', format: 'a4', orientation: 'landscape' });
            var pageWidth = pdf.internal.pageSize.getWidth();
            var pageHeight = pdf.internal.pageSize.getHeight();
            var margin = 24;
            var printableWidth = pageWidth - margin * 2;
            var scale = printableWidth / canvas.width;
            var sliceHeight = Math.floor((pageHeight - margin * 2) / scale);
            var offset = 0;

            while (offset < canvas.height) {
                var height = Math.min(sliceHeight, canvas.height - offset);
                var slice = document.createElement('canvas');
                slice.width = canvas.width;
                slice.height = height;
                slice.getContext('2d').drawImage(
                    canvas, 0, offset, canvas.width, height, 0, 0, canvas.width, height
                );
                if (offset > 0) pdf.addPage();
                pdf.addImage(slice.toDataURL('image/png'), 'PNG', margin, margin, printableWidth, height * scale);
                offset += height;
            }
            pdf.save(tableName(table) + '.pdf');
        } catch (error) {
            notify(EXPORT_LABEL + ': ' + error.message);
        } finally {
            table.classList.remove('table-exporting');
        }
    }

    function askForFormat(table) {
        exportTable = table;
        var modalEl = document.getElementById('tableExportModal');
        if (!modalEl || !window.bootstrap) {
            exportCsv(table);
            return;
        }
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    }

    function confirmExport() {
        var modalEl = document.getElementById('tableExportModal');
        var modal = window.bootstrap && modalEl ? bootstrap.Modal.getInstance(modalEl) : null;
        var checked = document.querySelector('#tableExportForm input[name="format"]:checked');
        var table = exportTable;
        exportTable = null;
        if (modal) modal.hide();
        if (!table) return;
        if (checked && checked.value === 'pdf') exportPdf(table);
        else exportCsv(table);
    }

    // ── Toolbar construction ────────────────────────────────

    function buildSearch() {
        var bar = document.createElement('div');
        bar.className = 'table-search-bar';

        var group = document.createElement('div');
        group.className = 'input-group input-group-sm table-search-group';

        var icon = document.createElement('span');
        icon.className = 'input-group-text';
        icon.innerHTML = '<i class="bi bi-search"></i>';

        var input = document.createElement('input');
        input.type = 'search';
        input.className = 'form-control table-search-input';
        input.placeholder = SEARCH_LABEL;
        input.setAttribute('aria-label', SEARCH_LABEL);

        group.appendChild(icon);
        group.appendChild(input);
        bar.appendChild(group);
        return { bar: bar, input: input };
    }

    function buildExport(table) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-sm btn-outline-primary table-export-btn';
        button.innerHTML = '<i class="bi bi-download me-1"></i>';
        button.appendChild(document.createTextNode(EXPORT_LABEL));
        button.addEventListener('click', function () {
            askForFormat(table);
        });
        return button;
    }

    function enhance(table) {
        if (table.dataset.tableSearch === READY) return;
        if (table.closest('.modal') || table.hasAttribute('data-no-search')) return;
        if (!table.tBodies.length) return;
        table.dataset.tableSearch = READY;

        var head = table.tHead;
        if (!head) {
            head = document.createElement('thead');
            table.insertBefore(head, table.firstChild);
        }

        var columns = 1;
        if (head.rows[0]) {
            columns = Array.prototype.reduce.call(head.rows[0].cells, function (total, cell) {
                return total + (cell.colSpan || 1);
            }, 0);
        }

        var search = buildSearch();
        var exportButton = buildExport(table);

        var row = document.createElement('tr');
        row.className = 'table-search-row';

        var spans = splitColumns(columns);
        if (spans) {
            var searchCell = document.createElement('td');
            searchCell.colSpan = spans[0];
            searchCell.style.width = '40%';
            searchCell.className = 'table-toolbar-cell';
            searchCell.appendChild(search.bar);

            var spacer = document.createElement('td');
            spacer.colSpan = spans[1];
            spacer.style.width = '20%';
            spacer.className = 'table-toolbar-gap';

            var exportCell = document.createElement('td');
            exportCell.colSpan = spans[2];
            exportCell.style.width = '40%';
            exportCell.className = 'table-toolbar-cell table-toolbar-end';
            exportCell.appendChild(exportButton);

            row.appendChild(searchCell);
            row.appendChild(spacer);
            row.appendChild(exportCell);
        } else {
            // Very narrow tables keep both controls on one row.
            var cell = document.createElement('td');
            cell.colSpan = columns;
            cell.className = 'table-toolbar-cell table-toolbar-inline';
            cell.appendChild(search.bar);
            cell.appendChild(exportButton);
            row.appendChild(cell);
        }
        head.insertBefore(row, head.firstChild);

        search.input.addEventListener('input', function () {
            filterRows(table, search.input, true);
        });
        search.input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                search.input.value = '';
                filterRows(table, search.input, true);
            }
        });

        // Rows arrive after the API answers, so filter them again on every change.
        new MutationObserver(function () {
            filterRows(table, search.input);
        }).observe(table.tBodies[0], { childList: true, subtree: true });
    }

    function enhanceAll() {
        Array.prototype.forEach.call(document.querySelectorAll('table'), enhance);
    }

    var scanQueued = false;
    function queueScan() {
        if (scanQueued) return;
        scanQueued = true;
        window.setTimeout(function () {
            scanQueued = false;
            enhanceAll();
        }, 60);
    }

    document.addEventListener('DOMContentLoaded', function () {
        enhanceAll();
        var confirmButton = document.getElementById('tableExportConfirm');
        if (confirmButton) confirmButton.addEventListener('click', confirmExport);
        new MutationObserver(queueScan).observe(document.body, { childList: true, subtree: true });
    });
})();

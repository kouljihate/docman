/**
 * Centered search bar carried by the first row of every data table.
 *
 * The bar is injected as the first row of the table header (full width, centred)
 * and filters the body rows as you type, ignoring case and accents. Tables whose
 * rows are re-rendered by a page script (async API loads) are filtered again
 * automatically, and dialogs are left alone so their small tables stay compact.
 */
(function () {
    'use strict';

    var SEARCH_LABEL = (document.body && document.body.dataset.searchPlaceholder) || 'Search';
    var READY = 'ready';

    function normalize(value) {
        return (value || '')
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }

    function bodyRows(table) {
        var body = table.tBodies[0];
        if (!body) return [];
        return Array.prototype.filter.call(body.rows, function (row) {
            return row.closest('table') === table;
        });
    }

    function filterRows(table, input) {
        var needle = normalize(input.value);
        bodyRows(table).forEach(function (row) {
            var match = !needle || normalize(row.textContent).indexOf(needle) !== -1;
            row.classList.toggle('d-none', !match);
        });
        table.classList.toggle('table-searching', needle !== '');
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

        var row = document.createElement('tr');
        row.className = 'table-search-row';

        var cell = document.createElement('td');
        cell.colSpan = columns;

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
        cell.appendChild(bar);
        row.appendChild(cell);
        head.insertBefore(row, head.firstChild);

        input.addEventListener('input', function () {
            filterRows(table, input);
        });
        input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                input.value = '';
                filterRows(table, input);
            }
        });

        // Rows arrive after the API answers, so filter them again on every change.
        new MutationObserver(function () {
            filterRows(table, input);
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
        new MutationObserver(queueScan).observe(document.body, { childList: true, subtree: true });
    });
})();

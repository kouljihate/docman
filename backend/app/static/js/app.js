const API_BASE = '/api';

async function apiRequest(url, options = {}) {
    const { skipAuthRedirect = false, ...fetchOptions } = options;
    const isFormData = fetchOptions.body instanceof FormData;
    // The session token lives in an HttpOnly cookie, so no auth header is set.
    const headers = {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...fetchOptions.headers,
    };

    const res = await fetch(`${API_BASE}${url}`, {
        ...fetchOptions,
        headers,
    });

    // A failed sign-in answers 401 too: the login page shows that message, so it
    // must not be mistaken for an expired session and swallowed by a redirect.
    if (res.status === 401 && !skipAuthRedirect) {
        localStorage.removeItem('user');
        window.location.href = '/login';
        return;
    }

    const contentType = res.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return res.json();
    }
    return res;
}

async function login(username, password) {
    const data = await apiRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
        skipAuthRedirect: true,
    });
    if (data && data.user) {
        localStorage.setItem('user', JSON.stringify(data.user));
    }
    return data;
}

async function logout() {
    try {
        await apiRequest('/auth/logout', { method: 'POST' });
    } catch (_) {}
    localStorage.removeItem('user');
    window.location.href = '/login';
}

function getUser() {
    try {
        return JSON.parse(localStorage.getItem('user'));
    } catch {
        return null;
    }
}

function isAuthenticated() {
    return !!localStorage.getItem('user');
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) {
        const div = document.createElement('div');
        div.id = 'toast-container';
        div.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        div.style = 'z-index: 9999';
        document.body.appendChild(div);
    }
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    document.getElementById('toast-container').appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

function formatDate(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const yyyy = d.getFullYear();
        const hh = String(d.getHours()).padStart(2, '0');
        const min = String(d.getMinutes()).padStart(2, '0');
        const ss = String(d.getSeconds()).padStart(2, '0');
        const formatted = dd + '/' + mm + '/' + yyyy + ' ' + hh + ':' + min + ':' + ss;
        if (document.documentElement.lang === 'ar') {
            return '<span dir="ltr" class="western-nums">' + formatted + '</span>';
        }
        return formatted;
    } catch {
        return iso;
    }
}

let socket = null;
window.onlineUserIds = new Set();

function initSocketIO() {
    if (!isAuthenticated() || socket) return;

    // The handshake carries the HttpOnly cookie; nothing to pass in the query.
    socket = io({
        transports: ['websocket', 'polling'],
    });

    socket.on('notification', function (data) {
        showToast(data.title || 'New notification', 'info');
        if (typeof updateNotificationBadge === 'function') {
            updateNotificationBadge();
        }
        if (window.location.pathname === '/notifications' && typeof loadNotificationsPage === 'function') {
            loadNotificationsPage();
        }
        if (data.type && data.type.startsWith('activity_') && window.location.pathname === '/activities' && typeof loadActivities === 'function') {
            loadActivities();
        }
        if (window.location.pathname === '/audit' && typeof loadAudit === 'function') {
            loadAudit();
        }
    });

    socket.on('notification_badge', function (data) {
        const badge = document.getElementById('notificationBadge');
        if (badge) {
            if (data.count > 0) {
                badge.textContent = data.count;
                badge.style.display = 'inline';
            } else {
                badge.style.display = 'none';
            }
        }
    });

    socket.on('online_users', function (data) {
        window.onlineUserIds = new Set(data.user_ids || []);
    });

    socket.on('disconnect', function () {
        window.onlineUserIds = new Set();
    });
}

async function sendNotification(userId, message, title) {
    return apiRequest('/activities/notifications/send', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, message: message, title: title || 'Notification' }),
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const lang = document.documentElement.lang || localStorage.getItem('lang') || 'en';
    document.documentElement.lang = lang;
    if (lang === 'ar') {
        document.documentElement.dir = 'rtl';
    }
    localStorage.setItem('lang', lang);
    if (isAuthenticated()) initSocketIO();
});

// Give each modal that opens a fresh backdrop: a random trianglify image for
// its header, body and footer, never repeating one within the same modal.
const MODAL_BACKDROPS = ['trianglify1.png', 'trianglify2.png', 'trianglify3.png',
                         'trianglify4.png', 'trianglify5.png', 'trianglify6.png',
                         'trianglify7.png', 'trianglify8.png', 'trianglify9.png',
                         'trianglify10.png'];

function pickModalBackdrops(count) {
    const pool = MODAL_BACKDROPS.slice();
    for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
    }
    return pool.slice(0, count);
}

document.addEventListener('show.bs.modal', (event) => {
    const content = event.target.querySelector('.modal-content');
    if (!content) return;
    const [header, body, footer] = pickModalBackdrops(3);
    content.style.setProperty('--modal-header-bg', `url("/static/img/${header}")`);
    content.style.setProperty('--modal-body-bg', `url("/static/img/${body}")`);
    content.style.setProperty('--modal-footer-bg', `url("/static/img/${footer}")`);
});

/* ---- Global loading overlay -------------------------------------------
 * A centred animated GIF covers the page while something is loading: the
 * initial page load, any link navigation, any form submit and every
 * fetch() call. showLoader()/hideLoader() are counted so overlapping
 * requests keep the overlay up until the last one finishes.
 */
let appLoaderPending = 0;

function showLoader() {
    const loader = document.getElementById('app-loader');
    if (!loader) return;
    appLoaderPending += 1;
    loader.classList.add('is-visible');
}

function hideLoader() {
    appLoaderPending = Math.max(0, appLoaderPending - 1);
    if (appLoaderPending > 0) return;
    document.querySelectorAll('#app-loader.is-visible').forEach((loader) => {
        loader.classList.remove('is-visible');
    });
}

function resetLoader() {
    appLoaderPending = 0;
    document.querySelectorAll('#app-loader.is-visible').forEach((loader) => {
        loader.classList.remove('is-visible');
    });
}

// Every fetch keeps the overlay visible until its response arrives.
const nativeFetch = window.fetch.bind(window);
window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.indexOf('/api/health') !== -1) {
        // Background status polling must not flash the overlay.
        return nativeFetch(input, init);
    }
    showLoader();
    return nativeFetch(input, init).finally(() => hideLoader());
};

// Links: show the overlay as soon as the navigation starts.
document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href') || '';
    if (!href || href.charAt(0) === '#' || href.toLowerCase().startsWith('javascript:')) return;
    if (link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    showLoader();
    // A script may cancel the navigation: don't leave the overlay up then.
    setTimeout(() => { if (event.defaultPrevented) hideLoader(); }, 0);
});

// Forms: same treatment for a classic post/reload.
document.addEventListener('submit', (event) => {
    if (event.defaultPrevented) return;
    showLoader();
    setTimeout(() => { if (event.defaultPrevented) hideLoader(); }, 0);
});

// Cover the gap between leaving the page and the next one painting.
window.addEventListener('beforeunload', showLoader);

// The markup starts with the overlay visible for the initial load; clear it
// once the page is fully loaded (or when restored from the back/forward cache).
window.addEventListener('load', () => {
    if (appLoaderPending === 0) resetLoader();
});
window.addEventListener('pageshow', (event) => {
    if (event.persisted) resetLoader();
});

/* ---- Table pagination -------------------------------------------------
 * Every table gets a Bootstrap pagination bar as soon as it holds more
 * than TABLE_PAGE_SIZE rows. Rows are paged client-side, so it works for
 * tables rendered by each page's own script; a MutationObserver re-pages
 * a table whenever its <tbody> is re-rendered (search, delete, reload).
 */
const TABLE_PAGE_SIZE = 10;
const tablePagination = new WeakMap();
const PAGINATION_I18N = window.APP_I18N || {};

function paginationText(key, fallback) {
    return PAGINATION_I18N[key] || fallback;
}

// Compact page list: 1 … 4 5 6 … 12
function paginationPageNumbers(current, pages) {
    if (pages <= 7) {
        const all = [];
        for (let i = 1; i <= pages; i++) all.push(i);
        return all;
    }
    const numbers = [1];
    const start = Math.max(2, current - 2);
    const end = Math.min(pages - 1, current + 2);
    if (start > 2) numbers.push('…');
    for (let i = start; i <= end; i++) numbers.push(i);
    if (end < pages - 1) numbers.push('…');
    numbers.push(pages);
    return numbers;
}

function paginationBar(table) {
    if (table._paginationBar && document.body.contains(table._paginationBar)) {
        return table._paginationBar;
    }
    const bar = document.createElement('div');
    bar.className = 'table-pagination';
    const host = table.closest('.table-responsive') || table;
    host.insertAdjacentElement('afterend', bar);
    table._paginationBar = bar;

    bar.addEventListener('click', (event) => {
        const button = event.target.closest('button[data-page]');
        if (!button || button.closest('.disabled')) return;
        const page = parseInt(button.getAttribute('data-page'), 10);
        const state = tablePagination.get(table);
        if (!state || !page || page === state.page) return;
        state.page = page;
        renderTablePagination(table);
        table.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    });
    return bar;
}

function renderTablePagination(table) {
    const tbody = table.tBodies[0];
    if (!tbody) return;

    const rows = Array.from(tbody.rows);
    const pages = Math.max(1, Math.ceil(rows.length / TABLE_PAGE_SIZE));
    const state = tablePagination.get(table) || { page: 1 };
    state.page = Math.min(Math.max(1, state.page), pages);
    tablePagination.set(table, state);

    rows.forEach((row, index) => {
        row.style.display = Math.floor(index / TABLE_PAGE_SIZE) + 1 === state.page ? '' : 'none';
    });

    const bar = paginationBar(table);
    if (rows.length <= TABLE_PAGE_SIZE) {
        bar.innerHTML = '';
        bar.style.display = 'none';
        return;
    }
    bar.style.display = '';

    const from = (state.page - 1) * TABLE_PAGE_SIZE + 1;
    const to = Math.min(rows.length, state.page * TABLE_PAGE_SIZE);
    const info = paginationText('paginationInfo', 'Showing {start}–{end} of {total}')
        .replace('{start}', from)
        .replace('{end}', to)
        .replace('{total}', rows.length);

    const numberItems = paginationPageNumbers(state.page, pages).map((number) => {
        if (number === '…') {
            return '<li class="page-item disabled"><span class="page-link">…</span></li>';
        }
        return `<li class="page-item ${number === state.page ? 'active' : ''}">` +
            `<button class="page-link" type="button" data-page="${number}"` +
            `${number === state.page ? ' aria-current="page"' : ''}>${number}</button></li>`;
    }).join('');

    bar.innerHTML = `
        <div class="table-pagination-inner">
            <small class="text-muted">${info}</small>
            <nav aria-label="${paginationText('paginationLabel', 'Table pagination')}">
                <ul class="pagination pagination-sm mb-0">
                    <li class="page-item ${state.page === 1 ? 'disabled' : ''}">
                        <button class="page-link" type="button" data-page="${state.page - 1}">
                            ${paginationText('paginationPrev', 'Previous')}
                        </button>
                    </li>
                    ${numberItems}
                    <li class="page-item ${state.page === pages ? 'disabled' : ''}">
                        <button class="page-link" type="button" data-page="${state.page + 1}">
                            ${paginationText('paginationNext', 'Next')}
                        </button>
                    </li>
                </ul>
            </nav>
        </div>`;
}

function paginateAllTables() {
    document.querySelectorAll('table').forEach((table) => {
        if (!table.tBodies.length) return;
        // Tables paged by the server already show one page of rows.
        if (table.hasAttribute('data-server-pagination')) return;
        renderTablePagination(table);
    });
}

let paginationScanQueued = false;

function queuePaginationScan() {
    if (paginationScanQueued) return;
    paginationScanQueued = true;
    setTimeout(() => {
        paginationScanQueued = false;
        paginateAllTables();
    }, 0);
}

// Table bodies are filled in by each page's script, so watch the document and
// re-page on every re-render. The paginator's own DOM is ignored to avoid loops.
const tablePaginationObserver = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        const target = mutation.target.nodeType === 1 ? mutation.target : mutation.target.parentElement;
        if (target && target.closest && target.closest('.table-pagination')) continue;
        queuePaginationScan();
        return;
    }
});

document.addEventListener('DOMContentLoaded', () => {
    paginateAllTables();
    tablePaginationObserver.observe(document.body, { childList: true, subtree: true });
});

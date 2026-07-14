function switchTab(tab) {
    if (!window.HOME_CONFIG.isAdmin) return;
    var isCompras = tab === 'compras';
    document.getElementById('panel-compras').classList.toggle('hidden', !isCompras);
    document.getElementById('panel-ventas').classList.toggle('hidden', isCompras);
    document.getElementById('action-compras').classList.toggle('hidden', !isCompras);
    document.getElementById('action-ventas').classList.toggle('hidden', isCompras);
    var activeClass   = 'flex-1 flex items-center justify-center gap-2 px-6 py-4 text-sm font-semibold transition-all bg-slate-900 text-white';
    var inactiveClass = 'flex-1 flex items-center justify-center gap-2 px-6 py-4 text-sm font-semibold transition-all text-slate-500 hover:bg-slate-50';
    document.getElementById('btn-compras').className = isCompras ? activeClass : inactiveClass;
    document.getElementById('btn-ventas').className  = isCompras ? inactiveClass : activeClass;
}

function toggleCard(btn) {
    var card   = btn.closest('.customer-card');
    var detail = card.querySelector('.card-detail');
    var label  = btn.querySelector('.btn-label');
    var isOpen = !detail.classList.contains('hidden');
    detail.classList.toggle('hidden', isOpen);
    if (label) label.textContent = isOpen ? 'Ver' : 'Ocultar';
    btn.classList.toggle('bg-blue-600', isOpen);
    btn.classList.toggle('bg-slate-600', !isOpen);
}

function togglePaidRows(cb) {
    var detail    = cb.closest('.card-detail');
    var rows      = detail.querySelectorAll('.paid-row');
    var separator = detail.querySelector('.paid-separator');
    var track     = cb.closest('label').querySelector('.toggle-track');
    var thumb     = cb.closest('label').querySelector('.toggle-thumb');
    rows.forEach(function(r) { r.style.display = cb.checked ? '' : 'none'; });
    if (separator) separator.style.display = cb.checked ? '' : 'none';
    if (cb.checked) {
        track.classList.replace('bg-slate-200', 'bg-emerald-500');
        thumb.style.transform = 'translateX(16px)';
    } else {
        track.classList.replace('bg-emerald-500', 'bg-slate-200');
        thumb.style.transform = '';
    }
}

document.addEventListener('DOMContentLoaded', function () {

    // ── Restaurar la pestaña activa según ?tab= de la URL ───────────────────
    // (compras y ventas ahora hacen submit real al servidor con GET, así que
    // sin esto, admin siempre volvería a caer en la pestaña de compras al
    // filtrar o cambiar de página en ventas)
    var params = new URLSearchParams(window.location.search);
    var tab = params.get('tab');
    if (tab === 'ventas' || tab === 'compras') {
        switchTab(tab);
    }

    // ── Buscador de cliente: 100% client-side, alterna tabla <-> tarjetas ──
    var searchInput = document.getElementById('customer-search');
    var tableWrap   = document.getElementById('ventas-table-wrap');
    var cardsWrap   = document.getElementById('ventas-cards-wrap');
    var noResults   = document.getElementById('no-results');

    function applySearch() {
        var query      = searchInput ? searchInput.value.trim().toLowerCase() : '';
        var isSearching = query.length > 0;

        if (tableWrap) tableWrap.style.display = isSearching ? 'none' : '';
        if (cardsWrap) cardsWrap.classList.toggle('hidden', !isSearching);

        if (!isSearching) return;

        var cards   = document.querySelectorAll('.customer-card');
        var visible = 0;
        cards.forEach(function (card) {
            var name     = card.dataset.customer || '';
            var invoices = card.dataset.invoices  || '';
            var match    = name.includes(query) || invoices.includes(query);
            card.style.display = match ? '' : 'none';
            if (match) visible++;
        });
        if (noResults) noResults.style.display = visible === 0 ? 'flex' : 'none';
    }

    if (searchInput) searchInput.addEventListener('input', applySearch);
    applySearch();
});
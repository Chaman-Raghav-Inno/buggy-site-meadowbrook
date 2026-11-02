(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.results = async function () {
    const r = await F.api('/api/results');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your results.', 'error');
    $('#rs-rows').innerHTML = r.data.results.map((x) => {
      const out = x.markers.filter((m) => m.flag === 'Low').length;
      const summary = out ? `<span class="flag flag-out">${F.plural(out, 'value')} outside range</span>` : '<span class="flag flag-ok">All in range</span>';
      return `<tr><td><a href="/result?id=${x.id}">${esc(x.name)}</a>${x.read ? '' : ' <span class="pill pill-new">New</span>'}</td><td>${F.date(x.date)}</td><td>${summary}</td>
        <td><a class="btn btn-small btn-ghost" href="/result?id=${x.id}">View</a></td></tr>`;
    }).join('') || '<tr><td colspan="4" class="muted">No results yet.</td></tr>';
  };
})();

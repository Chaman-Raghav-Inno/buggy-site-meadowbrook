(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.home = async function () {
    const r = await F.api('/api/home');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your home page.', 'error');
    const h = r.data;
    $('#hm-hello').textContent = `Hello, ${h.name}`;
    $('#hm-upcoming').textContent = h.upcoming;
    $('#hm-unread').textContent = h.unread;
    $('#hm-results').textContent = h.new_results;
    $('#hm-owed').textContent = F.gbp(h.owed);
    const a = h.next;
    $('#hm-next').innerHTML = a
      ? `<p class="big-date">${F.longDay(a.date)}</p><p><strong>${esc(a.time)}–${esc(a.end)}</strong> with ${esc(a.doctor_name)} (${esc(a.doctor_role)})</p>
         <p class="muted">${esc(a.reason || 'No reason given')}</p><p><a href="/appointments">Manage your appointments</a></p>`
      : '<p class="muted">Nothing booked.</p><p><a class="btn" href="/book">Book an appointment</a></p>';
  };
})();

(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.doctors = async function () {
    let seq = 0;

    function card(d) {
      const when = d.next ? `${F.day(d.next.slice(0, 10))}, ${d.next.slice(11)}` : 'No free times in the next 28 days';
      return `<article class="card doctor-card"><h2><a href="/doctor?id=${d.id}">${esc(d.name)}</a></h2>
        <p class="muted">${esc(d.role)}</p>
        <ul class="pills">${d.specialties.map((s) => `<li>${esc(s)}</li>`).join('')}</ul>
        <p class="small">Works ${esc(d.days_text)} · ${esc(d.hours[0])}–${esc(d.hours[1])}</p>
        <p class="small">Next available: <strong>${esc(when)}</strong></p>
        <div class="actions"><a class="btn btn-small" href="/book?doctor=${d.id}">Book</a><a class="btn btn-small btn-ghost" href="/doctor?id=${d.id}">Profile</a></div></article>`;
    }

    async function load() {
      const mine = ++seq;
      const q = new URLSearchParams({ q: $('#dr-q').value.trim(), specialty: $('#dr-specialty').value });
      const r = await F.api('/api/doctors?' + q.toString());
      if (mine !== seq) return;
      if (!r.ok) return F.toast(r.data.error || 'Could not load the clinicians.', 'error');
      const list = r.data.doctors;
      $('#dr-count').textContent = F.plural(list.length, 'clinician');
      $('#dr-list').innerHTML = list.map(card).join('') || '<p class="muted">Nobody matches. Try another name or specialty.</p>';
      return r.data;
    }

    let timer;
    $('#dr-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(load, 250); });
    $('#dr-specialty').addEventListener('change', load);
    const d = await load();
    if (d) $('#dr-specialty').innerHTML += d.specialties.map((s) => `<option>${esc(s)}</option>`).join('');
  };
})();

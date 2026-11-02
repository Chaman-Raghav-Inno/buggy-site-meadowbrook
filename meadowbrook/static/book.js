(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.book = async function () {
    let info;
    let picked = null;
    let seq = 0;

    async function loadTimes() {
      const mine = ++seq;
      picked = null;
      const day = $('#bk-date').value;
      if (!day) {
        $('#bk-times').innerHTML = '';
        $('#bk-note').textContent = 'Choose a day to see the free times.';
        return;
      }
      $('#bk-note').textContent = 'Finding free times…';
      const q = new URLSearchParams({ doctor: $('#bk-doctor').value, date: day, length: $('#bk-length').value });
      const r = await F.api('/api/slots?' + q.toString());
      if (mine !== seq) return;
      if (!r.ok) {
        $('#bk-times').innerHTML = '';
        $('#bk-note').textContent = r.data.error || 'Could not load the free times.';
        return;
      }
      $('#bk-times').innerHTML = r.data.times.map((t) => `<button type="button" class="time" data-time="${esc(t)}" aria-pressed="false">${esc(t)}</button>`).join('');
      $('#bk-note').textContent = r.data.note || `${F.plural(r.data.times.length, 'free time')} on ${F.day(day)}.`;
    }

    $('#bk-times').addEventListener('click', (e) => {
      const b = e.target.closest('[data-time]');
      if (!b) return;
      picked = b.dataset.time;
      F.$$('#bk-times .time').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    });
    ['#bk-doctor', '#bk-length', '#bk-date'].forEach((s) => $(s).addEventListener('change', loadTimes));

    $('#bk-form').addEventListener('submit', async () => {
      const msg = $('#bk-msg');
      if (!$('#bk-date').value) return F.say(msg, 'Choose a day.', 'error');
      if (!picked) return F.say(msg, 'Choose a time.', 'error');
      F.say(msg, '');
      const body = {
        doctor: Number($('#bk-doctor').value),
        date: $('#bk-date').value,
        time: picked,
        length: Number($('#bk-length').value),
        for: $('#bk-for').value,
        reason: $('#bk-reason').value.trim(),
      };
      const r = await F.api('/api/appointments', body);
      if (!r.ok) {
        F.say(msg, r.data.error || 'Could not book that time.', 'error');
        return loadTimes();
      }
      const a = r.data.appointment;
      const who = $('#bk-for').selectedOptions[0].textContent;
      $('#bk-done').innerHTML = `<h2>Booked</h2><p><strong>${F.longDay(a.date)}, ${esc(a.time)}–${esc(F.addMinutes(a.time, 15))}</strong></p>
        <p>${esc(a.doctor_name)} (${esc(a.doctor_role)}), for ${esc(who)}.</p><p><a href="/appointments">See your appointments</a></p>`;
      $('#bk-done').hidden = false;
      $('#bk-reason').value = '';
      F.toast('Appointment booked.');
      await loadTimes();
    });

    const r = await F.api('/api/book-info');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the booking page.', 'error');
    info = r.data;
    $('#bk-doctor').innerHTML = info.doctors.map((d) => `<option value="${d.id}">${esc(d.name)} · ${esc(d.role)}</option>`).join('');
    const want = F.params.get('doctor');
    if (want && info.doctors.some((d) => String(d.id) === want)) $('#bk-doctor').value = want;
    $('#bk-for').innerHTML = info.family.map((p, i) => `<option value="${p.id}">${esc(p.name)}${i ? '' : ' (you)'}</option>`).join('');
    $('#bk-closed').innerHTML = info.closures.map((c) => `<li>${F.longDay(c.date)}: ${esc(c.name)}</li>`).join('') || '<li>None in the next 28 days.</li>';
    $('#bk-date').min = info.today;
    $('#bk-date').max = info.until;
    $('#bk-date').value = F.addDays(info.today, 1);
    $('#loading').hidden = true;
    $('#book').hidden = false;
    await loadTimes();
  };
})();

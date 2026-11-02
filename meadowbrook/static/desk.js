(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  function times(start, end) {
    const out = [];
    for (let t = start; F.addMinutes(t, 15) <= end; t = F.addMinutes(t, 15)) {
      if (t < '12:30' || t >= '13:30') out.push(t);
    }
    return out;
  }

  F.pages.desk = async function () {
    let data;
    let doctors = [];
    let seq = 0;

    function draw() {
      $('#dk-date').value = data.day;
      $('#dk-day').textContent = `${F.longDay(data.day)}${data.day === data.today ? ' (today)' : ''}${data.closed ? ` · clinic closed: ${data.closed}` : ''}`;
      const list = data.appointments;
      const count = (s) => list.filter((a) => a.status === s).length;
      $('#dk-counts').innerHTML = [['Booked', count('booked')], ['Arrived', count('arrived')], ['Missed', count('no-show')], ['Cancelled', count('cancelled')]]
        .map(([k, v]) => `<div class="tile"><p class="tile-label">${k}</p><p class="tile-value">${v}</p></div>`).join('');
      $('#dk-rows').innerHTML = list.map((a) => `<tr><td>${esc(a.time)}–${esc(a.end)}</td><td>${esc(a.doctor_name)}</td><td>${esc(a.patient_name)}</td><td>${esc(a.reason)}</td><td>${F.status(a.status)}</td>
          <td>${a.status === 'booked' && a.date <= data.clinic_day ? `<div class="actions"><button type="button" class="btn btn-small" data-checkin="${a.id}">Check in</button><button type="button" class="btn btn-small btn-ghost" data-noshow="${a.id}">Missed</button></div>` : ''}</td></tr>`).join('')
        || '<tr><td colspan="6" class="muted">No appointments on this day.</td></tr>';
      $('#dk-csv').href = `/api/desk/day.csv?date=${data.day}`;
      $('#bl-list').innerHTML = data.blocked.map((b) => `<li><span>${F.day(b.date)} ${esc(b.time)} · ${esc(b.doctor_name)}<br><span class="muted small">${esc(b.reason)}</span></span>
          <button type="button" class="btn btn-small btn-ghost" data-unblock="${b.id}">Unblock</button></li>`).join('') || '<li class="muted">No times blocked.</li>';
    }

    async function load(day) {
      const mine = ++seq;
      const r = await F.api('/api/desk' + (day ? `?date=${encodeURIComponent(day)}` : ''));
      if (mine !== seq) return;
      if (!r.ok) return F.toast(r.data.error || 'Could not load the day list.', 'error');
      data = r.data;
      draw();
    }

    async function act(path, done) {
      const r = await F.api(path, {});
      if (!r.ok) return F.say($('#dk-msg'), r.data.error || 'Could not save that.', 'error');
      data = r.data;
      draw();
      F.say($('#dk-msg'), done, 'success');
    }

    function fillTimes() {
      const d = doctors.find((x) => String(x.id) === $('#bl-doctor').value);
      const hours = d && d.hours ? d.hours : ['08:00', '18:00'];
      $('#bl-time').innerHTML = times(hours[0], hours[1]).map((t) => `<option>${t}</option>`).join('');
    }

    $('#dk-date').addEventListener('change', () => { if ($('#dk-date').value) load($('#dk-date').value); });
    $('#dk-rows').addEventListener('click', (e) => {
      const c = e.target.closest('[data-checkin]');
      if (c) return act(`/api/desk/appointments/${c.dataset.checkin}/checkin`, 'Checked in.');
      const n = e.target.closest('[data-noshow]');
      if (n) return act(`/api/desk/appointments/${n.dataset.noshow}/noshow`, 'Marked as missed.');
    });
    $('#bl-list').addEventListener('click', (e) => {
      const b = e.target.closest('[data-unblock]');
      if (b) act(`/api/desk/block/${b.dataset.unblock}/delete`, 'Unblocked.');
    });
    $('#bl-doctor').addEventListener('change', fillTimes);
    $('#bl-form').addEventListener('submit', async () => {
      const msg = $('#bl-msg');
      const body = { doctor: Number($('#bl-doctor').value), date: $('#bl-date').value, time: $('#bl-time').value, reason: $('#bl-reason').value.trim() };
      if (!body.date) return F.say(msg, 'Choose a day.', 'error');
      const r = await F.api('/api/desk/block', body);
      if (!r.ok) return F.say(msg, r.data.error || 'Could not block that time.', 'error');
      data = r.data;
      draw();
      $('#bl-reason').value = '';
      F.say(msg, `${F.day(body.date)} at ${body.time} is now kept free.`, 'success');
    });
    $('#pt-form').addEventListener('submit', async () => {
      const q = $('#pt-q').value.trim();
      const r = await F.api('/api/desk/patients?q=' + encodeURIComponent(q));
      if (!r.ok) return F.say($('#pt-msg'), r.data.error || 'Could not search.', 'error');
      const list = r.data.patients;
      F.say($('#pt-msg'), F.plural(list.length, 'patient') + ' found.');
      $('#pt-list').innerHTML = list.map((p) => `<article class="patient"><h3>${esc(p.name)}</h3>
          <dl class="facts"><div><dt>Born</dt><dd>${F.date(p.dob)}</dd></div><div><dt>NHS number</dt><dd>${esc(p.nhs.replace(/(\d{3})(\d{3})(\d{4})/, '$1 $2 $3'))}</dd></div>
          <div><dt>Phone</dt><dd>${esc(p.phone)}</dd></div><div><dt>Email</dt><dd>${esc(p.email)}</dd></div></dl>
          <p class="small"><strong>Upcoming:</strong> ${p.upcoming.map((a) => `${F.day(a.date)} ${esc(a.time)} ${esc(a.doctor_name)} (${esc(a.status)})`).join('; ') || 'none'}</p>
          ${p.results.length ? `<p class="small"><strong>Latest results:</strong> ${p.results.map((x) => `${esc(x.name)} (${F.date(x.date)}): ${x.markers.map((m) => `${esc(m.name)} ${m.value} ${esc(m.unit)}${m.flag === 'Normal' ? '' : ' ' + m.flag}`).join(', ')}`).join('; ')}</p>` : ''}</article>`).join('');
    });

    const r = await F.api('/api/desk');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the day list.', 'error');
    data = r.data;
    doctors = data.doctors;
    $('#bl-doctor').innerHTML = doctors.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
    $('#bl-date').min = data.today;
    $('#bl-date').value = F.addDays(data.today, 1);
    fillTimes();
    draw();
  };
})();

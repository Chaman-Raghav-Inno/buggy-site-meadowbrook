(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, $$, esc } = F;

  F.pages.appointments = async function () {
    let data;
    let cancelling = null;
    let moving = null;
    let seq = 0;

    function row(a, actions) {
      const open = actions && a.status === 'booked';
      return `<tr><td>${F.day(a.date)}</td><td>${esc(a.time)}–${esc(a.end)} <span class="muted small">(${a.length} min)</span></td>
        <td>${esc(a.doctor_name)}<br><span class="muted small">${esc(a.doctor_role)}</span></td><td>${esc(a.patient_name)}</td><td>${F.status(a.status)}</td>
        ${actions ? `<td>${open ? `<div class="actions"><button type="button" class="btn btn-small btn-ghost" data-move="${a.id}">Move</button><button type="button" class="btn btn-small btn-ghost" data-cancel="${a.id}">Cancel</button><a class="btn btn-small btn-ghost" href="/api/appointments/${a.id}.ics" download>Add to calendar</a></div>` : ''}</td>` : ''}</tr>`;
    }

    function draw() {
      $('#ap-upcoming').innerHTML = data.upcoming.map((a) => row(a, true)).join('') || '<tr><td colspan="6" class="muted">Nothing booked.</td></tr>';
      $('#ap-past').innerHTML = data.past.map((a) => row(a, false)).join('') || '<tr><td colspan="5" class="muted">No past appointments.</td></tr>';
      $('#ap-owed').hidden = !data.owed;
      $('#ap-owed').textContent = `You have ${F.gbp(data.owed)} in fees to pay at reception.`;
    }

    const find = (id) => data.upcoming.find((a) => String(a.id) === id);

    $('#ap-upcoming').addEventListener('click', (e) => {
      const c = e.target.closest('[data-cancel]');
      if (c) {
        cancelling = find(c.dataset.cancel);
        $('#ap-cancel-text').textContent = `${F.longDay(cancelling.date)} at ${cancelling.time} with ${cancelling.doctor_name}, for ${cancelling.patient_name}.`;
        $('#ap-cancel-fee').textContent = cancelling.date === data.today
          ? 'This appointment is today, so cancelling costs £15 (no fee for children under 16).'
          : 'No fee: you are cancelling before the day of the appointment.';
        $('#ap-cancel').returnValue = '';
        $('#ap-cancel').showModal();
        return;
      }
      const m = e.target.closest('[data-move]');
      if (!m) return;
      moving = find(m.dataset.move);
      $('#ap-move-what').textContent = `Now ${F.day(moving.date)} at ${moving.time} with ${moving.doctor_name} (${moving.length} minutes).`;
      $('#ap-move-date').min = F.addDays(data.today, 1);
      $('#ap-move-date').max = F.addDays(data.today, 28);
      $('#ap-move-date').value = moving.date;
      F.say($('#ap-move-msg'), '');
      $('#ap-move').showModal();
      loadTimes();
    });

    async function loadTimes() {
      const mine = ++seq;
      const sel = $('#ap-move-time');
      sel.innerHTML = '<option value="">Loading…</option>';
      const q = new URLSearchParams({ doctor: moving.doctor, date: $('#ap-move-date').value, length: moving.length, moving: moving.id });
      const r = await F.api('/api/slots?' + q.toString());
      if (mine !== seq) return;
      const times = r.ok ? r.data.times : [];
      sel.innerHTML = times.map((t) => `<option>${esc(t)}</option>`).join('') || '<option value="">No free times</option>';
      F.say($('#ap-move-msg'), r.ok ? r.data.note || '' : r.data.error, r.ok && !r.data.note ? '' : 'error');
    }

    $('#ap-move-date').addEventListener('change', loadTimes);
    $('#ap-move-back').addEventListener('click', () => $('#ap-move').close());
    $('#ap-move-form').addEventListener('submit', async () => {
      const time = $('#ap-move-time').value;
      if (!time) return F.say($('#ap-move-msg'), 'Choose a new time.', 'error');
      const r = await F.api(`/api/appointments/${moving.id}/reschedule`, { date: $('#ap-move-date').value, time });
      if (!r.ok) return F.say($('#ap-move-msg'), r.data.error || 'Could not move the appointment.', 'error');
      data = r.data;
      draw();
      $('#ap-move').close();
      F.say($('#ap-msg'), `Moved to ${F.longDay(r.data.moved.date)} at ${r.data.moved.time}.`, 'success');
    });

    $$('#ap-cancel button').forEach((b) => b.addEventListener('click', () => $('#ap-cancel').close(b.dataset.value)));
    $('#ap-cancel').addEventListener('close', async () => {
      if ($('#ap-cancel').returnValue !== 'cancel' || !cancelling) return;
      const r = await F.api(`/api/appointments/${cancelling.id}/cancel`, {});
      if (!r.ok) return F.say($('#ap-msg'), r.data.error || 'Could not cancel the appointment.', 'error');
      data = r.data;
      draw();
      F.say($('#ap-msg'), r.data.fee ? `Cancelled. A late-cancellation fee of ${F.gbp(r.data.fee)} has been added to your account.` : 'Cancelled. There is no fee.', 'success');
    });

    const r = await F.api('/api/appointments');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your appointments.', 'error');
    data = r.data;
    draw();
  };
})();

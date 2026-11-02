(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.prescriptions = async function () {
    let data;

    function draw() {
      $('#rx-meds').innerHTML = data.medicines.map((m) => `<li><strong>${esc(m.name)}</strong><span class="muted small">${esc(m.dose)} · up to ${m.max} ${esc(m.unit)} per request</span>
          <span class="small">Last ordered ${F.date(m.last)} · next order from ${F.date(F.addDays(m.last, 30))}</span>
          ${m.overdue ? `<span class="notice small">Medication review overdue since ${F.date(m.review)}. Book a review before ordering.</span>` : `<span class="muted small">Review due ${F.date(m.review)}</span>`}</li>`).join('');
      const keep = $('#rx-medicine').value;
      $('#rx-medicine').innerHTML = '<option value="">Choose a medicine</option>' + data.medicines.map((m) => `<option value="${m.id}">${esc(m.name)}</option>`).join('');
      $('#rx-medicine').value = keep;
      $('#rx-history').innerHTML = data.requests.map((r) => `<tr><td>${esc(r.name)}</td><td class="num">${r.quantity}</td><td>${F.day(r.requested)}</td>
          <td>${F.day(r.ready)}</td><td>${esc(r.pharmacy)}</td><td>${F.status(r.status)}</td></tr>`).join('')
        || '<tr><td colspan="6" class="muted">No requests yet.</td></tr>';
      showMax();
    }

    function showMax() {
      const m = data.medicines.find((x) => String(x.id) === $('#rx-medicine').value);
      $('#rx-max').textContent = m ? `Up to ${m.max} ${m.unit}.` : '';
    }

    $('#rx-medicine').addEventListener('change', showMax);
    $('#rx-form').addEventListener('submit', async () => {
      const msg = $('#rx-msg');
      const medicine = Number($('#rx-medicine').value);
      const quantity = Number($('#rx-qty').value);
      if (!medicine) return F.say(msg, 'Choose a medicine.', 'error');
      if (!Number.isInteger(quantity) || quantity < 1) return F.say(msg, 'Enter how many you need.', 'error');
      const pharmacy = $('#rx-pharmacy').value;
      const r = await F.api('/api/prescriptions', { medicine, quantity, pharmacy });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not send the request.', 'error');
      data = r.data;
      draw();
      $('#rx-qty').value = '';
      F.say(msg, `Requested ${quantity} × ${r.data.request.name}. Ready to collect from ${F.longDay(r.data.request.ready)} at ${pharmacy}.`, 'success');
    });

    const r = await F.api('/api/prescriptions');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your prescriptions.', 'error');
    data = r.data;
    $('#rx-pharmacy').innerHTML = data.pharmacies.map((p) => `<option>${esc(p)}</option>`).join('');
    $('#rx-pharmacy').value = data.pharmacy;
    draw();
  };
})();

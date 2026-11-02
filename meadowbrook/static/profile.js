(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.profile = async function () {
    function draw(p) {
      $('#pf-name').value = p.name;
      $('#pf-dob').value = p.dob;
      $('#pf-nhs').value = p.nhs.replace(/(\d{3})(\d{3})(\d{4})/, '$1 $2 $3');
      $('#pf-phone').value = p.phone;
      $('#pf-email').value = p.email;
      $('#pf-owed').textContent = F.gbp(p.owed);
      $('#pf-fees').innerHTML = p.fees.map((f) => `<li>${F.date(f.date)} · ${esc(f.description)} · ${F.gbp(f.amount)}</li>`).join('') || '<li class="muted">No fees.</li>';
    }

    $('#pf-form').addEventListener('submit', async () => {
      const msg = $('#pf-msg');
      const body = { dob: $('#pf-dob').value, nhs: $('#pf-nhs').value.replace(/\s/g, ''), phone: $('#pf-phone').value.trim(), email: $('#pf-email').value.trim() };
      if (!body.dob) return F.say(msg, 'Enter your date of birth.', 'error');
      const r = await F.api('/api/profile', body);
      if (!r.ok) return F.say(msg, r.data.error || 'Could not save your details.', 'error');
      draw(r.data);
      F.say(msg, 'Your details are saved.', 'success');
    });

    const r = await F.api('/api/profile');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your details.', 'error');
    draw(r.data);
  };
})();

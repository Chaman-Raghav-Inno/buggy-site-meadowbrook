(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.family = async function () {
    let data;

    function draw() {
      $('#fm-list').innerHTML = data.children.map((c) => `<li><div class="section-head"><strong>${esc(c.name)}</strong><span class="muted small">Age ${c.age}</span></div>
          <p class="muted small">Born ${F.date(c.dob)} · NHS ${esc(c.nhs.replace(/(\d{3})(\d{3})(\d{4})/, '$1 $2 $3'))}</p>
          <p class="small">${c.upcoming.length ? 'Next: ' + c.upcoming.map((a) => `${F.day(a.date)} ${esc(a.time)} with ${esc(a.doctor_name)}`).join('; ') : 'No appointments booked.'}</p>
          <p class="small"><a href="/book">Book for ${esc(c.name.split(' ')[0])}</a></p></li>`).join('')
        || '<li class="muted">No children added yet.</li>';
    }

    $('#fm-form').addEventListener('submit', async () => {
      const msg = $('#fm-msg');
      const name = $('#fm-name').value.trim();
      const dob = $('#fm-dob').value;
      const nhs = $('#fm-nhs').value.replace(/\s/g, '');
      if (!name) return F.say(msg, 'Enter the child\'s full name.', 'error');
      if (!dob) return F.say(msg, 'Enter the child\'s date of birth.', 'error');
      if (!/^\d{10}$/.test(nhs)) return F.say(msg, 'Enter the 10-digit NHS number.', 'error');
      const r = await F.api('/api/family', { name, dob, nhs });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not add the child.', 'error');
      data = r.data;
      draw();
      $('#fm-form').reset();
      F.say(msg, `${name} added. You can now book appointments for them.`, 'success');
    });

    const r = await F.api('/api/family');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your family.', 'error');
    data = r.data;
    $('#fm-dob').max = data.today;
    draw();
  };
})();

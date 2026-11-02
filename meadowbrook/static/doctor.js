(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;
  const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  F.pages.doctor = async function () {
    const id = Number(F.params.get('id'));
    const r = await F.api(`/api/doctors/${id}`);
    const d = r.data.doctor;
    document.title = `${d.name} · Meadowbrook Clinic`;
    $('#dc-name').textContent = d.name;
    $('#dc-role').textContent = d.role;
    $('#dc-specialties').innerHTML = d.specialties.map((s) => `<li>${esc(s)}</li>`).join('');
    $('#dc-bio').textContent = d.bio;
    $('#dc-book').href = `/book?doctor=${d.id}`;
    $('#dc-next').textContent = d.next ? `${F.day(d.next.slice(0, 10))}, ${d.next.slice(11)}` : 'nothing in the next 28 days';
    $('#dc-week').innerHTML = d.weekdays.map((n) => `<div><dt>${DAYS[n]}</dt><dd>${esc(d.hours[0])}–${esc(d.hours[1])}</dd></div>`).join('');
    if (d.leave) {
      $('#dc-leave').textContent = `${d.name} is on leave until ${F.longDay(d.leave.until)}.`;
      $('#dc-leave').hidden = false;
    }
    $('#loading').hidden = true;
    $('#doctor').hidden = false;
  };
})();

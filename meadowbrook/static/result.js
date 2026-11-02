(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  function range(m) {
    if (m.low == null) return `up to ${m.high}`;
    if (m.high == null) return `${m.low} or more`;
    return `${m.low}–${m.high}`;
  }

  function trend(m) {
    if (m.previous == null) return '<span class="muted">First test</span>';
    if (m.value === m.previous) return `No change from ${m.previous}`;
    return m.value < m.previous ? `Up from ${m.previous}` : `Down from ${m.previous}`;
  }

  F.pages.result = async function () {
    const id = Number(F.params.get('id'));
    const r = await F.api(`/api/results/${id}`);
    if (!r.ok) {
      $('#loading').textContent = r.data.error || 'Could not load that result.';
      return;
    }
    const x = r.data.result;
    document.title = `${x.name} · Meadowbrook Clinic`;
    $('#rr-name').textContent = x.name;
    $('#rr-meta').textContent = `${x.patient_name} · NHS ${x.patient_nhs.replace(/(\d{3})(\d{3})(\d{4})/, '$1 $2 $3')} · taken ${F.date(x.date)} by ${x.by}`;
    $('#rr-rows').innerHTML = x.markers.map((m) => `<tr><td>${esc(m.name)}</td><td class="num"><strong>${m.value}</strong> ${esc(m.unit)}</td><td>${range(m)} ${esc(m.unit)}</td>
        <td><span class="flag ${m.flag === 'Normal' ? 'flag-ok' : 'flag-out'}">${m.flag === 'Normal' ? 'In range' : m.flag}</span></td><td>${trend(m)}</td></tr>`).join('');
    $('#rr-comment').textContent = x.comment;
    $('#loading').hidden = true;
    $('#result').hidden = false;
    if (!x.read) F.api(`/api/results/${id}/read`, {});
  };
})();

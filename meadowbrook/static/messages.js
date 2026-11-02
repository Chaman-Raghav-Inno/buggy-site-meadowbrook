(function () {
  'use strict';

  const F = window.Meadowbrook;
  const { $, esc } = F;

  F.pages.messages = async function () {
    let data;
    let open = null;

    function draw() {
      $('#ms-list').innerHTML = data.threads.map((t) => `<li><button type="button" class="thread-link${t.id === open ? ' current' : ''}" data-thread="${t.id}">
          <strong>${esc(t.subject)}</strong>${t.unread ? ' <span class="pill pill-new">New reply</span>' : ''}<span class="muted small">${esc(t.topic)} · ${F.date(t.updated)}</span></button></li>`).join('')
        || '<li class="muted">No messages yet.</li>';
      const t = data.threads.find((x) => x.id === open);
      $('#ms-thread').hidden = !t;
      if (t) {
        $('#ms-thread').innerHTML = `<h3>${esc(t.subject)}</h3>` + t.messages.map((m) => `<div class="bubble ${m.from}"><p class="muted small">${esc(m.name)} · ${F.date(m.date)}</p><p>${esc(m.text)}</p></div>`).join('');
      }
    }

    $('#ms-list').addEventListener('click', async (e) => {
      const b = e.target.closest('[data-thread]');
      if (!b) return;
      open = Number(b.dataset.thread);
      draw();
      const r = await F.api(`/api/messages/${open}/read`, {});
      if (r.ok) {
        const badge = $('#nav-unread');
        if (badge) {
          badge.textContent = r.data.unread;
          badge.hidden = !r.data.unread;
        }
      }
    });
    $('#ms-text').addEventListener('input', (e) => { $('#ms-count').textContent = `${e.target.value.length} / 1000`; });
    $('#ms-form').addEventListener('submit', async () => {
      const msg = $('#ms-msg');
      const topic = $('#ms-topic').value;
      const subject = $('#ms-subject').value.trim();
      const message = $('#ms-text').value;
      if (!topic) return F.say(msg, 'Choose a topic.', 'error');
      if (!subject) return F.say(msg, 'Add a subject.', 'error');
      if (!message) return F.say(msg, 'Write your message.', 'error');
      const r = await F.api('/api/messages', { topic, subject, message });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not send your message.', 'error');
      data = r.data;
      open = r.data.sent;
      draw();
      $('#ms-form').reset();
      $('#ms-count').textContent = '0 / 1000';
      F.say(msg, 'Sent. We reply within 2 working days.', 'success');
    });

    const r = await F.api('/api/messages');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your messages.', 'error');
    data = r.data;
    $('#ms-topic').innerHTML = '<option value="">Choose a topic</option>' + data.topics.map((t) => `<option>${esc(t)}</option>`).join('');
    draw();
  };
})();

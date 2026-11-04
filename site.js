/* Site-wide behaviour that every page shares: the WhatsApp button, the
   Tawk.to live chat, whole-card clicking and the booking form. The scripted desk assistant
   this replaces is in git history (chat.js). */
(() => {
  const WA = '919811788643';

  /* ── WhatsApp button, with the question already started ────────────────── */
  const fab = document.createElement('a');
  fab.className = 'wa-fab';
  fab.href = 'https://wa.me/' + WA + '?text=' +
    encodeURIComponent('Hi Showmaqers, I have a question about an event.');
  fab.target = '_blank';
  fab.rel = 'noopener';
  fab.setAttribute('aria-label', 'Chat with us on WhatsApp');
  fab.innerHTML =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.46 1.32 4.96L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22c5.46 0 9.91-4.45 9.91-9.91C21.96 6.45 17.5 2 12.04 2zm0 18.15c-1.56 0-3.09-.42-4.43-1.21l-.32-.19-3.3.87.88-3.22-.21-.33a8.23 8.23 0 0 1-1.26-4.39c0-4.54 3.7-8.23 8.25-8.23 2.2 0 4.27.86 5.83 2.42a8.19 8.19 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.25 8.23z"/><path d="M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.95 1.17-.17.2-.35.22-.65.07-.3-.15-1.13-.42-2.15-1.33-.8-.71-1.33-1.59-1.49-1.89-.15-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.02-.52-.07-.15-.67-1.61-.92-2.2-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.8.37-.27.3-1.04 1.02-1.04 2.48 0 1.46 1.07 2.87 1.22 3.07.15.2 2.1 3.33 5.1 4.54 2.99 1.21 2.99.81 3.53.76.54-.05 1.76-.72 2-1.42.25-.7.25-1.29.17-1.42-.07-.12-.27-.2-.57-.35z"/></svg>' +
    '<b>Chat on WhatsApp</b>';
  document.body.appendChild(fab);
  setTimeout(() => fab.classList.add('on'), 1400);   // let the page settle first

  /* ── Tawk.to live chat ─────────────────────────────────────────────────── */
  window.Tawk_API = window.Tawk_API || {};
  window.Tawk_LoadStart = new Date();
  const s = document.createElement('script');
  s.async = true;
  s.src = 'https://embed.tawk.to/5e591894298c395d1cea4c14/default';
  s.charset = 'UTF-8';
  s.setAttribute('crossorigin', '*');
  document.head.appendChild(s);

  /* ── the whole card is the link, not just the "Click here" button ───────
     Delegated rather than per-card so it also catches cards rendered later;
     the real link still carries the href, so keyboard and SEO are unchanged. */
  document.addEventListener('click', (e) => {
    if (e.target.closest('a, button, input, select, textarea, label, video')) return;
    const card = e.target.closest('.svc-card, .card');
    const link = card && card.querySelector('a[href]');
    if (link) link.click();
  });

  /* ── booking form → WhatsApp (no backend to keep alive) ───────────────────
     One form for every booking: the homepage's contact form, and the dialog
     that Hire, Book, Plan my event and Send an enquiry open. Those links keep
     their hrefs, so they still lead somewhere if this script does not run. */
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 10);
  const talk = (to) => `Opens WhatsApp with your details filled in. Prefer to talk? Call +91 ${to.slice(2, 7)} ${to.slice(7)}.`;
  const bookingFields = (id) => {
    const field = (name, label, control) => `<div class="field"><label for="${id}-${name}">${label}</label>` +
      control(`id="${id}-${name}" name="${name}" required`) + '</div>';
    const input = (attrs) => (a) => `<input ${a} ${attrs}>`;
    const pick = (options) => (a) => `<select ${a}><option value="">Choose one</option>` +
      options.map(o => `<option>${o}</option>`).join('') + '</select>';
    const words = 'pattern=".*\\S.*"';    // required alone accepts a line of spaces
    return field('name', 'Your name', input(`${words} autocomplete="name"`)) +
      '<div class="row2">' +
        field('type', 'Event type', pick(['Social', 'Corporate', 'Wedding', 'Birthday / anniversary',
          'Brand promotion / road show', 'College / school fest', 'Other'])) +
        field('date', 'Event date', input(`type="date" min="${today}"`)) +
      '</div><div class="row2">' +
        field('timings', 'Timings', input(`${words} placeholder="7 pm to 11 pm"`)) +
        field('duration', 'Duration of performance / service', pick(['Up to 1 hour', '2 hours', '3 to 4 hours',
          '5 to 6 hours', 'Full day', 'More than one day'])) +
      '</div>' +
      field('location', 'Location', input(`${words} placeholder="Venue or area, city" autocomplete="off"`)) +
      '<div class="row2">' +
        field('phone', 'Phone', input('type="tel" pattern="\\+?[0-9 \\-]{10,16}" title="Phone number with at least 10 digits" placeholder="98xxxxxxxx" autocomplete="tel"')) +
        field('email', 'Email', input('type="email" placeholder="you@example.com" autocomplete="email"')) +
      '</div>' +
      '<button class="btn btn--hot" type="submit">Send enquiry</button>' +
      `<small>${talk(WA)}</small>`;
  };

  const sendToWhatsApp = (form, booking) => form.addEventListener('submit', (e) => {
    e.preventDefault();
    const f = new FormData(form), { item, to } = booking();
    const text = [
      'Hi SHOWMAQERS! I would like to book.',
      item && `For: ${item}`,
      `Name: ${f.get('name').trim()}`,
      `Event type: ${f.get('type')}`,
      `Date: ${new Date(f.get('date') + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`,
      `Timings: ${f.get('timings').trim()}`,
      `Duration: ${f.get('duration')}`,
      `Location: ${f.get('location').trim()}`,
      `Phone: ${f.get('phone').trim()}`,
      `Email: ${f.get('email').trim()}`,
      `Page: ${document.title}`            // "For: BASIC" alone does not say basic what
    ].filter(Boolean).join('\n');
    window.open('https://wa.me/' + to + '?text=' + encodeURIComponent(text), '_blank', 'noopener');
    const note = form.querySelector('small');
    note.textContent = 'WhatsApp should have opened with your enquiry. Press send there and we will reply shortly.';
    note.style.color = 'var(--gold)';
  });

  const enq = document.getElementById('enq');
  if (enq) {
    enq.insertAdjacentHTML('afterbegin', bookingFields('enq'));
    sendToWhatsApp(enq, () => ({ item: '', to: WA }));
  }

  const dialog = document.createElement('dialog');
  dialog.className = 'booking';
  dialog.setAttribute('aria-labelledby', 'booking-title');
  dialog.innerHTML = '<button type="button" class="booking-x" aria-label="Close">✕</button>' +
    '<form class="glass"><h2 id="booking-title">Send an enquiry</h2><p class="booking-for" hidden></p>' +
    bookingFields('booking') + '</form>';
  document.body.appendChild(dialog);
  dialog.querySelector('.booking-x').addEventListener('click', () => dialog.close());
  const dialogFor = dialog.querySelector('.booking-for'), dialogNote = dialog.querySelector('small');
  let booking = { item: '', to: WA };
  sendToWhatsApp(dialog.querySelector('form'), () => booking);

  /* What is being booked: the link can say, else the card it sits on, else the
     page's heading, but only on a page whose heading names a service. */
  const servicePage = () => /"@type":"Service"/.test(document.querySelector('script[type="application/ld+json"]')?.textContent || '');
  const bookingItem = (a) => a.dataset.book
    || a.closest('.svc-card')?.querySelector('b')?.textContent.replace(/^\d+\.\s*/, '').trim()
    || (servicePage() && document.querySelector('h1')?.textContent.trim()) || '';

  document.addEventListener('click', (e) => {
    const a = e.target.closest('a.btn:not([href^="tel:"])');
    if (!a || !(/^(hire|book)\b/i.test(a.textContent.trim())
             || /(contact\.html|index\.html#contact)$/.test(a.getAttribute('href')))) return;
    e.preventDefault();
    booking = { item: bookingItem(a), to: a.dataset.wa || a.href.match(/wa\.me\/(\d+)/)?.[1] || WA };
    dialogFor.textContent = booking.item && 'For: ' + booking.item;
    dialogFor.hidden = !booking.item;
    dialogNote.textContent = talk(booking.to);
    dialogNote.style.color = '';
    dialog.showModal();
  });
})();

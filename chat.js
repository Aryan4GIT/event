/* Showmaqers desk assistant.
   Scripted, not an LLM: a static site cannot hold an API key, and the dozen
   questions people ask before enquiring are always the same dozen. Anything it
   does not recognise goes to WhatsApp with the question already typed in. */
(() => {
  const WA = '919811788643', TEL = '+91 98117 88643';
  const wa = (t) => 'https://wa.me/' + WA + '?text=' + encodeURIComponent(t);

  const REPLIES = [
    { k: ['hi', 'hello', 'hey', 'namaste', 'good morning', 'good evening'],
      a: 'Hello! I can tell you about our services, cities, artists and how booking works. What are you planning?' },

    { k: ['service', 'what do you do', 'offer', 'provide', 'help with'],
      a: 'Three desks under one roof:<br>• <b>Weddings &amp; celebrations</b> — destination weddings, ceremonies, birthdays, anniversaries<br>• <b>Corporate</b> — product launches, conferences, annual awards, road shows, BTL<br>• <b>Manpower &amp; artists</b> — anchors, DJs, singers, dance troupes, promoters, bouncers<br>Plus décor, flowers, stage fabrication and F&amp;B. <a href="index.html#services">See services</a>' },

    { k: ['wedding', 'shaadi', 'marriage', 'mandap', 'sangeet', 'haldi', 'destination'],
      a: 'Weddings are our main floor — décor, flower work, mandap and stage fabrication, artists, F&amp;B and the full guest journey, in Delhi NCR or at a destination. One certified planner stays with you from the first call to the final encore. <a href="index.html#contact">Tell us the date</a>' },

    { k: ['corporate', 'company', 'conference', 'product launch', 'seminar', 'award', 'brand', 'exhibition', 'road show'],
      a: 'Corporate work covers brand promotions, product launches, meetings and conferences, seminars and annual awards, road shows, BTL activity, exhibitions and consumer shows. <a href="index.html#contact">Send us the brief</a>' },

    { k: ['register', 'join', 'sign up', 'apply', 'work with you', 'i am an artist', 'audition', 'hire me', 'showreel'],
      a: 'Artists register free — no joining fee. Fill the form with your details, a clear photo and a short clip of your skill, and we call you within a few working days. <a href="vendors.html#register">Register as an artist</a>' },

    { k: ['artist', 'anchor', 'emcee', 'dj', 'singer', 'dancer', 'performer', 'celebrity', 'comedian', 'manpower', 'promoter', 'hostess', 'bouncer', 'roster', 'model'],
      a: 'We keep a vetted roster of 100+ artists — anchors and emcees, DJs, singers, dance troupes, stand-up comedians, TV and film celebrities, promoters, hostesses, models, bouncers and event staff. <a href="manpower.html">Browse the roster</a>' },

    { k: ['price', 'cost', 'budget', 'rate', 'charge', 'quote', 'package', 'fee', 'how much'],
      a: 'There is no fixed package — the quote depends on guest count, venue, dates and what you want built. Share those four and we come back with an itemised quote, usually the same day. <a href="index.html#contact">Get a quote</a> or call ' + TEL + '.' },

    { k: ['city', 'cities', 'where', 'location', 'area', 'delhi', 'noida', 'gurgaon', 'gurugram', 'faridabad', 'ghaziabad', 'jaipur', 'udaipur', 'agra', 'outstation', 'pan india'],
      a: 'Based in Chattarpur, New Delhi, working across all of Delhi NCR — Noida, Greater Noida, Gurugram, Faridabad, Ghaziabad, Meerut, Sonipat and more — and we travel pan India for destination events including Jaipur, Udaipur, Jodhpur, Jaisalmer and Agra. <a href="index.html#cities">See the full list</a>' },

    { k: ['contact', 'call', 'phone', 'number', 'email', 'whatsapp', 'reach', 'talk to', 'office', 'address'],
      a: 'Call <a href="tel:+919811788643">+91 98117 88643</a> or <a href="tel:+919910772449">+91 99107 72449</a>, email <a href="mailto:info@showmaqers.com">info@showmaqers.com</a>, or <a href="' + wa('Hi Showmaqers, I have a question about an event.') + '" target="_blank" rel="noopener">message us on WhatsApp</a>.<br>Office: 160, Dhappa Colony, Raipur Khurd, Chattarpur, New Delhi 110068.' },

    { k: ['how long', 'notice', 'advance', 'lead time', 'available', 'availability', 'date', 'book', 'booking', 'last minute', 'tomorrow'],
      a: 'Big weddings are best booked 2–3 months out, corporate events 3–4 weeks, and a single artist can often be arranged in a few days. Peak wedding season fills early — send us the date and we will tell you straight away if it is open. <a href="index.html#contact">Check a date</a>' },

    { k: ['gallery', 'photos', 'work', 'past event', 'portfolio', 'previous', 'experience', 'years'],
      a: 'Twelve years on the floor: 100+ weddings, 500+ parties, 1000+ promotions. <a href="index.html#gallery">See nights we built</a>' },

    { k: ['thanks', 'thank you', 'thankyou', 'bye'],
      a: 'Any time. When you are ready, <a href="index.html#contact">tell us the date</a> and we will take the floor.' }
  ];

  const CHIPS = [
    ['What do you do?', 'services'],
    ['Pricing', 'how much does it cost'],
    ['Artists', 'artist roster'],
    ['Cities', 'which cities'],
    ['Register as artist', 'i want to register as an artist'],
    ['Contact', 'contact']
  ];

  const fab = document.createElement('button');
  fab.className = 'chat-fab';
  fab.type = 'button';
  fab.setAttribute('aria-expanded', 'false');
  fab.setAttribute('aria-label', 'Chat with Showmaqers');
  fab.innerHTML =
    '<svg class="b" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3C6.9 3 3 6.6 3 11c0 2.3 1.1 4.3 2.9 5.7L5 21l4.5-2.2c.8.2 1.6.3 2.5.3 5.1 0 9-3.6 9-8s-3.9-8-9-8z"/></svg>'
  + '<svg class="x" viewBox="0 0 24 24" aria-hidden="true"><path d="M18.3 5.7 12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7 2.9 18.3 9.2 12 2.9 5.7l1.4-1.4L10.6 10.6l6.3-6.3z"/></svg>';

  const panel = document.createElement('div');
  panel.className = 'chat-panel';
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', 'Showmaqers assistant');
  panel.innerHTML =
    '<div class="chat-head"><span class="dot"></span><span><b>Showmaqers desk</b><small>Usually answers instantly</small></span></div>'
  + '<div class="chat-log" role="log" aria-live="polite"></div>'
  + '<div class="chat-chips">'
  + CHIPS.map(c => '<button type="button" data-q="' + c[1] + '">' + c[0] + '</button>').join('')
  + '</div>'
  + '<form class="chat-form" autocomplete="off">'
  + '<input type="text" aria-label="Your question" placeholder="Ask about dates, décor, artists…" required>'
  + '<button type="submit" aria-label="Send"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 21 23 12 2 3v7l15 2-15 2z"/></svg></button>'
  + '</form>';

  document.body.append(fab, panel);
  const log = panel.querySelector('.chat-log'), input = panel.querySelector('input');

  const add = (html, who) => {
    const p = document.createElement('p');
    p.className = who;
    p.innerHTML = html;
    log.append(p);
    log.scrollTop = log.scrollHeight;
    return p;
  };

  /* Whole words only, with an optional plural: otherwise "fireworks" matches
     the keyword "work", and "anchors" matches nothing. Order matters — the
     first rule that fits wins, so the narrower ones are listed first. */
  for (const r of REPLIES) {
    r.re = new RegExp('\\b(' + r.k.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')s?\\b', 'i');
  }

  const answer = (q) => {
    const hit = REPLIES.find(r => r.re.test(q));
    if (hit) return hit.a;
    return 'I am not sure about that one — our team can answer it properly. '
      + '<a href="' + wa('Hi Showmaqers, ' + q) + '" target="_blank" rel="noopener">Ask on WhatsApp</a>'
      + ' or call <a href="tel:+919811788643">' + TEL + '</a>.';
  };

  /* the visitor's own words go back on screen as text, never as markup */
  const ask = (q) => {
    const mine = add('', 'me');
    mine.textContent = q;
    const wait = add('…', 'bot');
    setTimeout(() => { wait.innerHTML = answer(q); log.scrollTop = log.scrollHeight; }, 420);
  };

  let greeted = false;
  const toggle = (open) => {
    panel.classList.toggle('on', open);
    fab.setAttribute('aria-expanded', String(open));
    if (open && !greeted) {
      greeted = true;
      add('Hi! I am the Showmaqers desk assistant. Ask me about services, cities, artists or getting a quote — or pick one below.', 'bot');
    }
    if (open) input.focus();
  };

  fab.addEventListener('click', () => toggle(!panel.classList.contains('on')));
  panel.querySelector('.chat-chips').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (b) ask(b.dataset.q);
  });
  panel.querySelector('.chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    ask(q);
  });
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panel.classList.contains('on')) { toggle(false); fab.focus(); }
  });
})();

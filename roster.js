/* The live artist roster, shared by manpower.html and every artist page.

   Any page that wants artists drops in a container and loads three scripts:

     <div class="people" data-people="dj"></div>
     <script src="supabase-config.js"></script>
     <script src="artists-data.js"></script>
     <script src="roster.js" defer></script>

   artists-data.js paints instantly and is what search engines read. If
   Supabase is configured and answers, the approved roster replaces it — so an
   artist approved in admin.html appears here without anyone editing a file.

   Was inline in manpower.html; moved here so the per-category pages show the
   same cards from the same source rather than a second copy of it. */
(() => {
  let DATA = window.ARTISTS || {};
  const isVideoPath = p => /\.(mp4|webm|mov)(\?|$)/i.test(p || '');

  /* where a category's own page cannot name the role from a heading */
  const label = {
    dj: 'DJ', anchors: 'Emcee / Anchor', singers: 'Singer', dancers: 'Dancer',
    choreographer: 'Choreographer', sfx: 'SFX Artist', photographer: 'Photographer',
    videographer: 'Videographer', 'game-coordinator': 'Game Coordinator',
    'russian-promoters': 'Promoter', tarot: 'Tarot Card Reader', pottery: 'Pottery Maker',
    puppet: 'Puppet Show Performer', magician: 'Magician', 'stilt-walker': 'Stilt Walker',
    joker: 'Joker / Clown', juggler: 'Juggler', mascots: 'Mascot Artist',
    mehendi: 'Mehendi Artist', 'makeup-artist': 'Make-up Artist', tattoo: 'Tattoo Artist',
    'face-painter': 'Face Painter', 'nail-artist': 'Nail Artist', parlour: 'Parlour Beautician'
  };

  const boxes = document.querySelectorAll('[data-people]');
  const showBtn = document.querySelector('[data-show]');
  const showBox = showBtn && document.querySelector(`[data-people="${showBtn.dataset.show}"]`);
  const faces = document.getElementById('facesTrack');

  function render() {
    boxes.forEach(box => {
      const kind = box.dataset.people, list = DATA[kind] || [];
      const role = label[kind] || box.closest('.cat')?.querySelector('h2')?.textContent.trim() || '';
      /* An approved artist with no photo rendered <img src="null"> — a broken
         tile on the public roster. Leave them out until a photo exists. */
      const shown = list.filter(p => p.i);
      box.innerHTML = shown.map(p => {
        const facts = [p.l, p.d, p.e].filter(Boolean).join(' · ');   // fee stays off the public card
        /* the gallery the lightbox walks: headshot, then every work sample */
        const gallery = [p.i, ...(p.m || []), ...(p.s ? [p.s] : [])];
        const hasVideo = gallery.some(isVideoPath);
        return `<figure class="person" data-src="${p.i}" data-cap="${p.n}"` +
        ` data-gallery="${encodeURIComponent(JSON.stringify(gallery))}"` +
        (p.id ? ` data-id="${p.id}"` : '') +
        (p.s ? ` data-clip="${p.s}"` : '') + '>' +
        (hasVideo ? '<span class="reel">▶ Reel</span>' : '') +
        `<img src="${p.i}" alt="${p.n}" loading="lazy">` +
        `<figcaption>${p.n}<b>${role}</b>${facts ? `<small>${facts}</small>` : ''}</figcaption></figure>`;
      }).join('');
      box.style.marginBottom = shown.length ? '1.1rem' : '0';
      /* An artist page says "our DJs" above the grid. With nobody approved in
         that category yet the heading would sit over nothing, so the page can
         wrap the whole block and have it disappear until someone is listed. */
      const section = box.closest('[data-roster]');
      if (section) section.hidden = !shown.length;
    });

    document.querySelectorAll('[data-count-for]').forEach(el => {
      const n = (DATA[el.dataset.countFor] || []).length;
      el.textContent = n + (n === 1 ? ' artist' : ' artists');
    });

    if (showBtn) {
      const total = (DATA[showBtn.dataset.show] || []).length;
      showBtn.hidden = total <= 24;
      if (showBox.classList.contains('clipped')) showBtn.textContent = `Show all ${total} anchors`;
    }

    if (faces) {
      const pick = [...(DATA.dj || []).slice(0, 4), ...(DATA.singers || []).slice(0, 3),
                    ...(DATA.anchors || []).slice(0, 9)];
      faces.innerHTML = pick.map(p =>
        `<figure><img src="${p.i}" alt="${p.n}" loading="lazy"></figure>`).join('').repeat(2);
    }
  }
  if (boxes.length) render();

  if (showBtn) showBtn.addEventListener('click', () => {
    const total = (DATA[showBtn.dataset.show] || []).length;
    const clipped = showBox.classList.toggle('clipped');
    showBtn.textContent = clipped ? `Show all ${total} anchors` : 'Show fewer';
    if (clipped) showBox.scrollIntoView({ block: 'start' });
  });

  (async () => {                                   // live roster, when connected
    if (!boxes.length) return;                     // nothing on this page wants it
    const cfg = window.SUPABASE;
    if (!cfg || /YOUR-/.test(cfg.url + cfg.anonKey)) return;
    try {
      const h = { headers: { apikey: cfg.anonKey, Authorization: 'Bearer ' + cfg.anonKey } };
      const read = cols => fetch(`${cfg.url}/rest/v1/roster?select=${cols}&order=sort.asc`, h);
      /* Each column arrives with its own migration, so ask for the richest
         set and fall back rather than losing the live roster:
         media -> media-gallery.sql, skill_path -> skill-media.sql */
      let r = await read('id,name,category_key,photo_path,skill_path,media,city,sort');
      if (!r.ok) r = await read('id,name,category_key,photo_path,skill_path,city,sort');
      if (!r.ok) r = await read('name,category_key,photo_path,city,sort');
      if (!r.ok) return;
      const rows = await r.json();
      if (!Array.isArray(rows) || !rows.length) return;   // never blank the page
      const live = {}, snap = window.ARTISTS || {};
      for (const row of rows) {
        const seen = (live[row.category_key] ||= []);
        /* duration and event type are staff-only, so the roster view does not
           carry them — take them from the snapshot, which is in the same
           sort order this query asks for */
        const was = (snap[row.category_key] || [])[seen.length] || {};
        seen.push({ n: row.name, i: row.photo_path, s: row.skill_path || null,
                    m: row.media || null, id: row.id,
                    l: row.city || was.l, d: was.d, e: was.e });
      }
      DATA = live;
      render();
    } catch (e) { /* offline or project paused — the snapshot stays up */ }
  })();

  /* ── lightbox over every photo on the page ───────────────────────────────
     The cards are cursor:zoom-in, so they have to open something. Also picks
     up the .strip galleries these pages already carry. */
  const lb = document.createElement('div');
  lb.className = 'lb'; lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true');
  lb.innerHTML = `<button class="lb-btn lb-close" aria-label="Close">✕</button>
    <button class="lb-btn lb-prev" aria-label="Previous">‹</button>
    <button class="lb-btn lb-next" aria-label="Next">›</button>
    <figure><img alt=""><video controls playsinline hidden></video><figcaption></figcaption></figure>`;
  document.body.appendChild(lb);
  const lbImg = lb.querySelector('img'), lbVid = lb.querySelector('video'), lbCap = lb.querySelector('figcaption');
  let shots = [], at = 0, opener = null;

  const show = (i) => {
    at = (i + shots.length) % shots.length;
    const shot = shots[at], clip = shot.clip, isVid = clip && /\.(mp4|webm|mov)(\?|$)/i.test(clip);
    lbVid.pause();
    lbVid.hidden = !isVid; lbImg.hidden = !!isVid;
    if (isVid) { lbVid.src = clip; lbVid.play().catch(() => {}); }
    else { lbVid.removeAttribute('src'); lbImg.src = clip || shot.src; }
    lbImg.alt = shot.cap;
    const where = shots.length > 1 ? ` <span class="lb-of">${at + 1} of ${shots.length}</span>` : '';
    lbCap.innerHTML = (shot.cap ? shot.cap.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c])) : '')
      + where
      + (shot.href ? ` <a class="lb-link" href="${shot.href}">Full profile &rarr;</a>` : '');
  };
  const close = () => { lb.classList.remove('on'); lbVid.pause(); opener?.focus?.(); };

  document.addEventListener('click', (e) => {
    const fig = e.target.closest('.person, .strip figure:not(.noimg)');
    if (!fig || e.target.closest('.lb')) return;

    /* a roster card steps through that artist's own photos and clip; a strip
       figure still steps through the strip it sits in */
    if (fig.dataset.gallery) {
      const cap = fig.dataset.cap || '';
      const href = fig.dataset.id ? 'artist.html?id=' + fig.dataset.id : null;
      shots = JSON.parse(decodeURIComponent(fig.dataset.gallery))
        .filter(Boolean)
        .map(src => ({ src, clip: isVideoPath(src) ? src : null, cap, href }));
      if (shots.length) {
        opener = fig;
        show(0);
        lb.classList.add('on');
        lb.querySelector('.lb-close').focus();
        return;
      }
    }

    const group = fig.closest('.people, .strip');
    shots = [...group.querySelectorAll('figure:not(.noimg)')].map(f => ({
      src: f.dataset.src || f.querySelector('img').getAttribute('src'),
      clip: f.dataset.clip || null,
      cap: f.dataset.cap || f.querySelector('figcaption')?.textContent.trim() || ''
    }));
    opener = fig;
    show([...group.querySelectorAll('figure:not(.noimg)')].indexOf(fig));
    lb.classList.add('on');
    lb.querySelector('.lb-close').focus();
  });
  lb.addEventListener('click', e => {
    if (e.target.closest('.lb-next')) show(at + 1);
    else if (e.target.closest('.lb-prev')) show(at - 1);
    else if (!e.target.closest('figure') || e.target.closest('.lb-close')) close();
  });
  addEventListener('keydown', e => {
    if (!lb.classList.contains('on')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight') show(at + 1);
    if (e.key === 'ArrowLeft') show(at - 1);
  });
})();

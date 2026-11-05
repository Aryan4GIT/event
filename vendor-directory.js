/* The public vendor list, and the rules its profile page shares with it.

   Reads the `supplier` view: approved vendors only, with no phone and no email.
   A vendor appears here the moment staff approve them in admin.html. */
window.VendorDirectory = (() => {
  const PAGE = 'event-vendors-suppliers-delhi-ncr.html';
  /* where a clip's thumbnail is taken from: a phone shows nothing until a video
     is told to seek, and clips made before the fix open on an empty frame */
  const FRAME = '#t=0.5';
  const isVideo = p => /\.(mp4|webm|mov)(\?|$)/i.test(p || '');
  const esc = s => String(s ?? '').replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));

  /* A vendor's bio opens with "Contact: <person>", which is for our team.
     Clients reach everyone through Showmaqers, so that line and any number,
     email or web address typed into the description stay off the page. Eight
     digits is the same line looks_like_a_phone() draws in the database. */
  const cleanBio = text => String(text || '')
    .replace(/^Contact:[^\n]*\n*/, '')
    .replace(/\+?[0-9][0-9 ().+-]{5,}[0-9]/g, m => (m.replace(/\D/g, '').length >= 8 ? '' : m))
    .replace(/[\w.+-]+@[\w-]+\.[\w.-]+/g, '')
    .replace(/\b(?:https?:\/\/|www\.)\S+|\b[\w-]+\.(?:com|in|net|org|co)\b\S*/gi, '')
    .replace(/^[^\n]*\b(?:instagram|facebook|website|whatsapp|call|contact|phone|mobile|e-?mail)\b[^\n\w]*$/gim, '')   // the label left behind
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  const samplesOf = row => [...(row.media || []), ...(row.skill_path ? [row.skill_path] : [])].filter(Boolean);

  /* The picture on a card. A vendor registers without a headshot, so their
     first work photo stands in, then their clip. */
  const coverOf = row => {
    const all = samplesOf(row);
    return { photo: row.photo_path || all.find(p => !isVideo(p)) || null, clip: all.find(isVideo) || null };
  };

  /* One section per category. A vendor who ticked several appears in each;
     `roles` reaches the view with vendor-directory.sql, and until then the
     primary category still places them. */
  function group(rows, categories) {
    const order = categories.map(c => c.key), label = {}, by = {};
    categories.forEach(c => { label[c.key] = c.label; });
    for (const row of rows) {
      for (const key of new Set(row.roles?.length ? row.roles : [row.category_key])) (by[key] ||= []).push(row);
    }
    return Object.keys(by)
      .sort((a, b) => order.indexOf(a) - order.indexOf(b))
      .map(key => ({ key, label: label[key] || key, vendors: by[key] }));
  }

  function card(row, role) {
    const { photo, clip } = coverOf(row);
    const name = esc(row.name);
    const face = photo ? `<img src="${esc(photo)}" alt="${name}" loading="lazy">`
      : clip ? `<video src="${esc(clip)}${FRAME}" muted playsinline preload="metadata"></video>`
      : `<span class="person-blank" aria-hidden="true">${esc(String(row.name || '?').trim().charAt(0).toUpperCase())}</span>`;
    return `<figure class="person"><a class="person-go" href="artist.html?id=${esc(row.id)}" aria-label="${name} profile"></a>`
      + (clip ? '<span class="reel">▶ Reel</span>' : '')
      + face
      + `<figcaption>${name}<b>${esc(role)}</b>${row.city ? `<small>${esc(row.city)}</small>` : ''}</figcaption></figure>`;
  }

  async function render() {
    const list = document.getElementById('v-list'), state = document.getElementById('v-state');
    const chips = document.getElementById('v-chips'), cfg = window.SUPABASE;
    try {
      if (!cfg || /YOUR-/.test(cfg.url)) throw new Error('not connected');
      const h = { headers: { apikey: cfg.anonKey, Authorization: 'Bearer ' + cfg.anonKey } };
      const read = async path => {
        const r = await fetch(`${cfg.url}/rest/v1/${path}`, h);
        if (!r.ok) throw new Error(path + ' ' + r.status);
        return r.json();
      };
      const [rows, categories] = await Promise.all([
        read('supplier?select=*&order=sort.asc'),
        read('categories?select=key,label,sort&order=sort.asc')
      ]);
      const sections = group(rows, categories);
      if (!sections.length) { state.textContent = 'Our first verified vendors are being added now.'; return; }
      chips.innerHTML = sections.map(s => `<a href="#cat-${esc(s.key)}">${esc(s.label)} (${s.vendors.length})</a>`).join('');
      list.innerHTML = sections.map(s => `
        <section class="vendor-cat" id="cat-${esc(s.key)}">
          <h2>${esc(s.label)}</h2>
          <div class="people">${s.vendors.map(v => card(v, s.label)).join('')}</div>
        </section>`).join('');
      state.remove();
    } catch (e) {
      console.warn('[vendors] could not load:', e.message);
      state.textContent = 'We could not load the vendors just now. Please try again in a moment.';
    }
  }

  if (typeof document !== 'undefined' && document.getElementById('v-list')) render();

  return { PAGE, FRAME, cleanBio, coverOf, samplesOf, group, isVideo, esc };
})();

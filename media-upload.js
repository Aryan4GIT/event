/* Work-sample picker and compressor, shared by the artist and vendor forms.

   Two photos and one video of at most 10 seconds. Everything is re-encoded in
   the browser before it is uploaded, because a phone shoots 4K: a raw 10s clip
   is 15-25 MB and the same clip at 720p is a little over 1 MB. Compressing
   here rather than on a server means no server, and the artist on mobile data
   uploads the small file, not the big one.

   Usage:
     const picker = MediaPicker.mount({ input, drop, list, say });
     const paths  = await picker.upload(putFn);   // [] when nothing was added

   putFn(name, blob) must store the blob and resolve truthy on success; the
   caller owns the bucket and the folder. */
window.MediaPicker = (() => {
  const MAX_PHOTOS = 2;
  const MAX_VIDEOS = 1;
  const MAX_SECONDS = 10;
  const PHOTO_EDGE = 1600;          // long edge after downscaling
  const VIDEO_EDGE = 720;
  const VIDEO_BITRATE = 1200000;    // ~1.2 Mbps — fine for a 720p work sample
  const RAW_LIMIT = 200 * 1024 * 1024;   // refuse to even decode a 200 MB file
  const OUT_LIMIT = 30 * 1024 * 1024;    // the bucket's cap, after vendor-directory.sql
  const KEEP_ORIGINAL = 12 * 1024 * 1024;   // fits the bucket whether or not that has run

  const esc = s => String(s).replace(/[<>&"]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[c]));

  /* Browsers often leave file.type empty (a HEIC on Windows, a clip from some
     Android galleries), and then only the name can say what it is. Anything
     that is an image or a video is welcome: it gets converted before upload. */
  const PHOTO_NAME = /\.(jpe?g|png|webp|heic|heif|avif|gif|bmp)$/i;
  const VIDEO_NAME = /\.(mp4|m4v|mov|webm|3gpp?|mkv|avi)$/i;
  function kindOf(file) {
    const type = file.type === 'application/octet-stream' ? '' : file.type;
    if (type) return type.startsWith('image/') ? 'photo' : type.startsWith('video/') ? 'video' : null;
    return PHOTO_NAME.test(file.name) ? 'photo' : VIDEO_NAME.test(file.name) ? 'video' : null;
  }

  const isVideoPath = p => /\.(mp4|webm|mov)(\?|$)/i.test(p);

  /* What the storage bucket will actually take. An iPhone HEIC is not on this
     list, so it has to be converted whatever its size. */
  const STORABLE = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' };

  /* ── photos: downscale, then WebP, which is ~30% smaller than JPEG for the
     same apparent quality. Older browsers get JPEG. ─────────────────────── */
  /* createImageBitmap is missing on older iPhones and refuses some formats the
     <img> route can still read */
  async function openImage(file) {
    try { if (window.createImageBitmap) return await createImageBitmap(file); } catch (e) { /* try the <img> */ }
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      return img;
    } finally { URL.revokeObjectURL(url); }
  }

  async function readable(file) {
    try { (await openImage(file)).close?.(); return true; } catch (e) { return false; }
  }

  const cannotOpen = file => /hei[cf]/i.test(file.type + file.name)
    ? `${file.name} is an iPhone HEIC photo, which this browser cannot open. Share it from your phone as a JPG, or take a screenshot of it.`
    : `${file.name} could not be opened as a photo. Please try a JPG or PNG.`;

  async function squashImage(file) {
    const bmp = await openImage(file);
    const scale = Math.min(1, PHOTO_EDGE / Math.max(bmp.width, bmp.height));
    const c = document.createElement('canvas');
    c.width = Math.round(bmp.width * scale);
    c.height = Math.round(bmp.height * scale);
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    bmp.close?.();

    const webp = await new Promise(r => c.toBlob(r, 'image/webp', 0.82));
    const jpg  = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.85));
    const best = webp && jpg ? (webp.size <= jpg.size ? { blob: webp, ext: 'webp' }
                                                      : { blob: jpg,  ext: 'jpg'  })
               : webp ? { blob: webp, ext: 'webp' }
               : jpg  ? { blob: jpg,  ext: 'jpg'  }
               : null;

    /* Size alone must not decide this. HEIC is efficient enough that our
       re-encode is often the larger file, and keeping the original then sent
       the bucket a mime type it refuses — which is how an iPhone photo was
       silently dropped while the video beside it went through. */
    const asIs = STORABLE[file.type];
    if (asIs && (!best || best.blob.size >= file.size)) return { blob: file, ext: asIs };
    if (best) return best;
    if (asIs) return { blob: file, ext: asIs };
    throw new Error('that photo is in a format this browser cannot convert');
  }

  /* ── video: play it, draw each frame to a 720p canvas, record the canvas.
     Real time, so a 10s clip takes about 10s. That is the price of having no
     server; it is why the cap is 10 seconds. ───────────────────────────── */
  function recorderType() {
    if (typeof MediaRecorder === 'undefined') return null;
    return ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus',
            'video/webm', 'video/mp4'].find(t => MediaRecorder.isTypeSupported(t)) || null;
  }

  /* The bucket knows three video types, and a phone's .m4v or .3gp is the same
     container as an mp4. Anything else could not be played back later anyway. */
  function originalClip(file) {
    const kind = (file.type + ' ' + file.name).toLowerCase();
    const as = /webm/.test(kind) ? ['video/webm', 'webm']
      : /quicktime|\.mov/.test(kind) ? ['video/quicktime', 'mov']
      : /mp4|m4v|3gp/.test(kind) ? ['video/mp4', 'mp4'] : null;
    return as && { blob: file.slice(0, file.size, as[0]), ext: as[1] };
  }

  async function squashVideo(file, onProgress) {
    const type = recorderType();
    if (!type) throw Object.assign(new Error('no recorder'), { soft: true });
    /* Safari cannot capture a video's sound, so converting there leaves a silent
       clip. Keep the original when the bucket will take it. */
    const keepsSound = 'captureStream' in HTMLMediaElement.prototype || 'mozCaptureStream' in HTMLMediaElement.prototype;
    if (!keepsSound && file.size <= KEEP_ORIGINAL) throw new Error('converting here would lose the sound');

    const v = document.createElement('video');
    v.muted = true; v.playsInline = true; v.preload = 'auto';
    v.src = URL.createObjectURL(file);
    try {
      await new Promise((res, rej) => {
        v.onloadedmetadata = res;
        v.onerror = () => rej(new Error('that video could not be read'));
        setTimeout(() => rej(new Error('that video took too long to open')), 20000);
      });

      const seconds = Math.min(v.duration || MAX_SECONDS, MAX_SECONDS);
      const scale = Math.min(1, VIDEO_EDGE / Math.max(v.videoWidth, v.videoHeight));
      const c = document.createElement('canvas');
      /* even dimensions — some encoders reject odd ones */
      c.width = Math.round(v.videoWidth * scale / 2) * 2;
      c.height = Math.round(v.videoHeight * scale / 2) * 2;
      const ctx = c.getContext('2d');

      const stream = c.captureStream(30);
      /* keep the sound: a DJ's clip without audio is pointless. Video-only if
         the browser will not hand over the track. */
      try {
        const src = v.captureStream ? v.captureStream() : v.mozCaptureStream?.();
        const audio = src?.getAudioTracks?.()[0];
        if (audio) stream.addTrack(audio);
      } catch (e) { /* video only */ }

      const chunks = [];
      const rec = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: VIDEO_BITRATE });
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      const done = new Promise(r => { rec.onstop = r; });

      await v.play();
      /* draw before recording, or the clip opens on an empty canvas and its
         thumbnail looks as if nothing uploaded */
      ctx.drawImage(v, 0, 0, c.width, c.height);
      rec.start(250);

      /* setInterval, not requestAnimationFrame: a background tab pauses rAF
         outright and the conversion would hang for ever. The watchdog covers
         a clip that stalls mid-decode. */
      await new Promise((stop, fail) => {
        const started = Date.now();
        const timer = setInterval(() => {
          if (v.ended || v.currentTime >= seconds) { clearInterval(timer); return stop(); }
          if (Date.now() - started > (seconds + 25) * 1000) {
            clearInterval(timer);
            return fail(new Error('converting that video stalled'));
          }
          ctx.drawImage(v, 0, 0, c.width, c.height);
          onProgress?.(Math.min(1, v.currentTime / seconds));
        }, 1000 / 30);
      });

      v.pause();
      rec.stop();
      await done;
      stream.getTracks().forEach(t => t.stop());

      const ext = type.startsWith('video/mp4') ? 'mp4' : 'webm';
      const blob = new Blob(chunks, { type: type.split(';')[0] });
      if (!blob.size) throw new Error('that video could not be converted');
      return { blob, ext, seconds };
    } finally {
      URL.revokeObjectURL(v.src);
    }
  }

  function mount({ input, drop, list, say }) {
    const picked = [];          // { file, kind, url }
    const failures = [];        // { name, why } from the last upload, for the caller to show

    const count = kind => picked.filter(p => p.kind === kind).length;

    function paint() {
      list.innerHTML = picked.map((p, i) => `
        <figure class="ms-item">
          ${p.kind === 'video'
            ? `<video src="${p.url}#t=0.1" muted playsinline preload="metadata"></video><span class="ms-tag">Video</span>`
            : `<img src="${p.url}" alt="">`}
          <button type="button" class="ms-x" data-i="${i}" aria-label="Remove">✕</button>
        </figure>`).join('');
      drop.classList.toggle('has', picked.length > 0);
      const room = [];
      if (count('photo') < MAX_PHOTOS) room.push(`${MAX_PHOTOS - count('photo')} more photo${MAX_PHOTOS - count('photo') > 1 ? 's' : ''}`);
      if (count('video') < MAX_VIDEOS) room.push('a video up to 10 seconds');
      drop.querySelector('.ms-msg').textContent = room.length
        ? 'Add ' + room.join(' and ') + ' of your work'
        : 'That is the lot — remove one to swap it';
    }

    async function take(files) {
      say('');
      for (const file of [...files]) {
        const kind = kindOf(file);
        if (!kind) { say(`${esc(file.name)} is not a photo or a video, so it was not added.`, 'err'); continue; }
        if (file.size > RAW_LIMIT) { say('That file is enormous — please pick a smaller one.', 'err'); continue; }
        if (kind === 'photo' && count('photo') >= MAX_PHOTOS) { say(`Two photos is the limit — remove one to swap it.`, 'err'); continue; }
        if (kind === 'video' && count('video') >= MAX_VIDEOS) { say('One video is the limit — remove it to swap it.', 'err'); continue; }
        /* find out now, while they can still pick another, not after they press send */
        if (kind === 'photo' && !await readable(file)) { say(esc(cannotOpen(file)), 'err'); continue; }
        picked.push({ file, kind, url: URL.createObjectURL(file) });
      }
      paint();
    }

    input.addEventListener('change', e => { take(e.target.files); input.value = ''; });
    drop.addEventListener('dragover', e => { e.preventDefault(); drop.classList.add('over'); });
    drop.addEventListener('dragleave', () => drop.classList.remove('over'));
    drop.addEventListener('drop', e => { e.preventDefault(); drop.classList.remove('over'); take(e.dataTransfer.files); });
    list.addEventListener('click', e => {
      const x = e.target.closest('.ms-x');
      if (!x) return;
      URL.revokeObjectURL(picked[+x.dataset.i].url);
      picked.splice(+x.dataset.i, 1);
      paint();
    });
    paint();

    /* Compress then store, in the order they were added. A sample that will
       not convert is skipped rather than losing the whole registration, and
       goes in failures so the caller can say so: a message here would only be
       overwritten by the caller's next line, which is how files used to vanish. */
    async function upload(put) {
      const paths = [];
      failures.length = 0;
      for (let i = 0; i < picked.length; i++) {
        const p = picked[i];
        const n = `${i + 1} of ${picked.length}`;
        try {
          let out;
          if (p.kind === 'photo') {
            say(`Shrinking photo ${n}…`);
            out = await squashImage(p.file);
          } else {
            say(`Converting your video (${n}) — this takes about ten seconds…`);
            try {
              out = await squashVideo(p.file, frac =>
                say(`Converting your video — ${Math.round(frac * 100)}%…`));
            } catch (err) {
              /* cannot re-encode here. Send the original when it already fits
                 rather than losing the clip; only give up when it is too big. */
              out = originalClip(p.file);
              if (!out) throw new Error('this phone cannot convert that video format. Please choose an MP4');
              if (p.file.size > OUT_LIMIT) throw new Error(
                `it is ${Math.round(p.file.size / 1048576)} MB and could not be shrunk on this device. Please trim it to about ${MAX_SECONDS} seconds`);
              console.warn('[media] sent the original clip unconverted:', err.message);
            }
          }
          if (out.blob.size > OUT_LIMIT) throw new Error('it is still too large after converting');
          /* put returns where it stored the file when it knows, so a caller
             that adds a folder or a timestamp does not have to reconstruct a
             path and get it wrong. A plain truthy answer means the name was
             used as given. */
          const name = `m${i}.${out.ext}`;
          const stored = await put(name, out.blob);
          if (!stored) throw new Error('our storage refused it');
          paths.push(typeof stored === 'string' ? stored : name);
        } catch (err) {
          console.warn('[media] skipped a sample:', err.message);
          failures.push({ name: p.file.name, why: err.message });
        }
      }
      return paths;
    }

    /* forget the selection once it is stored, or the next save sends it again */
    function clear() {
      picked.splice(0).forEach(p => URL.revokeObjectURL(p.url));
      paint();
    }

    return { upload, clear, failures, get length() { return picked.length; } };
  }

  /* why storage said no, in words someone can act on */
  async function refusal(res) {
    const body = await res.json().catch(() => ({}));
    const code = String(body.statusCode || res.status);
    if (code === '413') return 'it is too large for our storage';
    if (code === '415') return 'our storage does not accept that file type';
    return body.message || 'our storage refused it (' + res.status + ')';
  }

  const failureList = failures => failures.map(f => `${esc(f.name)}: ${esc(f.why)}.`).join('<br>');

  /* For someone whose details arrived but whose file did not. */
  const lostNote = (failures, waNumber, who) =>
    `<p class="status err" style="margin-top:1.2rem; color:var(--lav)">These files did not upload:<br>${failureList(failures)}<br>`
    + `<a href="https://wa.me/${waNumber}?text=${encodeURIComponent('Hi Showmaqers, I registered as ' + who + '. Here are the files that would not upload.')}" `
    + 'target="_blank" rel="noopener" style="font-weight:600">Send them to us on WhatsApp</a> and we will add them.</p>';

  return { mount, kindOf, originalClip, openImage, readable, cannotOpen, refusal, failureList, lostNote, esc,
           isVideoPath, MAX_PHOTOS, MAX_VIDEOS, MAX_SECONDS };
})();

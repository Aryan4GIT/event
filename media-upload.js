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
  const OUT_LIMIT = 12 * 1024 * 1024;    // the bucket's own cap

  const IMAGE = /^image\/(jpeg|png|webp)$/;
  const VIDEO = /^video\/(mp4|webm|quicktime)$/;

  const isVideoPath = p => /\.(mp4|webm|mov)(\?|$)/i.test(p);

  /* ── photos: downscale, then WebP, which is ~30% smaller than JPEG for the
     same apparent quality. Older browsers get JPEG. ─────────────────────── */
  async function squashImage(file) {
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, PHOTO_EDGE / Math.max(bmp.width, bmp.height));
    const c = document.createElement('canvas');
    c.width = Math.round(bmp.width * scale);
    c.height = Math.round(bmp.height * scale);
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    bmp.close?.();
    const webp = await new Promise(r => c.toBlob(r, 'image/webp', 0.82));
    if (webp && webp.size < file.size) return { blob: webp, ext: 'webp' };
    const jpg = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.85));
    if (jpg && jpg.size < file.size) return { blob: jpg, ext: 'jpg' };
    return { blob: file, ext: (file.type === 'image/png' ? 'png' : 'jpg') };   // already small
  }

  /* ── video: play it, draw each frame to a 720p canvas, record the canvas.
     Real time, so a 10s clip takes about 10s. That is the price of having no
     server; it is why the cap is 10 seconds. ───────────────────────────── */
  function recorderType() {
    if (typeof MediaRecorder === 'undefined') return null;
    return ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus',
            'video/webm', 'video/mp4'].find(t => MediaRecorder.isTypeSupported(t)) || null;
  }

  async function squashVideo(file, onProgress) {
    const type = recorderType();
    if (!type) throw Object.assign(new Error('no recorder'), { soft: true });

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

    const count = kind => picked.filter(p => p.kind === kind).length;

    function paint() {
      list.innerHTML = picked.map((p, i) => `
        <figure class="ms-item">
          ${p.kind === 'video'
            ? `<video src="${p.url}" muted playsinline preload="metadata"></video><span class="ms-tag">Video</span>`
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

    function take(files) {
      for (const file of [...files]) {
        const kind = IMAGE.test(file.type) ? 'photo' : VIDEO.test(file.type) ? 'video' : null;
        if (!kind) { say('Photos must be JPG, PNG or WebP, and video MP4, WebM or MOV.', 'err'); continue; }
        if (file.size > RAW_LIMIT) { say('That file is enormous — please pick a smaller one.', 'err'); continue; }
        if (kind === 'photo' && count('photo') >= MAX_PHOTOS) { say(`Two photos is the limit — remove one to swap it.`, 'err'); continue; }
        if (kind === 'video' && count('video') >= MAX_VIDEOS) { say('One video is the limit — remove it to swap it.', 'err'); continue; }
        picked.push({ file, kind, url: URL.createObjectURL(file) });
        say('');
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
       not convert is skipped with a warning rather than losing the whole
       registration — the photo and the details still matter more. */
    async function upload(put) {
      const paths = [];
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
            out = await squashVideo(p.file, frac =>
              say(`Converting your video — ${Math.round(frac * 100)}%…`));
          }
          if (out.blob.size > OUT_LIMIT) throw new Error('still too large after converting');
          const name = `m${i}.${out.ext}`;
          if (await put(name, out.blob)) paths.push(name);
          else throw new Error('upload refused');
        } catch (err) {
          console.warn('[media] skipped a sample:', err.message);
          say(`We could not process ${p.kind} ${n}, so it was left out. Everything else was sent.`, 'err');
        }
      }
      return paths;
    }

    return { upload, get length() { return picked.length; } };
  }

  return { mount, isVideoPath, MAX_PHOTOS, MAX_VIDEOS, MAX_SECONDS };
})();

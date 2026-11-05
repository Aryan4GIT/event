#!/usr/bin/env node
/* Checks the rules behind uploads and the vendor pages. No browser and no network.
   Run from the repo root:  node tools/test-upload-and-vendor-rules.js */
const assert = require('assert'), fs = require('fs'), vm = require('vm');

const load = (file, name) => {
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), sandbox);
  return sandbox.window[name];
};
const { kindOf, originalClip } = load('media-upload.js', 'MediaPicker');
const { cleanBio, coverOf, group } = load('vendor-directory.js', 'VendorDirectory');
const file = (name, type) => ({ name, type, size: 10, slice: (a, b, t) => ({ type: t }) });

/* What a phone or a PC hands the picker */
assert.strictEqual(kindOf(file('a.jpg', 'image/jpeg')), 'photo');
assert.strictEqual(kindOf(file('a.heic', '')), 'photo', 'Windows reports no type for a HEIC');
assert.strictEqual(kindOf(file('a.gif', 'image/gif')), 'photo', 'any image is converted');
assert.strictEqual(kindOf(file('a.mov', 'video/quicktime')), 'video');
assert.strictEqual(kindOf(file('a.m4v', 'video/x-m4v')), 'video');
assert.strictEqual(kindOf(file('a.3gp', 'video/3gpp')), 'video');
assert.strictEqual(kindOf(file('a.mp4', '')), 'video', 'some galleries report no type');
assert.strictEqual(kindOf(file('a.mp4', 'application/octet-stream')), 'video');
assert.strictEqual(kindOf(file('a.pdf', 'application/pdf')), null);
assert.strictEqual(kindOf(file('notes', '')), null);

/* The bucket knows three video types, so an unconverted clip must be labelled as one */
assert.strictEqual(originalClip(file('a.m4v', 'video/x-m4v')).blob.type, 'video/mp4');
assert.strictEqual(originalClip(file('a.3gp', 'video/3gpp')).ext, 'mp4');
assert.strictEqual(originalClip(file('a.mov', '')).blob.type, 'video/quicktime');
assert.strictEqual(originalClip(file('a.webm', 'video/webm')).ext, 'webm');
assert.strictEqual(originalClip(file('a.mkv', 'video/x-matroska')), null, 'nothing a browser could play later');

/* Clients reach a vendor through Showmaqers */
assert.strictEqual(cleanBio('Contact: Asha Rao\n\nGerman hangars up to 10,000 sq ft.'), 'German hangars up to 10,000 sq ft.');
assert.strictEqual(cleanBio('Call 98117 88643 now'), 'Call  now');
assert.strictEqual(cleanBio('Bands.\nCall +91 98117-88643'), 'Bands.', 'the label goes with the number');
assert.strictEqual(cleanBio('Live music\n\nInstagram: instagram.com/band\nWebsite: www.band.com\n\nBook now'), 'Live music\n\nBook now');
assert.strictEqual(cleanBio('We call it magic and it shows'), 'We call it magic and it shows', 'ordinary words stay');
assert.strictEqual(cleanBio('Write to a.b@mail.co.in today'), 'Write to  today');
assert.strictEqual(cleanBio('300 guests, 12 staff'), '300 guests, 12 staff', 'short numbers stay');
assert.strictEqual(cleanBio(null), '');

/* The card's picture */
assert.strictEqual(coverOf({ photo_path: 'p.jpg', media: ['m.webp'] }).photo, 'p.jpg');
assert.strictEqual(coverOf({ media: ['c.webm', 'm.webp'] }).photo, 'm.webp', 'a work photo stands in for a headshot');
assert.strictEqual(coverOf({ media: ['c.webm'] }).clip, 'c.webm');
assert.strictEqual(coverOf({ media: null }).photo, null);

/* A vendor sits under every category they ticked, in the site's category order */
const categories = [{ key: 'v-decor', label: 'Decor' }, { key: 'v-florist', label: 'Florist' }, { key: 'sfx', label: 'SFX' }];
const sections = group([
  { name: 'Both', category_key: 'v-florist', roles: ['v-florist', 'v-decor'] },
  { name: 'Old view', category_key: 'sfx' }
], categories);
assert.deepStrictEqual(Array.from(sections, s => s.key), ['v-decor', 'v-florist', 'sfx']);
assert.strictEqual(sections[0].vendors[0].name, 'Both');
assert.strictEqual(sections[1].vendors[0].name, 'Both');
assert.strictEqual(sections[2].vendors[0].name, 'Old view', 'works before vendor-directory.sql runs');

console.log('all upload and vendor rules hold');

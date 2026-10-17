/* Bath Solution Studio — browser app (no build step). */
(function () {
'use strict';
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const uid = () => Math.random().toString(36).slice(2, 9);
const today = () => new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
const store = { get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
const S = { me: null, meta: null, catalog: null, E: null, project: null, range: store.get('bss.range'), cat: { q: '', brand: '', series: '', category: '' }, review: null, users: null, catalogs: null, poll: null };

/* ---------- helpers ---------- */
let toastT;
function toast(m) { const t = $('#toast'); t.textContent = m; t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, 3500); }
async function api(method, url, body, isForm) {
  const opt = { method, credentials: 'same-origin', headers: {} };
  if (body !== undefined) { if (isForm) opt.body = body; else { opt.body = JSON.stringify(body); opt.headers['Content-Type'] = 'application/json'; } }
  const r = await fetch(url, opt);
  if (r.status === 401 && !url.startsWith('/api/login')) { S.me = null; showLogin(); throw new Error('Please sign in.'); }
  const ct = r.headers.get('content-type') || '';
  const data = ct.includes('json') ? await r.json() : null;
  if (!r.ok) throw new Error((data && data.error) || `Request failed (${r.status})`);
  return data;
}
const swc = k => '#' + ((S.meta && (S.meta.finishes.find(f => f.key === k) || {}).color) || DeckBuilder.SW[k] || '9AA3A8');
const money = (n, cur) => DeckBuilder.fmt(n, cur || 'EUR');
const curOf = brand => ((S.catalog && S.catalog.brands.find(b => b.name === brand)) || {}).currency || 'EUR';
const isAdmin = () => S.me && S.me.role === 'admin';
function download(name, blob) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
}
async function dataUrls(urls) {
  const out = {};
  await Promise.all([...new Set(urls.filter(Boolean))].map(async u => {
    try { const b = await (await fetch(u, { credentials: 'same-origin' })).blob(); out[u] = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(b); }); } catch (e) {}
  }));
  return u => out[u];
}
const slug = s => (s || 'deck').replace(/[^\w]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
const opts = (list, v) => list.map(([k, l]) => `<option value="${esc(k)}" ${String(k) === String(v) ? 'selected' : ''}>${esc(l)}</option>`).join('');
const seg = (act, list, v, room) => `<div class="seg" role="group">${list.map(([k, l]) => `<button type="button" data-act="${act}" data-room="${room || ''}" data-v="${esc(k)}" aria-pressed="${String(k) === String(v)}">${esc(l)}</button>`).join('')}</div>`;

/* ---------- auth screens ---------- */
function bare(html) { $('#bar').hidden = true; $('#totalbar').hidden = true; $('#main').innerHTML = html; }
function showLogin(msg) {
  bare(`<form class="card login" id="loginform"><h1>Sign in</h1><p class="muted" style="margin:0">Bath Solution Studio</p>
    <label class="field"><span>Email</span><input type="text" id="l-email" autocomplete="username" required></label>
    <label class="field"><span>Password</span><input type="password" id="l-pw" autocomplete="current-password" required style="border:1px solid var(--line);border-radius:8px;padding:7px 9px"></label>
    <div class="err" id="l-err">${esc(msg || '')}</div><button class="btn primary" type="submit">Sign in</button>
    <p class="muted small" style="margin:0">Forgot your password? Ask your admin to reset it.</p></form>`);
  $('#loginform').onsubmit = async e => {
    e.preventDefault();
    try { await api('POST', '/api/login', { email: $('#l-email').value, password: $('#l-pw').value }); await boot(); }
    catch (err) { $('#l-err').textContent = err.message; }
  };
}
function showSetup() {
  bare(`<form class="card login" id="setupform"><h1>Set up Bath Solution Studio</h1><p class="muted" style="margin:0">Create the first admin account. You'll add the sales team after this.</p>
    <label class="field"><span>Your name</span><input type="text" id="s-name" required></label>
    <label class="field"><span>Email</span><input type="text" id="s-email" required></label>
    <label class="field"><span>Password (8+ characters)</span><input type="password" id="s-pw" required style="border:1px solid var(--line);border-radius:8px;padding:7px 9px"></label>
    <div class="err" id="s-err"></div><button class="btn primary" type="submit">Create admin account</button></form>`);
  $('#setupform').onsubmit = async e => {
    e.preventDefault();
    try { await api('POST', '/api/setup', { name: $('#s-name').value, email: $('#s-email').value, password: $('#s-pw').value }); await boot(); }
    catch (err) { $('#s-err').textContent = err.message; }
  };
}

/* ---------- boot & routing ---------- */
async function loadCatalog() {
  S.catalog = await api('GET', '/api/catalog');
  S.E = Engine.make(S.catalog, S.meta);
  const b = S.catalog.brands[0];
  if (S.range) {  // saved choices from an earlier version may use old category names
    S.range.categories = (S.range.categories || []).filter(c => S.meta.categories.includes(c));
    if (!S.range.categories.length) S.range.categories = S.meta.categories.slice();
  }
  if (!S.range || !S.catalog.brands.find(x => x.name === S.range.brand)) {
    S.range = b ? { brand: b.name, series: b.series.map(s => s.name), categories: S.meta.categories.slice(), finishes: S.meta.finishes.map(f => f.key), exclude: [], layout: 'detail', showPrices: false, title: `${b.name} collections`, recipient: '' } : null;
  }
}
async function boot() {
  const st = await api('GET', '/api/status');
  if (st.needs_setup) return showSetup();
  try { S.me = await api('GET', '/api/me'); } catch (e) { return; }
  S.meta = await api('GET', '/api/meta');
  await loadCatalog();
  $('#bar').hidden = false;
  $('#dealer').textContent = S.me.settings.dealer || 'Bath Solution Studio';
  if (!location.hash || location.hash === '#/') location.hash = '#/projects';
  route();
}
function nav() {
  const h = location.hash;
  const items = [['#/projects', 'Projects'], ['#/range', 'Range deck'], ['#/catalog', 'Catalog']];
  if (isAdmin()) items.push(['#/admin/catalogs', 'Upload & review'], ['#/admin/users', 'Users'], ['#/admin/settings', 'Settings']);
  $('#nav').innerHTML = items.map(([href, l]) => `<button type="button" data-href="${href}" aria-selected="${h.startsWith(href) || (href === '#/projects' && h.startsWith('#/project/'))}">${l}</button>`).join('');
  $('#meta').innerHTML = `<a href="#/account" class="muted">${esc(S.me.name)}</a> · <button class="btn ghost" type="button" data-act="logout" style="padding:2px 4px">Sign out</button>`;
}
async function route() {
  if (!S.me) return;
  clearInterval(S.poll);
  nav();
  const h = location.hash.slice(1);
  $('#totalbar').hidden = true;
  let m;
  try {
    if (h === '/projects') await viewProjects();
    else if ((m = h.match(/^\/project\/(\d+)$/))) await openProject(+m[1]);
    else if (h === '/range') viewRange();
    else if (h === '/catalog') viewCatalog();
    else if (h === '/account') viewAccount();
    else if (h === '/admin/catalogs' && isAdmin()) await viewCatalogs();
    else if ((m = h.match(/^\/admin\/catalogs\/(\d+)$/)) && isAdmin()) await viewReview(+m[1]);
    else if (h === '/admin/users' && isAdmin()) await viewUsers();
    else if (h === '/admin/settings' && isAdmin()) viewSettings();
    else location.hash = '#/projects';
  } catch (e) { $('#main').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}
window.addEventListener('hashchange', route);
const noCatalog = () => `<div class="card empty" style="margin-top:16px">No catalogs are published yet. ${isAdmin() ? '<a href="#/admin/catalogs">Upload a price list</a> to get started.' : 'Ask your admin to upload and publish a price list.'}</div>`;

/* ---------- projects ---------- */
async function viewProjects() {
  const ps = await api('GET', '/api/projects');
  $('#main').innerHTML = `<div class="row" style="justify-content:space-between"><div><h1>Projects</h1><p class="lede">One project per customer. Each project holds the rooms and the products chosen for them.</p></div>
    <button class="btn primary" type="button" data-act="newproject" ${S.catalog.products.length ? '' : 'disabled'}>New project</button></div>
    ${S.catalog.products.length ? '' : noCatalog()}
    <section class="card list" style="margin-top:16px">${ps.length ? ps.map(p => `<div class="li"><div><a href="#/project/${p.id}">${esc(p.title)}</a>
      <div class="muted small">${esc(p.customer || 'No customer name')} · ${p.rooms || 0} rooms · updated ${esc((p.updated_at || '').slice(0, 16))}${isAdmin() ? ' · ' + esc(p.owner) : ''}</div></div>
      <div class="row"><button class="btn ghost" type="button" data-act="dupproject" data-id="${p.id}">Duplicate</button><button class="btn ghost" type="button" data-act="delproject" data-id="${p.id}">Delete</button></div></div>`).join('')
      : '<div class="empty">No projects yet. Start one for your next customer.</div>'}</section>`;
}
function defaultsFor(brandName) {
  const b = S.E.brandOf(brandName) || S.catalog.brands[0];
  const series = b.series[0] ? b.series[0].name : '';
  const keys = finishesFor(b.name, series);
  return { brand: b.name, series, finish: keys.includes('chrome') ? 'chrome' : keys[0] || 'chrome' };
}
function finishesFor(brand, series) {
  const keys = new Set(S.catalog.products.filter(p => p.brand === brand && p.series === series).flatMap(p => p.variants.map(v => v.finish_key)));
  return S.meta.finishes.map(f => f.key).filter(k => keys.has(k));
}
const ACC_TYPES = { shelf: 'shower_shelf', mirror: 'mirror', rack: 'towel_rack', towel_ring: 'towel_ring', towel_rail: 'towel_rail' };
function newRoom(type, over) {
  const r = Object.assign({ id: uid(), name: type === 'Custom' ? 'Room' : type, type, tier: 'standard' }, defaultsFor(), JSON.parse(JSON.stringify(Engine.ROOM_PRESETS[type])), over || {});
  for (const [k, t] of Object.entries(ACC_TYPES)) if (r.acc[k] && !S.E.find(r.brand, r.series, t)) r.acc[k] = 0;  // presets skip what the collection lacks
  return rebuild(r);
}
function rebuild(r) { const b = S.E.buildRoom(r); r.items = b.items; r.warnings = b.warnings; r.edited = false; return r; }
async function createProject() {
  const d = { title: 'New project', customer: '', data: { site: '', notes: '', rooms: [newRoom('Master bath')] } };
  const r = await api('POST', '/api/projects', d);
  location.hash = `#/project/${r.id}`;
}
async function openProject(id) {
  const p = await api('GET', `/api/projects/${id}`);
  S.project = { id: p.id, title: p.title, customer: p.customer, site: p.data.site || '', notes: p.data.notes || '', rooms: p.data.rooms || [] };
  // refresh rooms that weren't hand-edited against the current catalog; flag missing products in edited rooms
  S.project.rooms.forEach(r => {
    if (!S.E.brandOf(r.brand)) Object.assign(r, defaultsFor());
    if (!r.edited) rebuild(r);
    else {
      r.items = r.items.filter(i => S.E.byId[i.pid] || (r.warnings = [...(r.warnings || []), `${i.name} (${i.art}) is no longer in the catalog and was removed.`], false));
      r.items.forEach(i => { i.category = S.E.byId[i.pid].category; });
      r.items = S.E.sortItems(r.items);
    }
  });
  renderProject();
}
let saveT, saveState = '';
function saveSoon() {
  saveState = 'Saving…'; setSaved();
  clearTimeout(saveT);
  saveT = setTimeout(async () => {
    const P = S.project;
    try { await api('PUT', `/api/projects/${P.id}`, { title: P.title, customer: P.customer, data: { site: P.site, notes: P.notes, rooms: P.rooms } }); saveState = 'Saved'; }
    catch (e) { saveState = 'Not saved: ' + e.message; }
    setSaved();
  }, 700);
}
function setSaved() { const el = $('#savestate'); if (el) el.textContent = saveState; }

const OPT = {
  mount: [['standard', 'Standard height'], ['raised', 'Raised (shallow basin)'], ['vessel', 'Tall, for vessel basin'], ['wall', 'Wall-mounted, concealed'], ['3hole', 'Three-hole']],
  shower: [['none', 'No shower'], ['exposed', 'Exposed wall mixer + hand shower'], ['conc_hand', 'Concealed mixer + hand shower'], ['conc_rain', 'Concealed: rain shower + hand shower'], ['thermo_rain', 'Thermostatic: rain shower + hand shower']],
  bath: [['none', 'No bath tub'], ['exposed', 'Wall mixer with hand shower set'], ['exposed_thermo', 'Thermostatic wall mixer'], ['rim', 'Four-hole mixer on the bath rim'], ['floor', 'Floor-standing, for a freestanding tub'], ['wall_spout', 'Concealed mixer + wall spout']],
  bidet: [['none', 'None'], ['spray', 'Health faucet (spray set)'], ['concealed', 'Concealed bidet mixer']],
  acc: [['towel_rail', 'Towel rail'], ['towel_ring', 'Towel ring'], ['hook', 'Towel hooks'], ['tp', 'Toilet paper holder'], ['rack', 'Towel rack'], ['shelf', 'Shower shelf'], ['mirror', 'Cosmetic mirror']]
};
const roomTotal = r => r.items.reduce((a, i) => a + i.qty * i.price, 0);
function roomForm(r) {
  const id = r.id, rain = r.shower.kind === 'conc_rain' || r.shower.kind === 'thermo_rain';
  const b = S.E.brandOf(r.brand);
  const fins = finishesFor(r.brand, r.series);
  return `<div class="form">
    ${S.catalog.brands.length > 1 ? `<label class="field"><span>Brand</span><select id="br-${id}" data-f="brand" data-room="${id}">${opts(S.catalog.brands.map(x => [x.name, x.name]), r.brand)}</select></label>` : ''}
    <div class="field"><span>Collection</span>${seg('series', b.series.map(s => [s.name, s.name + (s.style ? ' · ' + s.style.split(',')[0].toLowerCase() : '')]), r.series, id)}</div>
    <div class="field"><span>Finish · ${esc(S.E.finishLabel(r.finish))}</span><div class="sw">${fins.map(k => `<button type="button" title="${esc(S.E.finishLabel(k))}" aria-label="${esc(S.E.finishLabel(k))}" data-act="finish" data-room="${id}" data-v="${k}" aria-pressed="${k === r.finish}" style="background:${swc(k)}"></button>`).join('')}</div></div>
    <div class="field"><span>Budget level</span>${seg('tier', [['value', 'Value'], ['standard', 'Standard'], ['premium', 'Premium']], r.tier, id)}</div>
    <div class="two">
      <label class="field"><span>Basins</span><select id="b-${id}" data-f="basins.count" data-room="${id}">${opts([[0, 'None'], [1, '1 basin'], [2, '2 basins']], r.basins.count)}</select></label>
      <label class="field"><span>Basin mixer</span><select id="m-${id}" data-f="basins.mount" data-room="${id}" ${r.basins.count ? '' : 'disabled'}>${opts(OPT.mount, r.basins.mount)}</select></label>
    </div>
    <label class="field"><span>Shower</span><select id="s-${id}" data-f="shower.kind" data-room="${id}">${opts(OPT.shower, r.shower.kind)}</select></label>
    ${rain ? `<div class="two">
      <label class="field"><span>Overhead size</span><select id="h-${id}" data-f="shower.head" data-room="${id}">${opts([[250, 'About 250 mm'], [300, 'About 300 mm']], r.shower.head)}</select></label>
      <label class="field"><span>Arm</span><select id="a-${id}" data-f="shower.arm" data-room="${id}">${opts([['wall', 'Wall-mounted'], ['ceiling', 'Ceiling-mounted']], r.shower.arm)}</select></label></div>` : ''}
    <label class="field"><span>Bath tub</span><select id="t-${id}" data-f="bath" data-room="${id}">${opts(OPT.bath, r.bath)}</select></label>
    <label class="field"><span>Bidet / health faucet</span><select id="d-${id}" data-f="bidet" data-room="${id}">${opts(OPT.bidet, r.bidet)}</select></label>
    <div class="field"><span>Accessories</span><div class="acc">${OPT.acc.map(([k, l]) => `<span>${esc(l)}</span><span class="step"><button type="button" aria-label="Fewer" data-act="acc" data-room="${id}" data-k="${k}" data-d="-1">−</button><b>${r.acc[k] || 0}</b><button type="button" aria-label="More" data-act="acc" data-room="${id}" data-k="${k}" data-d="1">+</button></span>`).join('')}</div></div>
  </div>`;
}
function itemRow(r, it) {
  const p = S.E.byId[it.pid];
  const fins = p ? [...new Map(p.variants.filter(v => !it.width_mm || !v.width_mm || v.width_mm === it.width_mm).map(v => [v.finish_key + '|' + v.finish, v])).values()] : [];
  const alts = S.E.alternatives(it);
  const cur = curOf(it.brand);
  return `<div class="it">
    <div class="thumb">${it.image ? `<img alt="" src="${esc(it.image)}" loading="lazy">` : ''}</div>
    <div style="min-width:0">
      <div class="nm">${esc(it.name)}${it.series !== r.series ? ` <span class="pill">${esc(it.series)}</span>` : ''}</div>
      <div class="muted small"><span class="mono">${esc(it.art)}</span> · <span class="dot" style="background:${swc(it.finish_key)}"></span> ${esc(it.finish)}${it.width_mm ? ' · ' + it.width_mm + ' mm' : ''}</div>
      ${it.why ? `<div class="why">${esc(it.why)}</div>` : ''}
      ${(it.flags || []).map(f => `<div class="flag">⚠ ${esc(f)}</div>`).join('')}
      <div class="ctl">
        ${fins.length > 1 ? `<select aria-label="Finish" id="f-${it.uid}" data-act="ifinish" data-room="${r.id}" data-uid="${it.uid}">${fins.map(v => `<option value="${v.finish_key}" ${v.art === it.art ? 'selected' : ''}>${esc(v.finish)}</option>`).join('')}</select>` : ''}
        ${alts.length ? `<select aria-label="Replace with" id="r-${it.uid}" data-act="swap" data-room="${r.id}" data-uid="${it.uid}"><option value="">Replace with…</option>${alts.map(a => `<option value="${a.id}">${esc(a.series + ' · ' + a.name)}</option>`).join('')}</select>` : ''}
      </div>
    </div>
    <div class="right">
      <span class="step"><button type="button" aria-label="Fewer" data-act="qty" data-room="${r.id}" data-uid="${it.uid}" data-d="-1">−</button><b>${it.qty}</b><button type="button" aria-label="More" data-act="qty" data-room="${r.id}" data-uid="${it.uid}" data-d="1">+</button></span>
      <span class="num" style="font-weight:600">${money(it.qty * it.price, cur)}</span>
      <span class="num muted small">${money(it.price, cur)} each</span>
      <button class="x" type="button" data-act="del" data-room="${r.id}" data-uid="${it.uid}">Remove</button>
    </div></div>`;
}
function addSelect(r) {
  const groups = S.meta.categories.map(c => [c, S.catalog.products.filter(p => p.brand === r.brand && p.category === c).sort((a, b) => (a.series === r.series ? -1 : 1) - (b.series === r.series ? -1 : 1))]).filter(g => g[1].length);
  return `<select class="add" aria-label="Add a product" id="add-${r.id}" data-act="add" data-room="${r.id}"><option value="">+ Add a product…</option>${groups.map(([c, ps]) => `<optgroup label="${esc(S.E.groupOf(c) + ' · ' + c)}">${ps.map(p => `<option value="${p.id}">${esc(p.series + ' · ' + p.name)}</option>`).join('')}</optgroup>`).join('')}</select>`;
}
function roomCard(r) {
  const b = S.E.brandOf(r.brand) || {};
  return `<section class="card room" id="room-${r.id}">
    <div class="room-head">
      <input type="text" id="n-${r.id}" aria-label="Room name" data-f="name" data-room="${r.id}" value="${esc(r.name)}">
      <select id="ty-${r.id}" aria-label="Room type" data-act="type" data-room="${r.id}">${opts(Object.keys(Engine.ROOM_PRESETS).map(k => [k, k + ' preset']), r.type)}</select>
      <div class="sub"><span class="muted small">${r.items.reduce((a, i) => a + i.qty, 0)} items</span><b class="num">${money(roomTotal(r), b.currency)}</b>
      <button class="btn ghost" type="button" data-act="dup" data-room="${r.id}">Duplicate</button>
      <button class="btn ghost" type="button" data-act="rmroom" data-room="${r.id}">Delete</button></div>
    </div>
    <div class="room-body">${roomForm(r)}
      <div class="items">
        ${r.edited ? `<div class="warns" style="background:var(--accent-soft);color:var(--ink);display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap"><p>You edited this list by hand. Changes to the form on the left won't apply until you rebuild.</p><button class="btn" type="button" data-act="rebuild" data-room="${r.id}">Rebuild from form</button></div>` : ''}
        ${(r.warnings || []).length ? `<div class="warns">${r.warnings.map(w => `<p>${esc(w)}</p>`).join('')}</div>` : ''}
        ${r.items.length ? r.items.map((it, i) => {
          const g = S.E.groupOf(it.category), prev = i ? S.E.groupOf(r.items[i - 1].category) : null;
          return (g && g !== prev ? `<div class="grouphead">${esc(g)}</div>` : '') + itemRow(r, it);
        }).join('') : '<div class="empty">No products yet. Choose fixtures on the left or add a product.</div>'}
        <div class="room-foot">${addSelect(r)}<span class="muted small">${esc(b.price_basis || '')} · ${esc(b.currency || '')}</span></div>
      </div>
    </div></section>`;
}
function renderProject() {
  const P = S.project, y = window.scrollY;
  $('#main').innerHTML = `<div class="row" style="justify-content:space-between;align-items:flex-start">
      <div><a href="#/projects" class="small">← All projects</a><h1 style="margin-top:4px">${esc(P.title)}</h1><p class="lede">Describe each room. The builder picks matching products, adds the parts each fitting needs, and keeps the finish consistent. Edit anything, then download an editable PowerPoint.</p></div>
      <span class="saved" id="savestate">${esc(saveState)}</span></div>
    <section class="card" style="margin-top:16px">
      <div class="proj">
        <label class="field"><span>Project</span><input type="text" id="p-title" data-p="title" value="${esc(P.title)}"></label>
        <label class="field"><span>Customer</span><input type="text" id="p-customer" data-p="customer" value="${esc(P.customer)}"></label>
        <label class="field"><span>Site</span><input type="text" id="p-site" data-p="site" value="${esc(P.site)}"></label>
      </div>
      <div style="padding:0 16px 16px"><label class="field"><span>Customer requirement notes (shown on the overview slide)</span><textarea id="p-notes" data-p="notes" placeholder="e.g. 3 bathrooms. Master: twin basins, rain shower, freestanding tub, matt black…">${esc(P.notes)}</textarea></label></div>
    </section>
    ${P.rooms.map(roomCard).join('')}
    <div class="row" style="margin-top:16px">${Object.keys(Engine.ROOM_PRESETS).map(k => `<button class="btn" type="button" data-act="addroom" data-v="${k}">+ ${k}</button>`).join('')}</div>`;
  const curs = [...new Set(P.rooms.map(r => curOf(r.brand)))];
  const t = P.rooms.reduce((a, r) => a + roomTotal(r), 0), n = P.rooms.reduce((a, r) => a + r.items.reduce((b, i) => b + i.qty, 0), 0);
  const fl = P.rooms.reduce((a, r) => a + r.items.filter(i => (i.flags || []).length).length, 0);
  $('#totalbar').hidden = false;
  $('#totalbar').innerHTML = `<div class="wrap"><div><div class="muted small">${P.rooms.length} rooms · ${n} items</div><div class="t">${curs.length > 1 ? 'Mixed currencies' : money(t, curs[0])}</div></div>
    <div class="msg">${fl ? `<span class="pill warn">${fl} item${fl > 1 ? 's' : ''} to check</span> Flagged items are listed on the notes slide.` : ''}</div>
    <button class="btn primary" type="button" data-act="pptsol" ${P.rooms.length ? '' : 'disabled'}>Download proposal (.pptx)</button></div>`;
  window.scrollTo(0, y);
}
function briefOf(r) {
  const parts = [];
  if (r.basins.count) parts.push(`${r.basins.count} basin${r.basins.count > 1 ? 's' : ''}`);
  const sh = { exposed: 'exposed shower', conc_hand: 'concealed hand shower', conc_rain: 'rain shower', thermo_rain: 'thermostatic rain shower' }[r.shower.kind]; if (sh) parts.push(sh);
  if (r.bath !== 'none') parts.push('bath tub');
  if (r.bidet !== 'none') parts.push('health faucet');
  return parts.join(' · ');
}
async function pptSolution(btn) {
  btn.disabled = true; btn.textContent = 'Building…';
  try {
    const P = S.project, st = S.me.settings;
    const img = await dataUrls(P.rooms.flatMap(r => r.items.map(i => i.image)));
    const brands = [...new Set(P.rooms.map(r => r.brand))].map(n => S.E.brandOf(n)).filter(Boolean);
    const rooms = P.rooms.map(r => ({ ...r, style: ((S.E.brandOf(r.brand) || { series: [] }).series.find(s => s.name === r.series) || {}).style || '', finishLabel: S.E.finishLabel(r.finish), brief: briefOf(r) }));
    const pptx = new PptxGenJS();
    DeckBuilder.buildSolution(pptx, { groupOf: S.E.groupOf, title: P.title, customer: P.customer, site: P.site, salesperson: S.me.name, dealer: st.dealer, notes: P.notes, date: today(), rooms,
      currency: brands[0] ? brands[0].currency : 'EUR', priceNote: brands.map(b => `${b.name}: ${b.price_basis}, ${b.currency}`).join('; '), sources: brands.map(b => `${b.name} ${b.catalog}`).join(', ') }, img);
    download(slug(P.title) + '-proposal.pptx', await pptx.write({ outputType: 'blob' }));
  } catch (e) { toast('Could not build the deck: ' + e.message); }
  btn.disabled = false; btn.textContent = 'Download proposal (.pptx)';
}

/* ---------- range deck ---------- */
function viewRange() {
  if (!S.range) { $('#main').innerHTML = `<h1>Brand range deck</h1>${noCatalog()}`; return; }
  const R = S.range, E = S.E, b = E.brandOf(R.brand);
  const all = E.rangeGroups({ ...R, exclude: [] }), groups = E.rangeGroups(R);
  const count = groups.reduce((a, g) => a + g.products.length, 0);
  const slides = 2 + groups.reduce((a, g) => {
    const grps = new Set(g.products.map(p => E.groupOf(p.category)));
    const perCat = Object.values(g.products.reduce((m, p) => (m[p.category] = (m[p.category] || 0) + 1, m), {}));
    return a + 1 + (grps.size > 1 ? grps.size : 0) + (R.layout === 'grid' ? perCat.reduce((x, n) => x + Math.ceil(n / 6), 0) : g.products.length);
  }, 0);
  $('#main').innerHTML = `<h1>Brand range deck</h1><p class="lede">Send an architect or designer a brand's range, or keep a brand-wise reference for the sales team. Every product gets its finishes and article numbers.</p>
  <div class="range">
    <section class="card panel">
      <label class="field"><span>Brand</span><select id="r-brand" data-r="brand">${opts(S.catalog.brands.map(x => [x.name, x.name]), R.brand)}</select><span class="muted small" style="text-transform:none;letter-spacing:0;font-weight:400">${esc(b.catalog)} · ${esc(b.price_basis)} · ${esc(b.currency)}</span></label>
      <div class="field"><span>Collections</span><div class="checks">${b.series.map(s => `<label><input type="checkbox" id="rs-${esc(s.name)}" data-rlist="series" value="${esc(s.name)}" ${R.series.includes(s.name) ? 'checked' : ''}> ${esc(s.name)} <span class="muted small">${esc(s.style)}</span></label>`).join('')}</div></div>
      ${S.meta.groups.filter(g => g.name !== 'Other').map(g => `<div class="field"><span>${esc(g.name)}</span><div class="checks">${g.categories.map(c => `<label><input type="checkbox" data-rlist="categories" value="${esc(c)}" ${R.categories.includes(c) ? 'checked' : ''}> ${esc(c)}</label>`).join('')}</div></div>`).join('')}
      <div class="field"><span>Finishes to list</span><div class="checks">${S.meta.finishes.map(f => `<label><input type="checkbox" data-rlist="finishes" value="${f.key}" ${R.finishes.includes(f.key) ? 'checked' : ''}> <span class="dot" style="background:#${f.color}"></span> ${esc(f.label)}</label>`).join('')}</div></div>
      <div class="field"><span>Layout</span>${seg('rlayout', [['detail', 'One product per slide'], ['grid', 'Overview, 6 per slide']], R.layout)}</div>
      <label><input type="checkbox" id="r-prices" data-rbool="showPrices" ${R.showPrices ? 'checked' : ''}> Show prices (internal use)</label>
      <label class="field"><span>Deck title</span><input type="text" id="r-title" data-rt="title" value="${esc(R.title)}"></label>
      <label class="field"><span>Prepared for</span><input type="text" id="r-rec" data-rt="recipient" value="${esc(R.recipient)}" placeholder="Architect or firm"></label>
    </section>
    <section class="card">
      <div class="room-head"><b>${count} products</b><span class="muted small">about ${slides} slides · ${R.showPrices ? 'with prices' : 'no prices'}</span>
        <div class="sub"><button class="btn ghost" type="button" data-act="rall">Include all</button></div></div>
      ${all.length ? all.map(g => `<div class="grid"><div class="cathead"><h2>${esc(g.series)}</h2><span class="muted small">${esc(g.style)}</span></div>${g.products.map((p, i) => {
        const on = !R.exclude.includes(p.id);
        const head = !i || g.products[i - 1].category !== p.category ? `<div class="cathead small"><b>${esc(p.category)}</b><span class="muted">${esc(E.groupOf(p.category))}</span></div>` : '';
        return head + `<label class="tile ${on ? '' : 'off'}"><input type="checkbox" data-rx="${p.id}" ${on ? 'checked' : ''}><div class="im">${p.image ? `<img alt="" loading="lazy" src="${esc(p.image)}">` : ''}</div><div class="tx"><span class="c">${esc(p.category)}</span><span class="n">${esc(p.name)}</span><span>${p.variants.map(v => `<span class="dot" style="background:${swc(v.finish_key)}"></span>`).join(' ')}</span></div></label>`;
      }).join('')}</div>`).join('') : '<div class="empty">Pick at least one collection and category.</div>'}
    </section>
  </div>`;
  $('#totalbar').hidden = false;
  $('#totalbar').innerHTML = `<div class="wrap"><div><div class="muted small">${esc(R.brand)} · ${esc(R.series.join(', ') || 'no collection')}</div><div class="t">${count} products</div></div><div class="msg"></div>
    <button class="btn primary" type="button" data-act="pptrange" ${count ? '' : 'disabled'}>Download range deck (.pptx)</button></div>`;
}
async function pptRange(btn) {
  btn.disabled = true; btn.textContent = 'Building…';
  try {
    const R = S.range, b = S.E.brandOf(R.brand), st = S.me.settings;
    const groups = S.E.rangeGroups(R);
    const img = await dataUrls(groups.flatMap(g => g.products.map(p => p.image)));
    const pptx = new PptxGenJS();
    DeckBuilder.buildRange(pptx, { groupOf: S.E.groupOf, brand: R.brand, catalog: b.catalog, currency: b.currency, priceNote: `${b.price_basis}, ${b.currency}`, title: R.title || `${R.brand} collections`, recipient: R.recipient,
      salesperson: S.me.name, dealer: st.dealer, contact: st.contact, date: today(), showPrices: R.showPrices, layout: R.layout, groups }, img);
    download(slug(R.title || R.brand) + '-range.pptx', await pptx.write({ outputType: 'blob' }));
  } catch (e) { toast('Could not build the deck: ' + e.message); }
  btn.disabled = false; btn.textContent = 'Download range deck (.pptx)';
}

/* ---------- catalog (browse) ---------- */
function catRows() {
  const C = S.cat, q = C.q.toLowerCase();
  return S.catalog.products.filter(p => (!C.brand || p.brand === C.brand) && (!C.series || p.series === C.series) && (!C.category || p.category === C.category) &&
    (!q || (p.brand + ' ' + p.name + ' ' + p.category + ' ' + p.series + ' ' + p.variants.map(v => v.art + ' ' + v.art.replace(/ /g, '') + ' ' + v.finish).join(' ') + ' ' + p.specs.flatMap(g => g.items).join(' ')).toLowerCase().includes(q)));
}
function catTable(rows) {
  return `<table><thead><tr><th></th><th>Product</th><th>Key specs</th><th>Finish</th><th>Article no.</th><th class="num">Price</th></tr></thead><tbody>${rows.slice(0, 400).map(p => p.variants.map((v, i) => `<tr>
    ${i === 0 ? `<td rowspan="${p.variants.length}" style="width:64px"><div class="thumb">${p.image ? `<img alt="" loading="lazy" src="${esc(p.image)}">` : ''}</div></td><td rowspan="${p.variants.length}" style="min-width:180px"><b>${esc(p.name)}</b><div class="muted small">${esc(p.brand)} ${esc(p.series)} · ${esc(p.category)}${p.source_page ? ' · p. ' + p.source_page : ''}</div>${p.note ? `<div class="muted small">${esc(p.note)}</div>` : ''}</td><td rowspan="${p.variants.length}" class="small muted" style="min-width:200px">${p.specs.flatMap(g => g.items).slice(0, 5).map(esc).join('<br>')}</td>` : ''}
    <td class="small"><span class="dot" style="background:${swc(v.finish_key)}"></span> ${esc(v.finish)}${v.width_mm ? ' · ' + v.width_mm + ' mm' : ''}</td><td class="mono">${esc(v.art)}</td><td class="num">${money(v.price, p.currency)}</td></tr>`).join('')).join('')}</tbody></table>${rows.length > 400 ? '<div class="empty">Showing the first 400 products. Narrow the search to see more.</div>' : ''}`;
}
function viewCatalog() {
  const C = S.cat, P = S.catalog.products;
  if (!P.length) { $('#main').innerHTML = `<h1>Catalog</h1>${noCatalog()}`; return; }
  const brand = C.brand ? S.E.brandOf(C.brand) : null;
  const rows = catRows();
  $('#main').innerHTML = `<h1>Catalog</h1><p class="lede">All published products, with finishes, article numbers and prices.</p>
  <div class="stats">${S.catalog.brands.map(b => `<div class="card stat"><span class="lab">${esc(b.name)}</span><b>${P.filter(p => p.brand === b.name).length}</b><span class="muted small">products · ${esc(b.catalog)}</span></div>`).join('')}</div>
  <section class="card" style="margin-top:16px">
    <div class="room-head">
      <input type="text" id="c-q" data-c="q" value="${esc(C.q)}" placeholder="Search name, spec or article no." style="max-width:300px">
      <select id="c-b" data-c="brand" style="width:auto"><option value="">All brands</option>${opts(S.catalog.brands.map(b => [b.name, b.name]), C.brand)}</select>
      ${brand ? `<select id="c-s" data-c="series" style="width:auto"><option value="">All collections</option>${opts(brand.series.map(s => [s.name, s.name]), C.series)}</select>` : ''}
      <select id="c-c" data-c="category" style="width:auto"><option value="">All categories</option>${S.meta.groups.map(g => `<optgroup label="${esc(g.name)}">${opts(g.categories.map(c => [c, c]), C.category)}</optgroup>`).join('')}</select>
      <div class="sub muted small" id="c-count">${rows.length} products</div>
    </div>
    <div class="tbl" id="c-tbl">${catTable(rows)}</div>
  </section>`;
}

/* ---------- account ---------- */
function viewAccount() {
  $('#main').innerHTML = `<h1>Your account</h1><p class="lede">${esc(S.me.name)} · ${esc(S.me.email)} · ${S.me.role === 'admin' ? 'Admin' : 'Sales'}</p>
  <form class="card panel" id="pwform" style="max-width:420px;margin-top:16px"><h2>Change password</h2>
    <label class="field"><span>Current password</span><input type="password" id="a-cur" required style="border:1px solid var(--line);border-radius:8px;padding:7px 9px"></label>
    <label class="field"><span>New password (8+ characters)</span><input type="password" id="a-new" required style="border:1px solid var(--line);border-radius:8px;padding:7px 9px"></label>
    <div class="err" id="a-err"></div><button class="btn primary" type="submit">Change password</button></form>`;
  $('#pwform').onsubmit = async e => {
    e.preventDefault();
    try { await api('POST', '/api/me/password', { current: $('#a-cur').value, new: $('#a-new').value }); toast('Password changed'); viewAccount(); }
    catch (err) { $('#a-err').textContent = err.message; }
  };
}

/* ---------- admin: catalogs ---------- */
async function viewCatalogs() {
  const cs = await api('GET', '/api/catalogs');
  const brands = [...new Set(cs.map(c => c.brand))];
  const busy = cs.some(c => c.status === 'processing');
  $('#main').innerHTML = `<h1>Upload & review</h1><p class="lede">Upload a brand's price list. The system reads the products, then you check and correct them before publishing to the sales team. If a PDF doesn't read well, fill the Excel template instead.</p>
  <div class="pipe"><div><div class="lab">1 · Upload</div>PDF price list or Excel template</div><div><div class="lab">2 · Read</div>Products, specs, finishes, prices, photos</div><div><div class="lab">3 · Review</div>Fix flagged items, set types and photos</div><div><div class="lab">4 · Publish</div>Sales team can use it</div></div>
  <form class="card" id="upform" style="margin-top:16px">
    <div class="upload">
      <label class="field"><span>File (PDF or .xlsx)</span><input type="file" id="u-file" accept=".pdf,.xlsx,.xlsm" required></label>
      <label class="field"><span>Brand</span><input type="text" id="u-brand" list="brandlist" required placeholder="e.g. KEUCO"><datalist id="brandlist">${brands.map(b => `<option value="${esc(b)}">`).join('')}</datalist></label>
      <label class="field"><span>Catalog name</span><input type="text" id="u-name" placeholder="e.g. Project Series 2025"></label>
      <label class="field"><span>Currency</span><select id="u-cur">${opts([['EUR', 'EUR €'], ['INR', 'INR ₹'], ['USD', 'USD $'], ['GBP', 'GBP £']], 'EUR')}</select></label>
      <label class="field"><span>Price basis</span><input type="text" id="u-basis" value="RRP excl. VAT"></label>
      <label class="field"><span>Reader</span><select id="u-parser">${opts([['auto', 'Automatic (by brand)'], ...S.meta.readers.map(r => [r.key, r.label])], 'auto')}</select></label>
      <label class="field"><span>Collection name (if not printed on pages)</span><input type="text" id="u-series" placeholder="Optional"></label>
      <div class="row"><button class="btn primary" type="submit" id="u-go">Upload and read</button><a href="/api/template.xlsx" class="small">Download Excel template</a></div>
    </div>
    <div class="err" id="u-err" style="padding:0 16px 12px"></div>
  </form>
  <section class="card list" style="margin-top:16px">${cs.length ? cs.map(c => `<div class="li"><div>
      <a href="#/admin/catalogs/${c.id}">${esc(c.brand)} · ${esc(c.name)}</a> <span class="status ${c.status}">${{ processing: 'Reading…', review: 'Needs review', published: 'Published', archived: 'Archived', failed: 'Failed' }[c.status]}</span>
      <div class="muted small">${c.products} products · ${c.skus} article numbers${c.flagged + c.product_issues ? ` · <span style="color:var(--warn)">${c.flagged + c.product_issues} to check</span>` : ''} · ${esc(c.filename || '')} · uploaded ${esc((c.uploaded_at || '').slice(0, 16))}${c.uploaded_by ? ' by ' + esc(c.uploaded_by) : ''}</div></div>
      <div class="row">${c.status === 'review' || c.status === 'archived' ? `<button class="btn" type="button" data-act="publish" data-id="${c.id}">Publish</button>` : ''}${c.status === 'published' ? `<button class="btn ghost" type="button" data-act="unpublish" data-id="${c.id}">Unpublish</button>` : ''}
      <a class="btn" href="#/admin/catalogs/${c.id}">Review</a><button class="btn ghost" type="button" data-act="delcatalog" data-id="${c.id}">Delete</button></div></div>`).join('')
    : '<div class="empty">No catalogs yet. Upload the first price list above.</div>'}</section>`;
  $('#upform').onsubmit = async e => {
    e.preventDefault();
    const f = $('#u-file').files[0]; if (!f) return;
    const fd = new FormData();
    fd.append('file', f); fd.append('brand', $('#u-brand').value); fd.append('name', $('#u-name').value); fd.append('currency', $('#u-cur').value);
    fd.append('price_basis', $('#u-basis').value); fd.append('parser', $('#u-parser').value); fd.append('series', $('#u-series').value);
    $('#u-go').disabled = true; $('#u-go').textContent = 'Uploading…';
    try { await api('POST', '/api/catalogs', fd, true); toast('Uploaded. Reading the file…'); viewCatalogs(); }
    catch (err) { $('#u-err').textContent = err.message; $('#u-go').disabled = false; $('#u-go').textContent = 'Upload and read'; }
  };
  if (busy) S.poll = setInterval(async () => { const n = await api('GET', '/api/catalogs'); if (!n.some(c => c.status === 'processing')) { clearInterval(S.poll); viewCatalogs(); } }, 2500);
}
const confirmBtn = (btn, label) => { if (btn.dataset.armed) return true; btn.dataset.armed = '1'; btn.dataset.label = btn.textContent; btn.textContent = label; btn.classList.add('confirm'); setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; btn.textContent = btn.dataset.label; btn.classList.remove('confirm'); } }, 4000); return false; };

/* ---------- admin: review ---------- */
function specsToText(specs) { return specs.map(g => (g.group ? `## ${g.group}\n` : '') + g.items.join('\n')).join('\n'); }
function textToSpecs(t) {
  const out = [{ group: null, items: [] }];
  t.split('\n').map(l => l.trim()).filter(Boolean).forEach(l => { if (l.startsWith('## ')) out.push({ group: l.slice(3), items: [] }); else out[out.length - 1].items.push(l.replace(/^[•\-]\s*/, '')); });
  return out.filter(g => g.items.length || g.group);
}
async function viewReview(id, keepScroll) {
  const y = window.scrollY;
  S.review = await api('GET', `/api/catalogs/${id}`);
  S.review.only = S.review.only ?? false;
  renderReview();
  if (keepScroll) window.scrollTo(0, y);
  if (S.review.catalog.status === 'processing') S.poll = setInterval(async () => { const r = await api('GET', `/api/catalogs/${id}`); if (r.catalog.status !== 'processing') { clearInterval(S.poll); viewReview(id); } else { const l = $('#log'); if (l) l.textContent = r.catalog.log; } }, 2000);
}
function needsWork(p) { return (p.attributes.issues || []).length || p.variants.some(v => v.flags.length); }
function renderReview() {
  const R = S.review, c = R.catalog, only = R.only, q = (R.q || '').toLowerCase();
  const list = R.products.filter(p => (!only || needsWork(p)) && (!q || (p.name + ' ' + p.series + ' ' + p.variants.map(v => v.art).join(' ')).toLowerCase().includes(q)));
  const nWork = R.products.filter(needsWork).length;
  const typeOpts = S.meta.categories.map(cat => `<optgroup label="${esc(S.E.groupOf(cat) + ' · ' + cat)}">${S.meta.types.filter(t => t.category === cat).map(t => `<option value="${t.key}">${esc(t.label)}</option>`).join('')}</optgroup>`).join('');
  $('#main').innerHTML = `<a href="#/admin/catalogs" class="small">← All catalogs</a>
  <div class="row" style="justify-content:space-between;margin-top:4px"><div><h1>${esc(c.brand)} · ${esc(c.name)} <span class="status ${c.status}">${c.status}</span></h1>
    <p class="lede">${R.products.length} products from ${esc(c.filename || '')}. ${nWork ? `${nWork} need attention.` : 'Nothing flagged.'} Sales see this catalog only after you publish it.</p></div></div>
  <div class="sticky-actions">
    ${c.status !== 'published' && c.status !== 'processing' && c.status !== 'failed' ? `<button class="btn primary" type="button" data-act="publish" data-id="${c.id}">Publish to sales</button><label class="small"><input type="checkbox" id="rv-replace" checked> Replace the brand's current catalog</label>` : ''}
    ${c.status === 'published' ? `<button class="btn" type="button" data-act="unpublish" data-id="${c.id}">Unpublish</button>` : ''}
    <label class="small"><input type="checkbox" id="rv-only" ${only ? 'checked' : ''}> Needs attention only</label>
    <input type="text" id="rv-q" placeholder="Find product or article no." value="${esc(R.q || '')}" style="max-width:240px">
    <button class="btn ghost" type="button" data-act="addproduct">+ Add product</button>
    <a class="btn ghost" href="/api/catalogs/${c.id}/file">Original file</a>
  </div>
  ${/didn't read cleanly/.test(c.log || '') ? `<div class="warns" style="margin:0 0 12px">${esc((c.log.split('\n').find(l => l.includes("didn't read cleanly")) || ''))}</div>` : ''}
  <details class="card" style="padding:12px 16px" ${c.status === 'processing' || c.status === 'failed' ? 'open' : ''}><summary>Reading log</summary><pre class="log" id="log">${esc(c.log || '')}</pre></details>
  <section class="card" style="margin-top:12px;padding:16px">
    <h2>Brand & collections</h2>
    <div class="upload" style="padding:12px 0 0">
      <label class="field"><span>Catalog name</span><input type="text" id="rc-name" value="${esc(c.name)}"></label>
      <label class="field"><span>Currency</span><select id="rc-cur">${opts([['EUR', 'EUR €'], ['INR', 'INR ₹'], ['USD', 'USD $'], ['GBP', 'GBP £']], c.currency)}</select></label>
      <label class="field"><span>Price basis</span><input type="text" id="rc-basis" value="${esc(c.price_basis)}"></label>
      <button class="btn" type="button" data-act="savecat" data-id="${c.id}">Save</button>
    </div>
    <div class="upload" style="padding:12px 0 0">${R.series.map(s => `<label class="field"><span>${esc(s.name)} style</span><input type="text" data-series="${s.id}" value="${esc(s.style)}" placeholder="e.g. Round, soft forms"></label>`).join('')}</div>
  </section>
  <section class="card" style="margin-top:12px" id="plist">
    ${list.length ? list.map(p => productForm(p, typeOpts)).join('') : `<div class="empty">${c.status === 'processing' ? 'Reading the file…' : 'No products match.'}</div>`}
  </section>
  <input type="file" id="imgpick" accept="image/*" hidden>`;
}
function productForm(p, typeOpts) {
  const fam = S.meta.finishes;
  return `<form class="pform" data-pid="${p.id}" id="pf-${p.id}">
    <div><div class="ph" data-act="pickimg" data-pid="${p.id}" title="Change photo">${p.image ? `<img alt="" loading="lazy" src="${esc(p.image)}">` : ''}<span>${p.image ? 'Change photo' : 'Add photo'}</span></div>
      <div class="muted small" style="margin-top:6px">${p.source_page ? 'Page ' + p.source_page : 'Added by hand'}</div></div>
    <div style="min-width:0;display:flex;flex-direction:column;gap:10px">
      ${(p.attributes.issues || []).map(i => `<div class="flag">⚠ ${esc(i)}</div>`).join('')}
      <div class="pgrid">
        <label class="field"><span>Product name</span><input type="text" name="name" value="${esc(p.name)}"></label>
        <label class="field"><span>Collection</span><input type="text" name="series" value="${esc(p.series)}"></label>
        <label class="field"><span>Type (used by the solution builder)</span><select name="type">${typeOpts.replace(`value="${p.type}"`, `value="${p.type}" selected`)}</select></label>
      </div>
      <div class="tbl"><table class="vt"><thead><tr><th>Article no.</th><th>Finish as printed</th><th>Finish family</th><th>Width mm</th><th>Price</th><th></th><th></th></tr></thead><tbody>
        ${p.variants.map(v => variantRow(v, fam)).join('')}
      </tbody></table></div>
      <div class="row"><button class="btn ghost" type="button" data-act="addvariant" data-pid="${p.id}">+ Finish / article</button></div>
      <details><summary class="small">Specs (${p.specs.reduce((a, g) => a + g.items.length, 0)} lines)</summary><textarea name="specs" rows="6" style="margin-top:6px">${esc(specsToText(p.specs))}</textarea><div class="muted small">One spec per line. Start a line with "## " to begin a group, for example "## Rough part".</div></details>
      <div class="row"><button class="btn primary" type="submit">Save product</button><button class="btn ghost" type="button" data-act="delproduct" data-pid="${p.id}">Delete product</button><span class="saved" id="ps-${p.id}"></span></div>
    </div></form>`;
}
function variantRow(v, fam) {
  return `<tr data-vid="${v.id || ''}"><td><input type="text" name="art" value="${esc(v.art)}" class="mono" style="min-width:150px"></td>
    <td><input type="text" name="finish" value="${esc(v.finish)}"></td>
    <td><select name="finish_key">${fam.map(f => `<option value="${f.key}" ${f.key === v.finish_key ? 'selected' : ''}>${esc(f.label)}</option>`).join('')}</select></td>
    <td><input type="text" name="width" value="${v.width_mm || ''}" style="width:70px"></td>
    <td><input type="text" name="price" value="${v.price ?? ''}" style="width:90px" class="num"></td>
    <td><button class="x btn ghost" type="button" data-act="delvariant">✕</button></td>
    <td class="fl">${(v.flags || []).map(esc).join('<br>')}${(v.flags || []).length && v.id ? `<br><button class="btn ghost small" type="button" data-act="acceptflag" data-vid="${v.id}" style="padding:2px 0">It's correct, clear warning</button>` : ''}</td></tr>`;
}
function readProductForm(form) {
  const g = n => form.querySelector(`[name="${n}"]`).value;
  const type = g('type');
  const variants = [...form.querySelectorAll('tbody tr')].map(tr => {
    const f = n => tr.querySelector(`[name="${n}"]`).value.trim();
    const price = f('price').replace(/,/g, '');
    return { id: tr.dataset.vid ? +tr.dataset.vid : null, art: f('art'), finish: f('finish'), finish_key: f('finish_key'), width_mm: /^\d+$/.test(f('width')) ? +f('width') : null, price: price === '' || isNaN(+price) ? null : +price };
  }).filter(v => v.art);
  return { name: g('name').trim() || 'Untitled product', series: g('series').trim(), type, category: (S.meta.types.find(t => t.key === type) || {}).category || 'Other', specs: textToSpecs(g('specs')), variants };
}
async function saveProduct(form) {
  const pid = +form.dataset.pid;
  const btn = form.querySelector('[type=submit]'); btn.disabled = true;
  try {
    const p = await api('PUT', `/api/products/${pid}`, readProductForm(form));
    const i = S.review.products.findIndex(x => x.id === pid); S.review.products[i] = p;
    const typeOpts = form.querySelector('[name=type]').innerHTML.replace(/ selected/g, '');
    form.outerHTML = productForm(p, typeOpts);
    const st = $(`#ps-${pid}`); if (st) st.textContent = 'Saved';
    form.classList.remove('dirty');
  } catch (e) { toast(e.message); btn.disabled = false; }
}

/* ---------- admin: users ---------- */
async function viewUsers() {
  const us = await api('GET', '/api/users');
  $('#main').innerHTML = `<h1>Users</h1><p class="lede">Add each salesperson with an email and a starting password, and give it to them. They can change it under their name at the top right.</p>
  <form class="card upload" id="uform" style="margin-top:16px">
    <label class="field"><span>Name</span><input type="text" id="nu-name" required></label>
    <label class="field"><span>Email</span><input type="text" id="nu-email" required></label>
    <label class="field"><span>Starting password (8+)</span><input type="text" id="nu-pw" required value="${Math.random().toString(36).slice(2, 6) + '-' + Math.random().toString(36).slice(2, 6)}"></label>
    <label class="field"><span>Role</span><select id="nu-role">${opts([['sales', 'Sales'], ['admin', 'Admin (can upload and manage users)']], 'sales')}</select></label>
    <button class="btn primary" type="submit">Add user</button><div class="err" id="nu-err"></div>
  </form>
  <section class="card list" style="margin-top:16px">${us.map(u => `<div class="li"><div><b>${esc(u.name)}</b> ${u.active ? '' : '<span class="pill">Deactivated</span>'}<div class="muted small">${esc(u.email)} · ${u.role === 'admin' ? 'Admin' : 'Sales'}</div></div>
    <div class="row">${u.id === S.me.id ? '<span class="muted small">You</span>' : `
      <select data-urole="${u.id}" style="width:auto">${opts([['sales', 'Sales'], ['admin', 'Admin']], u.role)}</select>
      <button class="btn ghost" type="button" data-act="resetpw" data-id="${u.id}">Reset password</button>
      <button class="btn ghost" type="button" data-act="toggleuser" data-id="${u.id}" data-active="${u.active}">${u.active ? 'Deactivate' : 'Reactivate'}</button>`}</div></div>`).join('')}</section>`;
  $('#uform').onsubmit = async e => {
    e.preventDefault();
    try { await api('POST', '/api/users', { name: $('#nu-name').value, email: $('#nu-email').value, password: $('#nu-pw').value, role: $('#nu-role').value }); toast(`Added ${$('#nu-name').value}. Share the email and password with them.`); viewUsers(); }
    catch (err) { $('#nu-err').textContent = err.message; }
  };
}

/* ---------- admin: settings ---------- */
function viewSettings() {
  const st = S.me.settings;
  $('#main').innerHTML = `<h1>Settings</h1>
  <form class="card panel" id="setform" style="max-width:560px;margin-top:16px"><h2>Showroom details</h2><p class="muted small" style="margin:0">Shown on every deck.</p>
    <label class="field"><span>Showroom / dealer name</span><input type="text" id="st-dealer" value="${esc(st.dealer)}"></label>
    <label class="field"><span>Contact line (phone, email, address)</span><input type="text" id="st-contact" value="${esc(st.contact)}"></label>
    <button class="btn primary" type="submit">Save</button></form>
  <section class="card panel" style="max-width:560px;margin-top:16px"><h2>Backup</h2><p class="muted small" style="margin:0">Downloads the database and product photos as one zip. Keep a copy somewhere safe, for example once a week.</p>
    <a class="btn" href="/api/backup" style="align-self:flex-start">Download backup</a></section>`;
  $('#setform').onsubmit = async e => {
    e.preventDefault();
    try { await api('PUT', '/api/settings', { dealer: $('#st-dealer').value, contact: $('#st-contact').value }); S.me = await api('GET', '/api/me'); $('#dealer').textContent = S.me.settings.dealer || 'Bath Solution Studio'; toast('Saved'); }
    catch (err) { toast(err.message); }
  };
}

/* ---------- events ---------- */
const roomOf = el => S.project.rooms.find(r => r.id === el.dataset.room);
const setPath = (o, path, v) => { const k = path.split('.'); let t = o; k.slice(0, -1).forEach(x => t = t[x]); t[k[k.length - 1]] = v; };
function changed(r) { if (r && !r.edited) rebuild(r); else if (r) r.items = S.E.sortItems(r.items); saveSoon(); renderProject(); }
function saveRange() { store.set('bss.range', S.range); viewRange(); }

document.addEventListener('click', async e => {
  const nb = e.target.closest('[data-href]');
  if (nb) { location.hash = nb.dataset.href; return; }
  const t = e.target.closest('[data-act]'); if (!t || t.tagName === 'SELECT') return;
  const a = t.dataset.act, r = t.dataset.room && S.project ? roomOf(t) : null;
  try {
    if (a === 'logout') { await api('POST', '/api/logout'); S.me = null; showLogin(); }
    else if (a === 'newproject') await createProject();
    else if (a === 'delproject') { if (confirmBtn(t, 'Confirm delete')) { await api('DELETE', `/api/projects/${t.dataset.id}`); viewProjects(); } }
    else if (a === 'dupproject') { const p = await api('GET', `/api/projects/${t.dataset.id}`); const n = await api('POST', '/api/projects', { title: p.title + ' (copy)', customer: p.customer, data: p.data }); location.hash = `#/project/${n.id}`; }
    else if (a === 'series') { r.series = t.dataset.v; const f = finishesFor(r.brand, r.series); if (!f.includes(r.finish)) r.finish = f.includes('chrome') ? 'chrome' : f[0]; changed(r); }
    else if (a === 'tier' || a === 'finish') { r[a] = t.dataset.v; changed(r); }
    else if (a === 'acc') { r.acc[t.dataset.k] = Math.max(0, (r.acc[t.dataset.k] || 0) + +t.dataset.d); changed(r); }
    else if (a === 'qty') { const it = r.items.find(i => i.uid === t.dataset.uid); it.qty = Math.max(1, it.qty + +t.dataset.d); r.edited = true; changed(r); }
    else if (a === 'del') { r.items = r.items.filter(i => i.uid !== t.dataset.uid); r.edited = true; changed(r); }
    else if (a === 'rebuild') { rebuild(r); changed(r); }
    else if (a === 'rmroom') { if (confirmBtn(t, 'Confirm delete')) { S.project.rooms = S.project.rooms.filter(x => x !== r); changed(null); } }
    else if (a === 'dup') { const c = JSON.parse(JSON.stringify(r)); c.id = uid(); c.name = r.name + ' copy'; c.items.forEach(i => i.uid = uid()); S.project.rooms.splice(S.project.rooms.indexOf(r) + 1, 0, c); changed(null); }
    else if (a === 'addroom') { const last = S.project.rooms[S.project.rooms.length - 1]; S.project.rooms.push(newRoom(t.dataset.v, last ? { brand: last.brand, series: last.series, finish: last.finish, tier: last.tier } : {})); changed(null); }
    else if (a === 'pptsol') await pptSolution(t);
    else if (a === 'rlayout') { S.range.layout = t.dataset.v; saveRange(); }
    else if (a === 'rall') { S.range.exclude = []; saveRange(); }
    else if (a === 'pptrange') await pptRange(t);
    else if (a === 'publish') { const rep = $('#rv-replace') ? $('#rv-replace').checked : true; await api('POST', `/api/catalogs/${t.dataset.id}/publish`, { replace_previous: rep }); await loadCatalog(); toast('Published. The sales team can use it now.'); route(); }
    else if (a === 'unpublish') { await api('POST', `/api/catalogs/${t.dataset.id}/unpublish`); await loadCatalog(); toast('Unpublished'); route(); }
    else if (a === 'delcatalog') { if (confirmBtn(t, 'Confirm delete')) { await api('DELETE', `/api/catalogs/${t.dataset.id}`); await loadCatalog(); viewCatalogs(); } }
    else if (a === 'savecat') { await api('PATCH', `/api/catalogs/${t.dataset.id}`, { name: $('#rc-name').value, currency: $('#rc-cur').value, price_basis: $('#rc-basis').value }); toast('Saved'); }
    else if (a === 'addvariant') { const tb = t.closest('form').querySelector('tbody'); tb.insertAdjacentHTML('beforeend', variantRow({ art: '', finish: '', finish_key: 'chrome', price: null, flags: [] }, S.meta.finishes)); t.closest('form').classList.add('dirty'); }
    else if (a === 'delvariant') { const f = t.closest('form'); t.closest('tr').remove(); f.classList.add('dirty'); }
    else if (a === 'delproduct') { if (confirmBtn(t, 'Confirm delete')) { await api('DELETE', `/api/products/${t.dataset.pid}`); S.review.products = S.review.products.filter(p => p.id !== +t.dataset.pid); renderReview(); } }
    else if (a === 'addproduct') { const n = await api('POST', `/api/catalogs/${S.review.catalog.id}/products`, { name: 'New product', series: (S.review.series[0] || {}).name || '', type: 'other', category: 'Other', variants: [] }); S.review.q = 'New product'; await viewReview(S.review.catalog.id); toast('Added. Fill in the details and save.'); }
    else if (a === 'acceptflag') { await api('POST', `/api/variants/${t.dataset.vid}/accept`); const p = S.review.products.find(x => x.variants.some(v => v.id === +t.dataset.vid)); const v = p.variants.find(v => v.id === +t.dataset.vid); v.flags = []; t.closest('td').innerHTML = ''; toast('Warning cleared'); }
    else if (a === 'pickimg') { const inp = $('#imgpick'); inp.dataset.pid = t.dataset.pid; inp.value = ''; inp.click(); }
    else if (a === 'resetpw') { const pw = Math.random().toString(36).slice(2, 6) + '-' + Math.random().toString(36).slice(2, 6); if (confirmBtn(t, 'Confirm reset')) { await api('PATCH', `/api/users/${t.dataset.id}`, { password: pw }); t.closest('.li').querySelector('.muted').insertAdjacentHTML('beforeend', ` · New password: <b class="mono">${pw}</b>`); } }
    else if (a === 'toggleuser') { await api('PATCH', `/api/users/${t.dataset.id}`, { active: t.dataset.active !== '1' }); viewUsers(); }
  } catch (err) { toast(err.message); }
});
document.addEventListener('change', async e => {
  const t = e.target, d = t.dataset;
  try {
    if (t.id === 'imgpick') {
      const f = t.files[0]; if (!f) return;
      const fd = new FormData(); fd.append('file', f);
      const res = await api('POST', `/api/products/${d.pid}/image`, fd, true);
      const p = S.review.products.find(x => x.id === +d.pid); p.image = res.image; p.attributes.issues = (p.attributes.issues || []).filter(i => !i.startsWith('No product photo'));
      const ph = document.querySelector(`.ph[data-pid="${d.pid}"]`); if (ph) ph.innerHTML = `<img alt="" src="${esc(res.image)}"><span>Change photo</span>`;
      toast('Photo updated'); return;
    }
    if (t.closest('form.pform')) { t.closest('form.pform').classList.add('dirty'); return; }
    if (d.f && d.room && d.f !== 'name') {
      const r = roomOf(t); let v = t.value; if (/count|head/.test(d.f)) v = +v; setPath(r, d.f, v);
      if (d.f === 'brand') Object.assign(r, defaultsFor(v));
      changed(r);
    }
    else if (d.act === 'type') { const r = roomOf(t); const keep = { id: r.id, name: r.name === r.type ? t.value : r.name, brand: r.brand, series: r.series, finish: r.finish, tier: r.tier }; Object.assign(r, newRoom(t.value, keep)); changed(r); }
    else if (d.act === 'ifinish') { const r = roomOf(t); const i = r.items.findIndex(x => x.uid === d.uid); r.items[i] = S.E.refinish(r.items[i], t.value); r.edited = true; changed(r); }
    else if (d.act === 'swap' && t.value) { const r = roomOf(t); const i = r.items.findIndex(x => x.uid === d.uid); r.items[i] = S.E.swap(r.items[i], t.value); r.edited = true; changed(r); }
    else if (d.act === 'add' && t.value) { const r = roomOf(t); const it = S.E.item(S.E.byId[t.value], r.finish, 1, 'Added by hand'); if (it) r.items.push(it); r.edited = true; changed(r); }
    else if (d.r === 'brand') { const b = S.E.brandOf(t.value); Object.assign(S.range, { brand: b.name, series: b.series.map(s => s.name), exclude: [], title: `${b.name} collections` }); saveRange(); }
    else if (d.rlist) { const L = S.range[d.rlist]; S.range[d.rlist] = t.checked ? [...new Set([...L, t.value])] : L.filter(x => x !== t.value); saveRange(); }
    else if (d.rbool) { S.range[d.rbool] = t.checked; saveRange(); }
    else if (d.rx) { S.range.exclude = t.checked ? S.range.exclude.filter(x => x !== d.rx) : [...S.range.exclude, d.rx]; saveRange(); }
    else if (['brand', 'series', 'category'].includes(d.c)) { S.cat[d.c] = t.value; if (d.c === 'brand') S.cat.series = ''; viewCatalog(); }
    else if (t.id === 'rv-only') { S.review.only = t.checked; renderReview(); }
    else if (d.series) { await api('PATCH', `/api/series/${d.series}`, { style: t.value }); toast('Saved'); }
    else if (d.urole) { await api('PATCH', `/api/users/${d.urole}`, { role: t.value }); toast('Role changed'); }
  } catch (err) { toast(err.message); }
});
document.addEventListener('input', e => {
  const t = e.target, d = t.dataset;
  if (t.closest('form.pform')) { t.closest('form.pform').classList.add('dirty'); return; }
  if (d.p && S.project) { S.project[d.p] = t.value; saveSoon(); }
  else if (d.f === 'name' && S.project) { roomOf(t).name = t.value; saveSoon(); }
  else if (d.rt) { S.range[d.rt] = t.value; store.set('bss.range', S.range); }
  else if (d.c === 'q') { S.cat.q = t.value; const rows = catRows(); $('#c-tbl').innerHTML = catTable(rows); $('#c-count').textContent = rows.length + ' products'; }
  else if (t.id === 'rv-q') { S.review.q = t.value; clearTimeout(S.rq); S.rq = setTimeout(() => { renderReview(); const q = $('#rv-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }, 400); }
});
document.addEventListener('submit', e => {
  const f = e.target.closest('form.pform');
  if (f) { e.preventDefault(); saveProduct(f); }
});
window.addEventListener('beforeunload', e => { if (document.querySelector('form.pform.dirty')) { e.preventDefault(); e.returnValue = ''; } });

boot().catch(e => { $('#main').innerHTML = `<div class="empty">Could not reach the server: ${esc(e.message)}</div>`; });
})();

/* Curation engine: turns a room requirement into a list of products, using each
   product's normalised type. Works for any brand whose products have types set. */
(function (root) {
  const ROOM_PRESETS = {
    'Master bath': { basins: { count: 2, mount: 'standard' }, shower: { kind: 'conc_rain', head: 300, arm: 'wall' }, bath: 'none', bidet: 'spray', acc: { towel_rail: 1, towel_ring: 2, hook: 2, tp: 1, rack: 0, shelf: 1, mirror: 1 } },
    'Guest bath': { basins: { count: 1, mount: 'standard' }, shower: { kind: 'conc_hand', head: 250, arm: 'wall' }, bath: 'none', bidet: 'spray', acc: { towel_rail: 1, towel_ring: 1, hook: 1, tp: 1, rack: 0, shelf: 0, mirror: 0 } },
    'Kids bath': { basins: { count: 1, mount: 'standard' }, shower: { kind: 'exposed', head: 250, arm: 'wall' }, bath: 'exposed', bidet: 'spray', acc: { towel_rail: 1, towel_ring: 1, hook: 2, tp: 1, rack: 0, shelf: 0, mirror: 0 } },
    'Powder room': { basins: { count: 1, mount: 'vessel' }, shower: { kind: 'none', head: 250, arm: 'wall' }, bath: 'none', bidet: 'spray', acc: { towel_rail: 0, towel_ring: 1, hook: 0, tp: 1, rack: 0, shelf: 0, mirror: 0 } },
    'Custom': { basins: { count: 1, mount: 'standard' }, shower: { kind: 'none', head: 250, arm: 'wall' }, bath: 'none', bidet: 'none', acc: { towel_rail: 0, towel_ring: 0, hook: 0, tp: 0, rack: 0, shelf: 0, mirror: 0 } }
  };

  function make(catalog, meta) {
    const P = catalog.products;
    const FIN = meta.finishes;
    const TYPE_LABEL = Object.fromEntries(meta.types.map(t => [t.key, t.label]));
    const CAT_ORDER = meta.categories;
    const GROUP_OF = Object.fromEntries((meta.groups || []).flatMap(g => g.categories.map(c => [c, g.name])));
    const groupOf = c => GROUP_OF[c] || '';
    const catRank = c => { const i = CAT_ORDER.indexOf(c); return i < 0 ? 999 : i; };
    const sortItems = items => items.map((it, i) => [it, i]).sort((a, b) => catRank(a[0].category) - catRank(b[0].category) || a[1] - b[1]).map(x => x[0]);
    const byId = Object.fromEntries(P.map(p => [p.id, p]));
    const find = (brand, series, type) => P.find(p => p.brand === brand && p.series === series && p.type === type);
    const finishLabel = k => (FIN.find(f => f.key === k) || {}).label || k;
    const brandOf = name => catalog.brands.find(b => b.name === name);

    function pickVariant(prod, fkey, width) {
      let vs = prod.variants.filter(v => !width || !v.width_mm || v.width_mm === width);
      if (!vs.length) vs = prod.variants;
      let v = vs.find(v => v.finish_key === fkey), note = null;
      if (!v) {
        v = vs.find(v => v.finish_key === 'chrome') || vs[0];
        note = `Not offered in ${finishLabel(fkey).toLowerCase()}; ${v ? v.finish : 'another finish'} used.`;
      }
      return { v, note };
    }
    function item(prod, fkey, qty, why, opts = {}) {
      const { v, note } = pickVariant(prod, fkey, opts.width);
      if (!v) return null;
      return {
        uid: Math.random().toString(36).slice(2, 9), pid: prod.id, name: prod.name, category: prod.category, series: prod.series, brand: prod.brand,
        art: v.art, finish: v.finish, finish_key: v.finish_key, width_mm: v.width_mm, qty, price: v.price || 0, image: prod.image,
        why: why || '', flags: [...(v.flags || []), ...(note ? [note] : [])], fallback: !!note
      };
    }
    function buildRoom(r) {
      const B = r.brand, S = r.series, F = r.finish, T = r.tier || 'standard', out = [], warn = [];
      const has = type => !!find(B, S, type);
      const add = (type, qty, why, opts) => {
        const p = find(B, S, type);
        if (!p) { warn.push(`${S} has no ${(TYPE_LABEL[type] || type).toLowerCase()}.`); return null; }
        const it = qty > 0 ? item(p, F, qty, why, opts) : null;
        if (it) out.push(it);
        return p;
      };
      const b = r.basins || {};
      if (b.count > 0) {
        const n = b.count;
        let t = { standard: 'basin_std', raised: 'basin_mid', vessel: 'basin_tall', wall: 'basin_wall', '3hole': 'basin_3hole' }[b.mount] || 'basin_std';
        if (!has(t) && t !== 'basin_std') { warn.push(`${S} has no ${TYPE_LABEL[t].toLowerCase()}; using the standard basin mixer.`); t = 'basin_std'; }
        add(t, n, b.mount === 'vessel' ? 'Tall body for a countertop (vessel) basin' : b.mount === 'wall' ? 'Wall-mounted; rough part included' : n > 1 ? 'One per basin' : '');
        add('waste', n, 'Mixer ships without a waste plug');
        add('trap', n, 'Visible bottle trap matching the finish');
        if (t !== 'basin_wall') add('angle_valve', 2 * n, 'Hot and cold supply for the connecting hoses');
      }
      const sh = r.shower || {};
      const head = T === 'value' ? 250 : (sh.head || 250);
      const arm = sh.arm === 'ceiling' ? 'arm_ceiling' : 'arm_wall';
      const handKit = () => { add('hand_shower', 1, 'Hand shower'); add('shower_hose', 1, 'Shower hose'); add('hand_bracket', 1, 'Holds the hand shower'); };
      if (sh.kind === 'exposed') {
        if (T === 'premium' && has('shower_thermo_exposed')) add('shower_thermo_exposed', 1, 'Thermostatic, safety stop at 38°C');
        else if (T === 'premium' && has('shower_exposed_bar')) add('shower_exposed_bar', 1, 'Bar design');
        else add('shower_exposed', 1, 'Wall mixer with hose outlet');
        if (T === 'value' || !has('rail_set')) handKit(); else add('rail_set', 1, 'Rail, hand shower and hose');
      } else if (sh.kind === 'conc_hand') {
        add('conc_1f', 1, 'Concealed; rough part included');
        if (T === 'value' || !has('rail_set')) handKit(); else add('rail_set', 1, 'Height-adjustable hand shower on a rail');
      } else if (sh.kind === 'conc_rain' || sh.kind === 'thermo_rain') {
        if ((sh.kind === 'thermo_rain' || T === 'premium') && has('thermo_2f')) add('thermo_2f', 1, 'Thermostatic, 2 outlets: overhead + hand shower');
        else add('conc_2f_push', 1, '2 outlets: overhead + hand shower');
        add('head_' + head, 1, `${head} mm overhead shower`);
        add(arm, 1, 'Carries the overhead shower');
        if (has('hose_union_set')) add('hose_union_set', 1, 'Hand shower, hose and bracket on a wall outlet');
        else { add('hose_union', 1, 'Wall outlet for the hand shower'); handKit(); }
      }
      if (r.bath === 'exposed') {
        if (has('bath_exposed_set')) add('bath_exposed_set', 1, 'Wall mixer with hand shower set');
        else { add('bath_exposed', 1, 'Wall bath mixer'); handKit(); }
      } else if (r.bath === 'exposed_thermo') {
        if (has('bath_thermo_exposed')) { add('bath_thermo_exposed', 1, 'Thermostatic bath mixer'); handKit(); }
        else { warn.push(`${S} has no thermostatic bath mixer; using the single lever set.`); add('bath_exposed_set', 1, 'Wall mixer with hand shower set'); }
      } else if (r.bath === 'rim') add('bath_4hole', 1, 'Mounted on the bath rim, with hand shower');
      else if (r.bath === 'floor') add('bath_floor', 1, 'For a freestanding tub; rough part included');
      else if (r.bath === 'wall_spout') {
        add('conc_2f_rot', 1, 'Concealed; feeds spout and hand shower');
        add('bath_filler', 1, 'Wall spout over the tub');
        if (has('hose_union_set')) add('hose_union_set', 1, 'Hand shower at the tub'); else handKit();
      }
      if (r.bidet === 'spray') {
        const bs = add('bidet_spray', 1, 'Health faucet with holder');
        if (bs && !bs.variants.some(v => v.finish_key === F)) warn.push(`The health faucet set isn't made in ${finishLabel(F).toLowerCase()}. Choose the concealed bidet mixer to match the finish.`);
        add('angle_valve', 1, 'Supply valve for the spray set');
      } else if (r.bidet === 'concealed') add('bidet_concealed', 1, 'Hot/cold mixing; rough part included');
      const a = r.acc || {};
      if (a.towel_rail) add('towel_rail', a.towel_rail, '', { width: T === 'value' ? 500 : 650 });
      if (a.towel_ring) add('towel_ring', a.towel_ring, '');
      if (a.hook) {
        const dbl = a.hook > 1 && T !== 'value' && has('hook_double');
        add(dbl ? 'hook_double' : 'hook', dbl ? Math.ceil(a.hook / 2) : a.hook, '');
      }
      if (a.tp) add(T !== 'value' && has('tp_shelf') ? 'tp_shelf' : (has('tp_rigid') ? 'tp_rigid' : 'tp_swivel'), a.tp, '');
      if (a.rack) add('towel_rack', a.rack, '');
      if (a.shelf) add('shower_shelf', a.shelf, '');
      if (a.mirror) add('mirror', a.mirror, '');
      const merged = [];
      out.forEach(it => {
        const m = merged.find(x => x.art === it.art);
        if (m) { m.qty += it.qty; if (it.why && !m.why.includes(it.why)) m.why = m.why ? m.why + '; ' + it.why : it.why; }
        else merged.push(it);
      });
      return { items: sortItems(merged), warnings: [...new Set(warn)] };
    }
    function alternatives(it) {
      const cur = byId[it.pid];
      if (!cur) return [];
      return P.filter(p => p.category === cur.category && p.brand === cur.brand && p.id !== cur.id)
        .sort((x, y) => (x.series === cur.series ? -1 : 1) - (y.series === cur.series ? -1 : 1));
    }
    function swap(it, pid) { const n = item(byId[pid], it.finish_key, it.qty, '', { width: it.width_mm }); n.uid = it.uid; return n; }
    function refinish(it, fkey) { const n = item(byId[it.pid], fkey, it.qty, it.why, { width: it.width_mm }); n.uid = it.uid; return n; }
    function rangeGroups(o) {
      const brand = brandOf(o.brand);
      if (!brand) return [];
      return o.series.map(s => {
        const prods = P.filter(p => p.brand === o.brand && p.series === s && o.categories.includes(p.category) && !(o.exclude || []).includes(p.id))
          .map((p, i) => [p, i]).sort((a, b) => catRank(a[0].category) - catRank(b[0].category) || a[1] - b[1]).map(x => x[0])
          .map(p => {
            const vs = o.finishes.length ? p.variants.filter(v => o.finishes.includes(v.finish_key)) : p.variants;  // none ticked = every finish
            return {
              ...p, variants: vs.length ? vs : p.variants.slice(0, 1),
              specGroups: p.specs.filter(g => g.items.length),
              keySpecs: p.specs.flatMap(g => g.items).filter(t => /Outlet height|Projection|Flow rate|Diameter|Dimension|Length|Height|Installation depth|Roll width|Magnification|Size/i.test(t))
            };
          });
        const keys = [...new Set(prods.flatMap(p => p.variants.map(v => v.finish_key)))];
        const order = FIN.map(f => f.key).filter(k => keys.includes(k));
        const meta2 = brand.series.find(x => x.name === s);
        return { series: s, style: meta2 ? meta2.style : '', products: prods, finishes: order.map(k => ({ key: k, short: finishLabel(k) })) };
      }).filter(g => g.products.length);
    }
    return { buildRoom, alternatives, swap, refinish, item, byId, find, finishLabel, rangeGroups, brandOf, groupOf, sortItems, CAT_ORDER, FIN };
  }
  const api = { make, ROOM_PRESETS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.Engine = api;
})(typeof window !== 'undefined' ? window : globalThis);

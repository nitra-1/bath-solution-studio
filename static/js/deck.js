/* Deck builder for the sales tool. Works in the browser (window.DeckBuilder) and in Node (module.exports). */
(function (root) {
  const C = {
    ink: '22272B', sub: '5E676D', line: 'D9DEE0', mist: 'F1F4F4', panel: '1E3A3F', accent: '3E7C7F', white: 'FFFFFF', warn: 'B4532A'
  };
  const FONT = 'Calibri', HFONT = 'Calibri Light';
  const SW = { chrome: 'C9CED3', black: '232323', nickel: 'A9A498', gold: 'C8A96B', rosegold: 'B97E6B', gunmetal: '5B5E61', steel: 'B4B8BB', brass: '9C7A3C', white: 'F2F2F2', other: '9AA3A8' };
  const W = 13.333, H = 7.5;
  const SYM = { EUR: '€', USD: '$', GBP: '£', INR: '₹' };
  const fmt = (n, cur) => (SYM[cur] || (cur ? cur + ' ' : '')) + Number(n || 0).toLocaleString(cur === 'INR' ? 'en-IN' : 'en-IE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const eur = n => fmt(n, 'EUR');
  let money = eur;
  function pic(s, data, o) { if (data) s.addImage({ data, ...o }); }

  function footer(s, left, n) {
    s.addShape('line', { x: 0.5, y: 7.0, w: W - 1, h: 0, line: { color: C.line, width: 0.75 } });
    s.addText(left, { x: 0.5, y: 7.05, w: 9, h: 0.3, fontFace: FONT, fontSize: 9, color: C.sub, margin: 0 });
    if (n != null) s.addText(String(n), { x: W - 1.5, y: 7.05, w: 1, h: 0.3, fontFace: FONT, fontSize: 9, color: C.sub, align: 'right', margin: 0 });
  }
  function header(s, eyebrow, title, right) {
    s.addText(eyebrow.toUpperCase(), { x: 0.5, y: 0.35, w: 9, h: 0.3, fontFace: FONT, fontSize: 10, bold: true, color: C.accent, charSpacing: 2, margin: 0 });
    s.addText(title, { x: 0.5, y: 0.65, w: 9.5, h: 0.6, fontFace: HFONT, fontSize: 26, color: C.ink, margin: 0 });
    if (right) s.addText(right, { x: 8.3, y: 0.65, w: 4.55, h: 0.6, fontFace: FONT, fontSize: 12, color: C.sub, align: 'right', valign: 'bottom', margin: 0 });
  }
  function swatch(s, key, x, y, d) {
    s.addShape('ellipse', { x, y, w: d, h: d, fill: { color: SW[key] || 'CCCCCC' }, line: { color: 'FFFFFF', width: 0.5 } });
  }
  function cover(pptx, o) {
    const s = pptx.addSlide();
    s.background = { color: C.white };
    s.addShape('rect', { x: 0, y: 0, w: 5.4, h: H, fill: { color: C.panel }, line: { color: C.panel } });
    s.addText((o.eyebrow || '').toUpperCase(), { x: 0.6, y: 0.8, w: 4.4, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: 'A9C9C8', charSpacing: 3, margin: 0 });
    s.addText(o.title, { x: 0.6, y: 1.25, w: 4.4, h: 2.2, fontFace: HFONT, fontSize: 36, color: C.white, valign: 'top', margin: 0 });
    const lines = (o.lines || []).filter(Boolean).map((l, i) => ({ text: l, options: { breakLine: true, fontSize: i === 0 ? 14 : 12, color: i === 0 ? C.white : 'C9D6D6' } }));
    if (lines.length) s.addText(lines, { x: 0.6, y: 4.6, w: 4.4, h: 1.6, fontFace: FONT, valign: 'bottom', margin: 0, paraSpaceAfter: 4 });
    s.addText(o.date || '', { x: 0.6, y: 6.6, w: 4.4, h: 0.3, fontFace: FONT, fontSize: 10, color: 'A9C9C8', margin: 0 });
    const imgs = (o.images || []).slice(0, 4);
    const pos = [[6.0, 0.7, 3.3, 3.0], [9.5, 0.7, 3.3, 3.0], [6.0, 3.9, 3.3, 3.0], [9.5, 3.9, 3.3, 3.0]];
    imgs.forEach((im, i) => {
      const [x, y, w, h] = pos[i];
      s.addShape('rect', { x, y, w, h, fill: { color: C.mist }, line: { color: C.mist } });
      pic(s, im, { x: x + 0.3, y: y + 0.3, w: w - 0.6, h: h - 0.6, sizing: { type: 'contain', w: w - 0.6, h: h - 0.6 } });
    });
    return s;
  }

  /* ---------- Customer solution deck ---------- */
  function buildSolution(pptx, proj, img) {
    pptx.layout = 'LAYOUT_WIDE';
    pptx.title = proj.title || 'Bathroom solution';
    money = n => fmt(n, proj.currency || 'EUR');
    const priceNote = proj.priceNote || 'Prices excl. VAT';
    let n = 1;
    const foot = `${proj.dealer || ''}${proj.dealer ? '  ·  ' : ''}${proj.customer || ''}  ·  ${priceNote}`;
    const allItems = proj.rooms.flatMap(r => r.items);
    cover(pptx, {
      eyebrow: 'Bath & sanitary proposal', title: proj.title || 'Bathroom solution',
      lines: [proj.customer && `Prepared for ${proj.customer}`, proj.site, proj.salesperson && `Prepared by ${proj.salesperson}${proj.dealer ? ', ' + proj.dealer : ''}`],
      date: proj.date, images: [...new Set([...allItems].sort((a, b) => b.price - a.price).map(i => i.image))].slice(0, 4).map(img)
    });
    n++;
    // Overview
    {
      const s = pptx.addSlide();
      header(s, 'Overview', 'Rooms in this proposal', `${proj.rooms.length} rooms · ${allItems.reduce((a, i) => a + i.qty, 0)} items`);
      const rows = [[
        { text: 'Room', options: { bold: true, color: C.sub } }, { text: 'Collection', options: { bold: true, color: C.sub } },
        { text: 'Finish', options: { bold: true, color: C.sub } }, { text: 'Items', options: { bold: true, color: C.sub, align: 'right' } },
        { text: 'Subtotal', options: { bold: true, color: C.sub, align: 'right' } }]];
      let grand = 0;
      proj.rooms.forEach(r => {
        const t = r.items.reduce((a, i) => a + i.qty * i.price, 0); grand += t;
        rows.push([r.name, `${r.brand} ${r.series} · ${r.style}`, r.finishLabel, { text: String(r.items.reduce((a, i) => a + i.qty, 0)), options: { align: 'right' } }, { text: money(t), options: { align: 'right' } }]);
      });
      rows.push([{ text: 'Total', options: { bold: true } }, '', '', '', { text: money(grand), options: { bold: true, align: 'right' } }]);
      s.addTable(rows, { x: 0.5, y: 1.6, w: W - 1, colW: [2.8, 3.8, 2.6, 1.0, 2.13], fontFace: FONT, fontSize: 13, color: C.ink, border: { type: 'solid', pt: 0.5, color: C.line }, rowH: 0.45, valign: 'middle' });
      if (proj.notes) s.addText([{ text: 'Requirement notes  ', options: { bold: true, color: C.accent } }, { text: proj.notes }], { x: 0.5, y: 5.6, w: W - 1, h: 1.1, fontFace: FONT, fontSize: 11, color: C.sub, valign: 'top', margin: 0 });
      footer(s, foot, n++);
    }
    // Room slides: main products first, then accessories, each on their own slide(s)
    const groupOf = proj.groupOf || (() => '');
    const splitByGroup = items => {
      const out = [];
      items.forEach(i => { const g = groupOf(i.category); let e = out.find(x => x.group === g); if (!e) out.push(e = { group: g, items: [] }); e.items.push(i); });
      return out;
    };
    proj.rooms.forEach(r => {
      const per = 8;
      const parts = splitByGroup(r.items);
      if (!parts.length) parts.push({ group: '', items: [] });
      const t = r.items.reduce((a, i) => a + i.qty * i.price, 0);
      parts.forEach(part => {
        const pages = Math.max(1, Math.ceil(part.items.length / per));
        for (let p = 0; p < pages; p++) {
          const s = pptx.addSlide();
          const chunk = part.items.slice(p * per, p * per + per);
          const title = r.name + (part.group && parts.length > 1 ? `  ·  ${part.group}` : '') + (p ? ' (continued)' : '');
          header(s, `${r.brand} ${r.series}  ·  ${r.finishLabel}`, title, part === parts[0] && !p ? (r.brief || '') : '');
          const cw = 2.95, ch = 2.62, gx = 0.17, gy = 0.2, x0 = 0.5, y0 = 1.55;
          chunk.forEach((it, i) => {
            const cx = x0 + (i % 4) * (cw + gx), cy = y0 + Math.floor(i / 4) * (ch + gy);
            s.addShape('rect', { x: cx, y: cy, w: cw, h: ch, fill: { color: C.white }, line: { color: C.line, width: 0.75 } });
            s.addShape('rect', { x: cx, y: cy, w: cw, h: 1.25, fill: { color: C.mist }, line: { color: C.mist } });
            pic(s, img(it.image), { x: cx + 0.6, y: cy + 0.08, w: cw - 1.2, h: 1.09, sizing: { type: 'contain', w: cw - 1.2, h: 1.09 } });
            if (it.qty > 1) s.addText('×' + it.qty, { x: cx + cw - 0.62, y: cy + 0.08, w: 0.52, h: 0.28, fontFace: FONT, fontSize: 10, bold: true, color: C.white, fill: { color: C.accent }, align: 'center', margin: 0 });
            s.addText([
              { text: (it.category || '').toUpperCase(), options: { fontSize: 7.5, bold: true, color: C.accent, charSpacing: 1, breakLine: true } },
              { text: it.name, options: { fontSize: 11, bold: true, color: C.ink, breakLine: true } },
              { text: it.art + '  ·  ' + it.finish, options: { fontSize: 9, color: C.sub, breakLine: true } },
              { text: it.why || '', options: { fontSize: 9, italic: true, color: C.accent } }
            ], { x: cx + 0.12, y: cy + 1.3, w: cw - 0.24, h: 0.97, fontFace: FONT, valign: 'top', margin: 0, paraSpaceAfter: 2 });
            s.addText(money(it.qty * it.price), { x: cx + 0.12, y: cy + ch - 0.36, w: cw - 0.24, h: 0.28, fontFace: FONT, fontSize: 11, bold: true, color: C.ink, align: 'right', margin: 0 });
          });
          s.addText(`Room subtotal  ${money(t)}`, { x: W - 4.5, y: 0.3, w: 4, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: C.ink, align: 'right', margin: 0 });
          footer(s, foot, n++);
        }
      });
    });
    // Bill of quantities, grouped by room, then main products / accessories
    const lines = [];
    proj.rooms.forEach(r => {
      lines.push({ room: r.name });
      splitByGroup(r.items).forEach(part => {
        if (part.group) lines.push({ grp: part.group });
        part.items.forEach(i => lines.push(i));
      });
      lines.push({ sub: r.items.reduce((a, i) => a + i.qty * i.price, 0) });
    });
    const pages = Math.ceil(lines.length / 14); const per = Math.ceil(lines.length / pages);
    for (let p = 0; p < pages; p++) {
      const s = pptx.addSlide();
      header(s, 'Bill of quantities', 'Price summary' + (pages > 1 ? ` (${p + 1}/${pages})` : ''), priceNote);
      const head = ['Article no.', 'Description', 'Finish', 'Qty', 'Unit', 'Total'].map((t, i) => ({ text: t, options: { bold: true, color: C.sub, align: i >= 3 ? 'right' : 'left' } }));
      const rows = [head];
      lines.slice(p * per, p * per + per).forEach(l => {
        if (l.room) rows.push([{ text: l.room, options: { bold: true, color: C.accent, colspan: 6 } }]);
        else if (l.grp) rows.push([{ text: l.grp, options: { italic: true, color: C.sub, colspan: 6 } }]);
        else if (l.sub != null) rows.push([{ text: 'Subtotal', options: { colspan: 5, align: 'right', color: C.sub } }, { text: money(l.sub), options: { bold: true, align: 'right' } }]);
        else rows.push([l.art, l.name, l.finish, { text: String(l.qty), options: { align: 'right' } }, { text: money(l.price), options: { align: 'right' } }, { text: money(l.qty * l.price), options: { align: 'right' } }]);
      });
      if (p === pages - 1) {
        const g = allItems.reduce((a, i) => a + i.qty * i.price, 0);
        rows.push([{ text: 'Grand total', options: { colspan: 5, align: 'right', bold: true } }, { text: money(g), options: { bold: true, align: 'right' } }]);
      }
      s.addTable(rows, { x: 0.5, y: 1.5, w: W - 1, colW: [1.7, 4.9, 2.6, 0.6, 1.25, 1.28], fontFace: FONT, fontSize: 10.5, color: C.ink, border: { type: 'solid', pt: 0.5, color: C.line }, rowH: 0.34, valign: 'middle' });
      footer(s, foot, n++);
    }
    // Notes
    {
      const s = pptx.addSlide();
      header(s, 'Notes', 'Pricing and ordering notes');
      const flagged = allItems.filter(i => i.flags && i.flags.length);
      const pts = [
        `${priceNote}. Source: ${proj.sources || 'brand price lists'}.`,
        'Packaging, shipping and installation are not included.',
        'Concealed mixers include the rough part (in-wall body). Check installation depths with the plumber before tiling.',
        'Waste plugs, bottle traps and angle valves are listed as separate items where the mixer needs them.',
        ...[...new Map(flagged.map(i => [i.art, `${i.art} (${i.name}): ${i.flags.join(' ')}`])).values()]
      ];
      s.addText(pts.map(t => ({ text: t, options: { bullet: { indent: 14 }, breakLine: true } })), { x: 0.5, y: 1.6, w: W - 1, h: 4.9, fontFace: FONT, fontSize: 13, color: C.ink, valign: 'top', paraSpaceAfter: 8, margin: 0 });
      footer(s, foot, n++);
    }
    return pptx;
  }

  /* ---------- Brand range deck ---------- */
  function buildRange(pptx, sel, img) {
    pptx.layout = 'LAYOUT_WIDE';
    pptx.title = sel.title;
    money = n => fmt(n, sel.currency || 'EUR');
    let n = 1;
    const foot = `${sel.dealer || ''}${sel.dealer ? '  ·  ' : ''}${sel.brand} ${sel.catalog}${sel.showPrices ? '  ·  ' + (sel.priceNote || 'Prices excl. VAT') : ''}`;
    cover(pptx, {
      eyebrow: `${sel.brand} product range`, title: sel.title,
      lines: [sel.recipient && `Prepared for ${sel.recipient}`, `${sel.groups.reduce((a, g) => a + g.products.length, 0)} products · ${sel.groups.map(g => g.series).join(', ')}`, sel.salesperson && `Prepared by ${sel.salesperson}${sel.dealer ? ', ' + sel.dealer : ''}`],
      date: sel.date, images: (sel.groups.length > 1 ? sel.groups.flatMap(g => g.products.slice(0, 2)) : sel.groups[0].products.slice(0, 4)).map(p => img(p.image)).slice(0, 4)
    });
    n++;
    sel.groups.forEach(g => {
      // series divider
      const d = pptx.addSlide();
      d.background = { color: C.mist };
      d.addText(sel.brand.toUpperCase(), { x: 0.8, y: 1.6, w: 6, h: 0.35, fontFace: FONT, fontSize: 12, bold: true, color: C.accent, charSpacing: 3, margin: 0 });
      d.addText(g.series, { x: 0.8, y: 2.0, w: 6.5, h: 1.2, fontFace: HFONT, fontSize: 60, color: C.ink, margin: 0 });
      d.addText(`${g.style}  ·  ${g.products.length} products`, { x: 0.8, y: 3.25, w: 6.5, h: 0.4, fontFace: FONT, fontSize: 16, color: C.sub, margin: 0 });
      const groupOf = sel.groupOf || (() => '');
      const parts = [];
      g.products.forEach(p => { const k = groupOf(p.category); let e = parts.find(x => x.group === k); if (!e) parts.push(e = { group: k, products: [] }); e.products.push(p); });
      d.addText(parts.map(pt => ({ text: (pt.group ? pt.group + ':  ' : '') + [...new Set(pt.products.map(p => p.category))].join(' · '), options: { breakLine: true } })),
        { x: 0.8, y: 3.8, w: 6.5, h: 1.0, fontFace: FONT, fontSize: 12, color: C.sub, valign: 'top', margin: 0, paraSpaceAfter: 4 });
      d.addText('FINISHES', { x: 0.8, y: 5.0, w: 3, h: 0.3, fontFace: FONT, fontSize: 10, bold: true, color: C.sub, charSpacing: 2, margin: 0 });
      g.finishes.forEach((f, i) => {
        const x = 0.8 + i * 1.05;
        swatch(d, f.key, x, 5.4, 0.42);
        d.addText(f.short, { x: x - 0.25, y: 5.88, w: 0.92, h: 0.4, fontFace: FONT, fontSize: 9, color: C.sub, align: 'center', margin: 0 });
      });
      const hero = parts[0].products.slice(0, 4);
      hero.forEach((p, i) => {
        const x = 7.6 + (i % 2) * 2.75, y = 0.9 + Math.floor(i / 2) * 2.95;
        d.addShape('rect', { x, y, w: 2.6, h: 2.8, fill: { color: C.white }, line: { color: C.white } });
        pic(d, img(p.image), { x: x + 0.25, y: y + 0.25, w: 2.1, h: 2.3, sizing: { type: 'contain', w: 2.1, h: 2.3 } });
      });
      n++;
      parts.forEach(part => {
        if (parts.length > 1 && part.group) {
          // group divider, e.g. "TEVEO · Accessories"
          const gd = pptx.addSlide();
          gd.background = { color: C.mist };
          gd.addText(`${sel.brand} ${g.series}`.toUpperCase(), { x: 0.8, y: 2.6, w: 8, h: 0.35, fontFace: FONT, fontSize: 12, bold: true, color: C.accent, charSpacing: 3, margin: 0 });
          gd.addText(part.group, { x: 0.8, y: 3.0, w: 11, h: 0.9, fontFace: HFONT, fontSize: 40, color: C.ink, margin: 0 });
          gd.addText([...new Set(part.products.map(p => p.category))].join('   ·   ') + `   ·   ${part.products.length} products`, { x: 0.8, y: 3.95, w: 11.5, h: 0.5, fontFace: FONT, fontSize: 14, color: C.sub, margin: 0 });
          n++;
        }
      if (sel.layout === 'grid') {
        // overview: up to 6 per slide; each category starts on its own slide
        const per = 6;
        const byCat = [];
        part.products.forEach(p => { let e = byCat.find(x => x.cat === p.category); if (!e) byCat.push(e = { cat: p.category, list: [] }); e.list.push(p); });
        byCat.forEach(({ cat, list }) => { for (let p = 0; p < Math.ceil(list.length / per); p++) {
          const s = pptx.addSlide();
          const chunk = list.slice(p * per, p * per + per);
          header(s, `${sel.brand} ${g.series}${part.group ? '  ·  ' + part.group : ''}`, cat + (p ? ' (continued)' : ''));
          const cw = 3.98, ch = 2.62, gx = 0.18, gy = 0.2;
          chunk.forEach((pr, i) => {
            const cx = 0.5 + (i % 3) * (cw + gx), cy = 1.55 + Math.floor(i / 3) * (ch + gy);
            s.addShape('rect', { x: cx, y: cy, w: cw, h: ch, fill: { color: C.white }, line: { color: C.line, width: 0.75 } });
            s.addShape('rect', { x: cx, y: cy, w: 1.7, h: ch, fill: { color: C.mist }, line: { color: C.mist } });
            pic(s, img(pr.image), { x: cx + 0.12, y: cy + 0.2, w: 1.46, h: ch - 0.4, sizing: { type: 'contain', w: 1.46, h: ch - 0.4 } });
            const base = pr.variants[0];
            const minP = Math.min(...pr.variants.map(v => v.price));
            s.addText([
              { text: pr.category.toUpperCase(), options: { fontSize: 8, bold: true, color: C.accent, charSpacing: 1, breakLine: true } },
              { text: pr.name, options: { fontSize: 12, bold: true, color: C.ink, breakLine: true } },
              { text: pr.keySpecs.slice(0, 3).join('\n'), options: { fontSize: 9, color: C.sub, breakLine: true } },
              { text: 'Art. ' + base.art + (pr.variants.length > 1 ? `  +${pr.variants.length - 1} finishes` : ''), options: { fontSize: 9, color: C.sub } }
            ], { x: cx + 1.82, y: cy + 0.15, w: cw - 1.95, h: ch - 0.75, fontFace: FONT, valign: 'top', margin: 0, paraSpaceAfter: 3 });
            [...new Set(pr.variants.map(v => v.finish_key))].forEach((k2, k) => swatch(s, k2, cx + 1.82 + k * 0.27, cy + ch - 0.5, 0.2));
            if (sel.showPrices) s.addText('from ' + money(minP), { x: cx + 1.82, y: cy + ch - 0.32, w: cw - 1.95, h: 0.24, fontFace: FONT, fontSize: 10, bold: true, color: C.ink, align: 'right', margin: 0 });
          });
          footer(s, foot, n++);
        } });
      } else {
        part.products.forEach(pr => {
          const s = pptx.addSlide();
          s.addShape('rect', { x: 0, y: 0, w: 5.2, h: 7.0, fill: { color: C.mist }, line: { color: C.mist } });
          pic(s, img(pr.image), { x: 0.6, y: 0.8, w: 4.0, h: 5.4, sizing: { type: 'contain', w: 4.0, h: 5.4 } });
          s.addText(`${sel.brand} ${g.series}  ·  ${pr.category}`.toUpperCase(), { x: 5.7, y: 0.5, w: 7.1, h: 0.3, fontFace: FONT, fontSize: 10, bold: true, color: C.accent, charSpacing: 2, margin: 0 });
          s.addText(pr.name, { x: 5.7, y: 0.85, w: 7.1, h: 0.9, fontFace: HFONT, fontSize: 24, color: C.ink, valign: 'top', margin: 0 });
          const specLines = pr.specGroups.flatMap(gp => [
            ...(gp.group ? [{ text: gp.group, options: { bold: true, color: C.ink, breakLine: true } }] : []),
            ...gp.items.map(t => ({ text: t, options: { bullet: { indent: 12 }, breakLine: true } }))
          ]);
          const rowsN = pr.variants.length;
          const tableH = 0.32 * (rowsN + 1);
          const specH = 6.75 - 1.85 - tableH - 0.3;
          s.addText(specLines, { x: 5.7, y: 1.85, w: 7.1, h: specH, fontFace: FONT, fontSize: specLines.length > 12 ? 10.5 : 13, color: C.sub, valign: 'top', margin: 0, paraSpaceAfter: 3 });
          const hasW = pr.variants.some(v => v.width_mm);
          const cols = [['', 0.4], ['Finish', hasW ? 2.9 : 3.5], ...(hasW ? [['Width', 0.9]] : []), ['Article no.', hasW ? 1.7 : 2.0], ...(sel.showPrices ? [['Price', 1.2]] : [])];
          const used = cols.reduce((a, c) => a + c[1], 0); cols[1][1] += 7.1 - used;
          const head = cols.map((c, i) => ({ text: c[0], options: { bold: true, color: C.sub, align: c[0] === 'Price' ? 'right' : 'left' } }));
          const rows = [head, ...pr.variants.map(v => ['', v.finish, ...(hasW ? [v.width_mm ? v.width_mm + ' mm' : ''] : []), v.art, ...(sel.showPrices ? [{ text: money(v.price), options: { align: 'right' } }] : [])])];
          const ty = 6.75 - tableH;
          s.addTable(rows, { x: 5.7, y: ty, w: 7.1, colW: cols.map(c => c[1]), fontFace: FONT, fontSize: 10, color: C.ink, border: { type: 'solid', pt: 0.5, color: C.line }, rowH: 0.32, valign: 'middle' });
          pr.variants.forEach((v, k) => swatch(s, v.finish_key, 5.8, ty + 0.32 * (k + 1) + 0.07, 0.18));
          footer(s, foot, n++);
        });
      }
      });
    });
    // closing
    const s = pptx.addSlide();
    s.background = { color: C.panel };
    s.addText('Thank you', { x: 0.8, y: 2.6, w: 8, h: 1, fontFace: HFONT, fontSize: 44, color: C.white, margin: 0 });
    s.addText([sel.salesperson, sel.dealer, sel.contact].filter(Boolean).join('\n'), { x: 0.8, y: 3.7, w: 8, h: 1.5, fontFace: FONT, fontSize: 14, color: 'C9D6D6', valign: 'top', margin: 0 });
    s.addText(`Product data: ${sel.brand} ${sel.catalog}. Subject to model changes; errors and misprints excepted.`, { x: 0.8, y: 6.6, w: 11, h: 0.3, fontFace: FONT, fontSize: 9, color: 'A9C9C8', margin: 0 });
    return pptx;
  }

  const api = { buildSolution, buildRange, eur, fmt, SW };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.DeckBuilder = api;
})(typeof window !== 'undefined' ? window : globalThis);

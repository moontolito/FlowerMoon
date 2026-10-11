/* FlowerMoon Transport — browser client. All engineering logic stays on the server. */
(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const fmt = (value, digits = 1) => Number(value).toFixed(digits);
  const g = (value) => String(Number(Number(value).toPrecision(12)));

  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === 'class') node.className = value;
      else if (key === 'text') node.textContent = value;
      else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? '' : value);
    }
    for (const child of children.flat(Infinity)) {
      if (child !== null && child !== undefined && child !== false) node.append(child);
    }
    return node;
  }

  // ----- server ----------------------------------------------------------
  let busy = 0;
  function setBusy(delta) {
    busy = Math.max(0, busy + delta);
    $('#progress').hidden = busy === 0;
  }

  async function api(method, url, body, { quiet = false, raw = false } = {}) {
    if (!quiet) setBusy(1);
    try {
      const response = await fetch(url, {
        method,
        headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: 'same-origin',
      });
      if (!response.ok) {
        let message = `Request failed (${response.status}).`;
        try { message = (await response.json()).detail || message; } catch (_) { /* not JSON */ }
        throw new Error(typeof message === 'string' ? message : 'Invalid input.');
      }
      return raw ? response : response.json();
    } finally {
      if (!quiet) setBusy(-1);
    }
  }

  function setStatus(text, isError = false) {
    const node = $('#status');
    node.textContent = text || '';
    node.classList.toggle('error', isError);
  }

  async function run(task) {
    try {
      return await task();
    } catch (error) {
      setStatus(error.message, true);
      return undefined;
    }
  }

  // ----- state -----------------------------------------------------------
  let S = null;            // server snapshot
  let site = null;         // site & environment view
  let panel = 'route';
  let pick = 'destination';
  const local = { origin: { name: '', coords: '' }, destination: { name: '', coords: '' } };

  function apply(snapshot) {
    S = snapshot;
    for (const target of ['origin', 'destination']) {
      local[target] = { name: S[target].name, coords: S[target].coords };
      const input = $(`#${target}-input`);
      if (document.activeElement !== input) input.value = S[target].name;
      $(`#${target}-coords`).textContent = S[target].coords ? S[target].coords : 'No point selected';
    }
    const p = S.product;
    $('#product-name').textContent = p.name;
    $('#product-dims').textContent = `${g(p.length)} × ${g(p.width)} × ${g(p.height)} m  ·  ${g(p.weight)} t  ·  ${p.quantity} unit${p.quantity === 1 ? '' : 's'}`;
    $('#profile-summary').textContent = S.profileSummary;
    for (const select of $$('.preset-select')) {
      select.replaceChildren(
        el('option', { value: '', text: S.active ? 'Choose a preset…' : 'No compatible vehicle', disabled: true }),
        ...S.presets.map((v) => el('option', { value: v.id, text: v.title }))
      );
      select.value = S.active ? S.active.vehicle.id : '';
    }
    for (const box of $$('.truck')) drawTruck(box, box.classList.contains('truck-compact'));
    renderAdjust();
    renderResults();
    renderMap();
    setStatus(S.status);
    $('#calculate').disabled = !S.active;
  }

  async function refresh() {
    apply(await api('GET', '/api/state'));
  }

  // ----- vehicle ---------------------------------------------------------
  function drawTruck(box, compact) {
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('viewBox', compact ? '0 20 300 80' : '0 0 300 145');
    const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const add = (tag, attrs, text) => {
      const node = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      if (text) node.textContent = text;
      svg.append(node);
    };
    add('rect', { x: 42, y: 44, width: 184, height: 36, fill: css('--selection'), stroke: css('--primary'), 'stroke-width': 2 });
    add('polygon', { points: '230,59 260,59 277,77 277,93 230,93', fill: css('--primary') });
    add('rect', { x: 241, y: 64, width: 15, height: 12, fill: css('--surface') });
    add('line', { x1: 34, y1: 87, x2: 278, y2: 87, stroke: css('--secondary'), 'stroke-width': 3 });
    for (const x of [61, 82, 200, 219, 257]) add('circle', { cx: x, cy: 92, r: 6, fill: css('--text'), stroke: css('--surface'), 'stroke-width': 2 });
    if (S.active) {
      const d = S.active.loaded;
      add('text', { x: 134, y: 67, 'text-anchor': 'middle', fill: css('--primary'), 'font-weight': 700, 'font-size': 13 }, `${g(d.weight)} t`);
      if (!compact) {
        add('line', { x1: 35, y1: 118, x2: 278, y2: 118, stroke: css('--secondary') });
        add('text', { x: 157, y: 137, 'text-anchor': 'middle', fill: css('--secondary'), 'font-size': 11 }, `L ${g(d.length)} m  ·  W ${g(d.width)} m`);
        add('line', { x1: 22, y1: 42, x2: 22, y2: 97, stroke: css('--primary') });
        add('text', { x: 150, y: 27, 'text-anchor': 'middle', fill: css('--primary'), 'font-weight': 700, 'font-size': 11 }, `Total height ${g(d.height)} m`);
      }
    }
    box.replaceChildren(svg);
  }

  const SLIDERS = [
    ['length', 'Length', 'm', 1, 30], ['width', 'Width', 'm', 1, 6], ['height', 'Height', 'm', 1, 6],
    ['weight', 'Total weight', 't', 1, 80], ['axle_load', 'Maximum axle load', 't', 1, 20], ['axle_count', 'Number of axles', '', 2, 12],
  ];

  function renderAdjust() {
    const box = $('#vehicle-adjust');
    if (!S.active) {
      box.replaceChildren(
        el('p', { class: 'muted pre', text: S.profileSummary }),
        el('button', { type: 'button', class: 'btn btn-block', text: 'Recommend for product', onclick: () => run(async () => apply(await api('POST', '/api/vehicle/recommend'))) })
      );
      return;
    }
    const rows = SLIDERS.map(([key, label, unit, lo, hi]) => {
      const current = S.active.loaded[key];
      const step = key === 'axle_count' ? 1 : 0.01;
      const number = el('input', { type: 'number', step, min: 0, value: g(current), 'data-key': key, 'aria-label': label });
      const range = el('input', { type: 'range', min: lo, max: Math.max(hi, current), step, value: current, 'aria-label': label + ' slider' });
      range.addEventListener('input', () => { number.value = g(range.value); });
      number.addEventListener('input', () => { range.value = number.value; });
      number.addEventListener('keydown', (e) => { if (e.key === 'Enter') applyAdjust(); });
      return el('div', { class: 'adjust-row' }, el('span', { class: 'muted', text: label }), number, el('span', { class: 'muted', text: unit }), range);
    });
    box.replaceChildren(
      el('p', { class: 'muted', text: 'Total dimensions, including the product.' }),
      ...rows,
      el('button', { type: 'button', class: 'btn btn-block', style: 'margin-top:12px', text: 'Apply adjustments', onclick: applyAdjust }),
      el('button', { type: 'button', class: 'btn btn-block', style: 'margin-top:8px', text: 'Reset recommendation for product', onclick: () => run(async () => apply(await api('POST', '/api/vehicle/recommend'))) })
    );
  }

  function adjustValues() {
    return Object.fromEntries($$('#vehicle-adjust input[type="number"]').map((input) => [input.dataset.key, input.value]));
  }

  function adjustPending() {
    if (panel !== 'vehicle' || !S.active) return false;
    return Object.entries(adjustValues()).some(([key, value]) => Math.abs(Number(value) - S.active.loaded[key]) > 1e-5);
  }

  function applyAdjust() {
    run(async () => apply(await api('POST', '/api/vehicle/adjust', adjustValues())));
  }

  function setPanel(name) {
    panel = name;
    for (const tab of $$('.tab')) tab.setAttribute('aria-selected', String(tab.dataset.panel === name));
    $('#panel-route').hidden = name !== 'route';
    $('#panel-vehicle').hidden = name !== 'vehicle';
  }

  // ----- addresses -------------------------------------------------------
  function addressField(target) {
    const input = $(`#${target}-input`);
    const list = $(`#${target}-list`);
    let timer = null;
    let serial = 0;
    let rows = [];
    let index = -1;

    const close = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); index = -1; };
    const highlight = () => $$('li', list).forEach((li, i) => li.setAttribute('aria-selected', String(i === index)));
    const choose = (row) => {
      close();
      input.value = row.label;
      local[target] = { name: row.label, coords: `${row.lat.toFixed(7)}, ${row.lon.toFixed(7)}` };
      saveLocations(target === 'destination' ? 'Address selected. Destination data will load automatically.' : 'Departure selected.', true);
    };
    const show = (items, message) => {
      rows = items;
      index = -1;
      list.replaceChildren(...(items.length
        ? items.map((row, i) => el('li', { role: 'option', id: `${target}-opt-${i}`, text: row.label, onmousedown: (e) => { e.preventDefault(); choose(row); } }))
        : [el('li', { class: 'empty', text: message })]));
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    };

    input.addEventListener('input', () => {
      local[target] = { name: input.value, coords: '' };  // a typed name is not a location yet
      $(`#${target}-coords`).textContent = 'Choose a suggestion or click on the map';
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 3) { close(); return; }
      const mine = ++serial;
      timer = setTimeout(async () => {
        try {
          const items = await api('GET', '/api/places?q=' + encodeURIComponent(query), undefined, { quiet: true });
          if (mine === serial && document.activeElement === input) show(items, 'No results. Enter coordinates or choose a point on the map.');
        } catch (error) {
          if (mine === serial) show([], error.message);
        }
      }, 650);
    });
    input.addEventListener('keydown', (e) => {
      if (list.hidden || !rows.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        index = (index + (e.key === 'ArrowDown' ? 1 : rows.length - 1)) % rows.length;
        highlight();
        input.setAttribute('aria-activedescendant', `${target}-opt-${index}`);
      } else if (e.key === 'Enter' && index >= 0) {
        e.preventDefault();
        choose(rows[index]);
      } else if (e.key === 'Escape') {
        close();
      }
    });
    input.addEventListener('blur', () => setTimeout(close, 120));
  }

  async function saveLocations(message, fly = false) {
    return run(async () => {
      apply(await api('POST', '/api/locations', {
        originName: local.origin.name, originCoords: local.origin.coords,
        destinationName: local.destination.name, destinationCoords: local.destination.coords, via: S.via,
      }));
      if (message) setStatus(message);
      if (fly) fitMarkers();
      watchSite();
      autoRoute();
    });
  }

  // Like the desktop app: once both points exist, a preliminary truck route is
  // calculated automatically. It never counts as vehicle confirmation.
  let autoRouting = null;
  function autoRoute() {
    if (!S.active || !S.origin.coords || !S.destination.coords || S.routes.length) return;
    const request = api('POST', '/api/route', { preliminary: true }, { quiet: true })
      .then((snapshot) => {
        if (autoRouting !== request) return;
        apply(snapshot);
        if (S.routes.length) { fitRoute(); watchSite(); }
      })
      .catch(() => { /* recorded on the server; the Calculate button still works */ })
      .finally(() => { if (autoRouting === request) autoRouting = null; });
    autoRouting = request;
  }

  // ----- map -------------------------------------------------------------
  const map = L.map('map', { zoomControl: true, worldCopyJump: true }).setView([46.3, 25], 6);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);
  const hazardLayer = L.tileLayer('/api/hazard/{z}/{x}/{y}.png', {
    maxNativeZoom: 10, maxZoom: 18, opacity: 1, zIndex: 5,
    attribution: '© GEM Foundation 2023 · CC BY-NC-SA 4.0',
  });
  const markerLayer = L.layerGroup().addTo(map);
  const routeLayer = L.layerGroup().addTo(map);
  const regionLayer = L.layerGroup().addTo(map);
  let regionVersion = null;

  const primary = () => getComputedStyle(document.documentElement).getPropertyValue('--primary').trim();
  const pointOf = (text) => {
    const parts = String(text || '').replace(/[;,]/g, ' ').trim().split(/\s+/);
    if (parts.length !== 2) return null;
    const [lat, lon] = parts.map(Number);
    return Number.isFinite(lat) && Number.isFinite(lon) ? [lat, lon] : null;
  };

  function renderMap() {
    markerLayer.clearLayers();
    for (const [target, label] of [['origin', 'A'], ['destination', 'B']]) {
      const point = pointOf(S[target].coords);
      if (!point) continue;
      L.marker(point, {
        icon: L.divIcon({ className: 'marker-label', html: `<span>${label}</span>`, iconSize: [26, 26], iconAnchor: [13, 13] }),
        title: S[target].name, keyboard: false,
      }).addTo(markerLayer);
    }
    routeLayer.clearLayers();
    S.routes.forEach((route, i) => {
      if (i === S.selectedRoute) return;
      L.geoJSON(route.geometry, { style: { color: primary(), weight: 4, opacity: 0.35, dashArray: '6 6' }, interactive: false }).addTo(routeLayer);
    });
    if (S.selectedRoute !== null && S.routes[S.selectedRoute]) {
      L.geoJSON(S.routes[S.selectedRoute].geometry, { style: { color: primary(), weight: 5, opacity: 0.9 }, interactive: false }).addTo(routeLayer);
    }
    syncRegion(S.region);
  }

  function fitMarkers() {
    const points = ['origin', 'destination'].map((t) => pointOf(S[t].coords)).filter(Boolean);
    if (points.length === 2) map.fitBounds(points, { padding: [60, 60], maxZoom: 13 });
    else if (points.length === 1) map.setView(points[0], 12);
  }

  function fitRoute() {
    const route = S.routes[S.selectedRoute];
    if (route) map.fitBounds(L.geoJSON(route.geometry).getBounds(), { padding: [40, 40] });
  }

  async function syncRegion(region) {
    const label = $('#region-label');
    if (!region || !region.status) {
      label.hidden = true;
      regionLayer.clearLayers();
      regionVersion = null;
      return;
    }
    label.hidden = false;
    label.textContent = region.status === 'ready'
      ? `Delivery region: ${region.name} · geoBoundaries gbOpen / ADM1`
      : 'Delivery region boundary unavailable';
    if (region.status !== 'ready') { regionLayer.clearLayers(); regionVersion = null; return; }
    if (region.version === regionVersion) return;
    regionVersion = region.version;
    const data = await api('GET', '/api/site/region', undefined, { quiet: true }).catch(() => null);
    regionLayer.clearLayers();
    if (data && regionVersion === region.version) {
      L.geoJSON(data.geometry, { style: { color: primary(), weight: 3, dashArray: '7 3', fill: false }, interactive: false }).addTo(regionLayer);
    }
  }

  map.on('click', (event) => {
    const { lat, lng } = event.latlng;
    const lon = ((lng + 180) % 360 + 360) % 360 - 180;
    const target = pick;
    local[target] = { name: 'Point selected on map', coords: `${lat.toFixed(7)}, ${lon.toFixed(7)}` };
    run(async () => {
      apply(await api('POST', '/api/locations', {
        originName: local.origin.name, originCoords: local.origin.coords,
        destinationName: local.destination.name, destinationCoords: local.destination.coords, via: S.via,
      }));
      setStatus('Point selected. Looking up a nearby address…');
      watchSite();
      autoRoute();
      apply(await api('POST', '/api/locations/reverse', { target }, { quiet: true }));
    });
  });

  for (const button of $$('[data-pick]')) {
    button.addEventListener('click', () => {
      pick = button.dataset.pick;
      for (const b of $$('[data-pick]')) b.setAttribute('aria-checked', String(b === button));
    });
  }

  let legendLoaded = false;
  $('#hazard-toggle').addEventListener('change', async (event) => {
    const legend = $('#hazard-legend');
    if (event.target.checked) {
      hazardLayer.addTo(map);
      legend.hidden = false;
      if (!legendLoaded) {
        legendLoaded = true;
        const bands = await api('GET', '/api/hazard/legend', undefined, { quiet: true }).catch(() => []);
        legend.replaceChildren(
          el('strong', { text: 'GEM 2023.1 · PGA (g) · rock · 475 years' }),
          el('div', { class: 'muted', text: 'Relative PGA · application labels' }),
          el('ul', {}, bands.map((b) => el('li', {}, el('span', { class: 'swatch', style: `background:${b.color}` }), `${b.interval} · ${b.label}`))),
          el('div', { class: 'muted', text: '© GEM · CC BY-NC-SA 4.0' })
        );
      }
    } else {
      map.removeLayer(hazardLayer);
      legend.hidden = true;
    }
  });

  // ----- route -----------------------------------------------------------
  function renderResults() {
    const results = $('#results');
    results.hidden = !S.routes.length;
    $('#route-rows').replaceChildren(...S.routes.map((route, i) => el('tr', {
      'aria-selected': String(i === S.selectedRoute), tabindex: 0,
      onclick: () => selectRoute(i),
      onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectRoute(i); } },
    }, el('td', { text: route.name + (route.ferryDetected ? ' · ferry' : '') }), el('td', { class: 'num', text: fmt(route.distance_km) }), el('td', { class: 'num', text: fmt(route.hours) }))));
    $('#route-detail').textContent = S.routeDetail;
  }

  function selectRoute(index) {
    if (index === S.selectedRoute) return;
    run(async () => { apply(await api('POST', '/api/route/select', { index })); watchSite(); });
  }

  async function calculate() {
    if (adjustPending()) { setStatus('Apply vehicle adjustments before calculating.', true); return; }
    if (!S.active) { setStatus('No compatible vehicle. Edit the product or choose a profile.', true); return; }
    for (const [target, label] of [['origin', 'departure'], ['destination', 'destination']]) {
      if (!local[target].coords) {
        setStatus(`Choose the ${label}: select an address suggestion or click on the map.`, true);
        $(`#${target}-input`).focus();
        return;
      }
    }
    if (!S.accepted) {
      const ok = await formDialog({
        title: 'Confirm vehicle',
        help: S.profileSummary + '\n\n' + S.active.vehicle.notes + '\n\nUse these values for a preliminary route?',
        fields: [], submitLabel: 'Use these values', onSubmit: async () => true,
      });
      if (!ok) return;
    }
    setStatus('Calculating the truck route…');
    await run(async () => {
      apply(await api('POST', '/api/route', { confirmed: true }));
      fitRoute();
      watchSite();
    });
  }

  // ----- dialogs ---------------------------------------------------------
  const dialog = $('#dialog');
  function formDialog({ title, help = '', fields, submitLabel = 'Save', onSubmit, body = null, single = false, hideSubmit = false }) {
    return new Promise((resolve) => {
      $('.dialog-title', dialog).textContent = title;
      $('.dialog-help', dialog).textContent = help;
      $('.dialog-help', dialog).classList.add('pre');
      $('.dialog-error', dialog).textContent = '';
      const submit = $('.dialog-submit', dialog);
      submit.textContent = submitLabel;
      submit.hidden = hideSubmit;
      $('[data-close]', dialog).textContent = hideSubmit ? 'Close' : 'Cancel';
      const container = $('.dialog-body', dialog);
      container.classList.toggle('single', single);
      const inputs = {};
      container.replaceChildren(...(body ? [body] : fields.map((f) => {
        let input;
        if (f.options) input = el('select', { class: 'select', name: f.key }, f.options.map(([v, t]) => el('option', { value: v, text: t })));
        else if (f.type === 'textarea') input = el('textarea', { name: f.key, rows: 2 });
        else input = el('input', { type: f.type || 'text', name: f.key, inputmode: f.numeric ? 'decimal' : undefined });
        input.value = f.value ?? '';
        inputs[f.key] = input;
        return el('label', { class: f.full ? 'full' : undefined }, f.label, input);
      })));
      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        dialog.removeEventListener('close', onClose);
        $('form', dialog).removeEventListener('submit', onSave);
        $('[data-close]', dialog).removeEventListener('click', onCancel);
        if (dialog.open) dialog.close();
        resolve(value);
      };
      const onClose = () => finish(false);
      const onCancel = () => finish(false);
      const onSave = async (event) => {
        event.preventDefault();
        const values = Object.fromEntries(Object.entries(inputs).map(([k, input]) => [k, input.value]));
        submit.disabled = true;
        try {
          const result = await onSubmit(values);
          finish(result === undefined ? true : result);
        } catch (error) {
          $('.dialog-error', dialog).textContent = error.message;
        } finally {
          submit.disabled = false;
        }
      };
      dialog.addEventListener('close', onClose);
      $('form', dialog).addEventListener('submit', onSave);
      $('[data-close]', dialog).addEventListener('click', onCancel);
      dialog.showModal();
      const first = Object.values(inputs)[0];
      if (first) first.focus();
    });
  }

  function editProduct() {
    const p = S.product;
    formDialog({
      title: 'Transported product',
      help: 'Dimensions of one product. A vehicle is recommended after saving.',
      fields: [
        { key: 'name', label: 'Product name', value: p.name, full: true },
        { key: 'quantity', label: 'Quantity (units)', value: p.quantity, numeric: true },
        { key: 'weight', label: 'Weight / product (t)', value: g(p.weight), numeric: true },
        { key: 'length', label: 'Length (m)', value: g(p.length), numeric: true },
        { key: 'width', label: 'Width (m)', value: g(p.width), numeric: true },
        { key: 'height', label: 'Height (m)', value: g(p.height), numeric: true },
      ],
      onSubmit: async (values) => apply(await api('POST', '/api/product', values)),
    });
  }

  function editCoordinates() {
    formDialog({
      title: 'Exact coordinates',
      help: 'Optional: enter coordinates or select points on the map. Format: latitude, longitude.',
      fields: [
        { key: 'origin', label: 'Departure · lat, lon', value: local.origin.coords, full: true },
        { key: 'destination', label: 'Destination · lat, lon', value: local.destination.coords, full: true },
        { key: 'via', label: 'Via · lat lon; lat lon', value: S.via, full: true },
      ],
      onSubmit: async (values) => {
        const name = (target, coords) => (coords === local[target].coords ? local[target].name : (coords ? 'Point entered as coordinates' : local[target].name));
        apply(await api('POST', '/api/locations', {
          originName: name('origin', values.origin.trim()), originCoords: values.origin.trim(),
          destinationName: name('destination', values.destination.trim()), destinationCoords: values.destination.trim(), via: values.via,
        }));
        fitMarkers();
        watchSite();
        autoRoute();
      },
    });
  }

  const RATE_FIELDS = [
    ['loaded', 'Loaded rate (EUR/km)'], ['empty', 'Empty rate (EUR/km)'], ['fixed', 'Fixed cost (EUR/trip)'],
    ['markup', 'Markup (%)'], ['vat', 'VAT (%)'],
  ];

  function tripFields() {
    const route = S.routes[S.selectedRoute] || {};
    return [
      { key: 'quantity', label: 'Products / trips', value: S.product.quantity, numeric: true },
      { key: 'return_km', label: 'Empty return per trip (km)', value: route.distance_km ? fmt(route.distance_km, 2) : 0, numeric: true },
      { key: 'position_km', label: 'Positioning per trip (km)', value: 0, numeric: true },
    ];
  }

  async function download(response, fallback) {
    const blob = await response.blob();
    const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '');
    const link = el('a', { href: URL.createObjectURL(blob), download: match ? match[1] : fallback });
    document.body.append(link);
    link.click();
    setTimeout(() => { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
  }

  function exportExcel() {
    const current = S.selectedRoute !== null;
    const saved = S.deliveries.length > 0;
    if (!current && !saved) { setStatus('Choose the destination and calculate a route first.', true); return; }
    const modes = [...(current ? [['current', 'Current transport']] : []), ...(saved ? [['saved', 'Saved deliveries']] : [])];
    formDialog({
      title: 'Export transport to Excel',
      help: 'Exports transport costs, route details and Site & Environment with the delivery address, coordinates and sources. '
        + 'Return distance is an editable assumption. Quantity and empty kilometres apply to Current transport; Saved deliveries retain their stored values.',
      fields: [
        { key: 'mode', label: 'Export', options: modes, full: true },
        ...tripFields(),
        ...RATE_FIELDS.map(([key, label]) => ({ key, label, value: S.rates[key], numeric: true })),
        { key: 'notes', label: 'Transport assumptions', type: 'textarea', full: true, value: 'Return distance equals outbound distance; verify the return route.' },
      ],
      submitLabel: 'Export Excel',
      onSubmit: async (values) => {
        const response = await api('POST', '/api/export', values, { raw: true });
        await download(response, 'FlowerMoon-Transport.xlsx');
        await refresh();
        setStatus('Excel exported. Check your downloads folder.');
      },
    });
  }

  function saveDelivery() {
    if (S.selectedRoute === null) { setStatus('Calculate and select a route.', true); return; }
    formDialog({
      title: 'Save delivery',
      help: `Valhalla distance: ${fmt(S.routes[S.selectedRoute].distance_km, 2)} km one way. One product per trip. Return distance is editable and is not a validated return route.`,
      fields: [...tripFields(), { key: 'notes', label: 'Notes / assumptions', type: 'textarea', full: true, value: 'Return equals outbound distance — assumption to confirm.' }],
      onSubmit: async (values) => apply(await api('POST', '/api/deliveries', values)),
    });
  }

  function deliveriesTable() {
    const table = el('table', { class: 'table' },
      el('thead', {}, el('tr', {}, ['Product / destination', 'Route km', 'Units / trips', 'Empty km / trip', 'Total EUR', ''].map((t) => el('th', { text: t })))),
      el('tbody', {}, S.deliveries.length ? S.deliveries.map((d) => el('tr', {},
        el('td', { text: d.name }), el('td', { class: 'num', text: fmt(d.distance_km, 2) }), el('td', { class: 'num', text: String(d.quantity) }),
        el('td', { class: 'num', text: fmt(d.empty_km, 2) }), el('td', { class: 'num', text: S.rates.loaded > 0 ? fmt(d.total, 2) : 'Rate missing' }),
        el('td', {}, el('button', {
          type: 'button', class: 'btn btn-sm', text: 'Archive',
          onclick: async () => {
            await run(async () => apply(await api('DELETE', '/api/deliveries/' + encodeURIComponent(d.id))));
            table.replaceWith(deliveriesTable());
          },
        }))
      )) : el('tr', {}, el('td', { colspan: 6, class: 'muted', text: 'No saved deliveries yet. Calculate a route, then select Save delivery.' }))));
    return table;
  }

  function showDeliveries() {
    formDialog({ title: 'Saved deliveries', help: 'Each row is one delivery. One product per trip. Rates apply to all rows at export.', fields: [], body: deliveriesTable(), single: true, hideSubmit: true, onSubmit: async () => true });
  }

  // ----- site & environment ---------------------------------------------
  const expanded = new Set();
  let selectedKey = null;
  let siteTimer = null;

  function badgeClass(status) {
    if (/^(Verify|Model|Display)/.test(status)) return 'warn';
    if (/^(Disabled|Not available)/.test(status)) return 'off';
    if (/^(Calculated|Auto|Ready)/i.test(status)) return 'ok';
    return '';
  }

  function renderSite() {
    if (!site) return;
    $('#site-address').textContent = 'Destination  /  ' + (site.address || 'Choose the destination on the map');
    $('#site-summary').textContent = 'Destination coordinates (WGS84): ' + (site.coordinates || 'Not selected')
      + ' · All environmental and structural data below refers to this delivery point.';
    $('#site-progress').textContent = site.progress.join('\n');
    $('#site-warnings').textContent = site.warnings.join('\n');
    const visible = site.rows.filter((row) => !row.parent || expanded.has(row.parent));
    const wrap = $('.site-table-wrap');
    const scroll = wrap.scrollTop;  // replacing rows would otherwise jump back to the top
    $('#site-rows').replaceChildren(...visible.map((row, i) => {
      if (row.section && !row.parent) {
        return el('tr', { class: 'section' }, el('td', {}), el('td', { colspan: 6, text: row.label }));
      }
      const classes = [row.section ? 'subsection' : '', row.parent ? 'child' : '', row.estimate ? 'estimate' : ''].filter(Boolean).join(' ');
      const toggle = row.expandable ? el('button', {
        type: 'button', class: 'toggle', 'aria-expanded': String(expanded.has(row.key)),
        'aria-label': (expanded.has(row.key) ? 'Collapse ' : 'Expand ') + row.label, text: expanded.has(row.key) ? '−' : '+',
        onclick: (e) => { e.stopPropagation(); if (expanded.has(row.key)) expanded.delete(row.key); else expanded.add(row.key); renderSite(); },
      }) : '';
      return el('tr', {
        class: classes || undefined, tabindex: row.section ? undefined : 0, 'aria-selected': String(row.key === selectedKey), 'data-key': row.key,
        onclick: () => { if (!row.section) selectRow(row); },
        ondblclick: () => { if (!row.section) valueDetails(row.key); },
        onkeydown: (e) => { if (e.key === 'Enter' && !row.section) valueDetails(row.key); },
      },
      el('td', {}, toggle),
      el('td', { text: row.label }),
      el('td', { class: 'num', text: row.value }),
      el('td', { text: row.unit }),
      el('td', { text: row.source }),
      el('td', { class: 'muted', text: row.brief }),
      el('td', {}, row.status ? el('span', { class: 'badge ' + badgeClass(row.status), text: row.status }) : ''));
    }));
    wrap.scrollTop = scroll;
    $('#value-button').disabled = !selectedKey;
  }

  function selectRow(row) {
    selectedKey = row.key;
    $('#site-meaning').textContent = (row.meaning || '') + ' Double-click or open Value details for sources and method.';
    for (const tr of $$('#site-rows tr')) tr.setAttribute('aria-selected', String(tr.dataset.key === row.key));
    $('#value-button').disabled = false;
  }

  async function loadSite() {
    site = await api('GET', '/api/site', undefined, { quiet: true });
    renderSite();
    syncRegion(site.region);
    return site;
  }

  function watchSite() {
    clearTimeout(siteTimer);
    const tick = async () => {
      try {
        const view = await loadSite();
        if (view.pending.length) siteTimer = setTimeout(tick, 1500);
      } catch (_) {
        siteTimer = setTimeout(tick, 4000);
      }
    };
    siteTimer = setTimeout(tick, 400);
  }

  async function valueDetails(key) {
    await run(async () => {
      const doc = await api('GET', '/api/site/value?key=' + encodeURIComponent(key));
      const [first, ...rest] = doc.sections;
      const body = el('div', { class: 'details' },
        el('p', { class: 'value', text: doc.value }),
        first ? [el('h3', { text: first.title }), el('p', { text: first.body })] : [],
        el('h3', { text: 'Sources & links' }),
        doc.links.length
          ? doc.links.map((l) => el('p', {}, el('a', { href: l.url, target: '_blank', rel: 'noopener noreferrer', text: l.label }), el('br'), el('span', { class: 'muted', text: l.url })))
          : el('p', { class: 'muted', text: 'No external source link recorded for this value.' }),
        rest.map((s) => [el('h3', { text: s.title }), el('p', { text: s.body })]));
      formDialog({ title: doc.title, fields: [], body, single: true, hideSubmit: true, onSubmit: async () => true });
    });
  }

  function openSite() {
    $('#site').hidden = false;
    document.body.style.overflow = 'hidden';
    $('[data-action="close-site"]').focus();
    run(loadSite);
  }

  function closeSite() {
    $('#site').hidden = true;
    document.body.style.overflow = '';
    map.invalidateSize();
  }

  // ----- theme -----------------------------------------------------------
  function toggleTheme() {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'light' : 'dark';
    try { localStorage.setItem('fm-theme', document.documentElement.dataset.theme); } catch (_) { /* storage blocked */ }
    if (S) apply(S);
  }
  try {
    const saved = localStorage.getItem('fm-theme');
    if (saved === 'light' || saved === 'dark') document.documentElement.dataset.theme = saved;
  } catch (_) { /* storage blocked */ }

  // ----- wiring ----------------------------------------------------------
  const moreButton = $('#more-button');
  const moreMenu = $('#more-menu');
  const closeMenu = () => { moreMenu.hidden = true; moreButton.setAttribute('aria-expanded', 'false'); };
  moreButton.addEventListener('click', (e) => {
    e.stopPropagation();
    moreMenu.hidden = !moreMenu.hidden;
    moreButton.setAttribute('aria-expanded', String(!moreMenu.hidden));
    if (!moreMenu.hidden) $('button', moreMenu).focus();
  });
  document.addEventListener('click', closeMenu);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeMenu(); if (!$('#site').hidden && !dialog.open) closeSite(); }
  });

  const actions = {
    export: exportExcel, site: openSite, 'close-site': closeSite, deliveries: showDeliveries,
    coordinates: editCoordinates, theme: toggleTheme, product: editProduct, 'save-delivery': saveDelivery,
    'refresh-site': () => run(async () => { site = await api('POST', '/api/site/refresh'); renderSite(); watchSite(); }),
  };
  document.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action]');
    if (target && actions[target.dataset.action]) { closeMenu(); actions[target.dataset.action](); }
    const switcher = e.target.closest('[data-panel-switch]');
    if (switcher) setPanel(switcher.dataset.panelSwitch);
  });
  for (const tab of $$('.tab')) tab.addEventListener('click', () => setPanel(tab.dataset.panel));
  for (const select of $$('.preset-select')) {
    select.addEventListener('change', () => run(async () => apply(await api('POST', '/api/vehicle/preset', { id: select.value }))));
  }
  $('#calculate').addEventListener('click', calculate);
  $('#value-button').addEventListener('click', () => selectedKey && valueDetails(selectedKey));
  addressField('origin');
  addressField('destination');

  setStatus('Connecting… the free server may need up to a minute to wake up.');
  run(async () => {
    await refresh();
    fitMarkers();
    watchSite();
  });
})();

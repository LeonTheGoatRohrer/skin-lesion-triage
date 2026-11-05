// Quadratischer Zuschnitt mit Verschieben (Ziehen) und Zoomen (Mausrad, zwei Finger, Regler).
// Der sichtbare Ausschnitt ist genau das, was das Modell bekommt.

export function createCropper(host, bitmap, { onChange } = {}) {
  const canvas = document.createElement('canvas');
  host.replaceChildren(canvas);
  const ctx = canvas.getContext('2d');
  const W = bitmap.width;
  const H = bitmap.height;
  const maxSide = Math.min(W, H);
  const minSide = Math.max(24, maxSide / 12);
  // Startwert: mittleres Quadrat mit 55 % der kürzeren Seite
  const st = { cx: W / 2, cy: H / 2, side: maxSide * 0.55 };
  const pointers = new Map();
  let pinch = null;
  let raf = 0;

  function clamp() {
    st.side = Math.min(maxSide, Math.max(minSide, st.side));
    const h = st.side / 2;
    st.cx = Math.min(W - h, Math.max(h, st.cx));
    st.cy = Math.min(H - h, Math.max(h, st.cy));
  }

  function resize() {
    const r = host.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    canvas.width = Math.max(1, Math.round(r.width * dpr));
    canvas.height = Math.max(1, Math.round(r.width * dpr));
    draw();
  }

  function draw() {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const s = canvas.width;
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.fillStyle = '#111';
      ctx.fillRect(0, 0, s, s);
      ctx.drawImage(bitmap, st.cx - st.side / 2, st.cy - st.side / 2, st.side, st.side, 0, 0, s, s);
      // Hilfskreis: Hautstelle soll ihn ungefähr ausfüllen
      ctx.save();
      ctx.lineWidth = Math.max(2, s / 180);
      ctx.setLineDash([s / 40, s / 60]);
      ctx.strokeStyle = 'rgba(255,255,255,0.9)';
      ctx.shadowColor = 'rgba(0,0,0,0.6)';
      ctx.shadowBlur = s / 80;
      ctx.beginPath();
      ctx.arc(s / 2, s / 2, s * 0.27, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      // Fadenkreuz in der Mitte
      const c = s / 2;
      const k = s / 40;
      ctx.beginPath();
      ctx.moveTo(c - k, c); ctx.lineTo(c + k, c);
      ctx.moveTo(c, c - k); ctx.lineTo(c, c + k);
      ctx.stroke();
      ctx.restore();
      onChange?.(getCrop());
    });
  }

  function toImageDelta(dxCss, dyCss) {
    const r = host.getBoundingClientRect();
    const f = st.side / r.width;
    return [dxCss * f, dyCss * f];
  }

  function zoomAt(factor, xCss, yCss) {
    const r = host.getBoundingClientRect();
    const px = xCss == null ? 0.5 : (xCss - r.left) / r.width;
    const py = yCss == null ? 0.5 : (yCss - r.top) / r.height;
    const ix = st.cx - st.side / 2 + px * st.side;
    const iy = st.cy - st.side / 2 + py * st.side;
    st.side /= factor;
    clamp();
    st.cx = ix - (px - 0.5) * st.side;
    st.cy = iy - (py - 0.5) * st.side;
    clamp();
    draw();
  }

  function onDown(e) {
    host.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) };
    }
  }

  function onMove(e) {
    const prev = pointers.get(e.pointerId);
    if (!prev) return;
    const cur = { x: e.clientX, y: e.clientY };
    pointers.set(e.pointerId, cur);
    if (pointers.size === 1) {
      const [dx, dy] = toImageDelta(cur.x - prev.x, cur.y - prev.y);
      st.cx -= dx;
      st.cy -= dy;
      clamp();
      draw();
    } else if (pointers.size === 2 && pinch) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (pinch.d > 0) zoomAt(d / pinch.d, (a.x + b.x) / 2, (a.y + b.y) / 2);
      pinch.d = d;
    }
  }

  function onUp(e) {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
  }

  function onWheel(e) {
    e.preventDefault();
    zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY);
  }

  function onKey(e) {
    const step = st.side * 0.05;
    const map = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (map[e.key]) {
      st.cx += map[e.key][0];
      st.cy += map[e.key][1];
      clamp();
      draw();
      e.preventDefault();
    } else if (e.key === '+' || e.key === '=') { zoomAt(1.15); e.preventDefault(); }
    else if (e.key === '-') { zoomAt(1 / 1.15); e.preventDefault(); }
  }

  host.tabIndex = 0;
  host.addEventListener('pointerdown', onDown);
  host.addEventListener('pointermove', onMove);
  host.addEventListener('pointerup', onUp);
  host.addEventListener('pointercancel', onUp);
  host.addEventListener('wheel', onWheel, { passive: false });
  host.addEventListener('keydown', onKey);
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  clamp();
  resize();

  function getCrop() {
    return { x: st.cx - st.side / 2, y: st.cy - st.side / 2, side: st.side };
  }

  return {
    getCrop,
    /** Zoom als Wert 0..1 (0 = ganzes Bild, 1 = maximal hineingezoomt), logarithmisch */
    getZoom: () => Math.log(maxSide / st.side) / Math.log(maxSide / minSide),
    setZoom(v) {
      st.side = maxSide / Math.exp(v * Math.log(maxSide / minSide));
      clamp();
      draw();
    },
    zoomBy: (f) => zoomAt(f),
    destroy() {
      ro.disconnect();
      cancelAnimationFrame(raf);
    },
  };
}

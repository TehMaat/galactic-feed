// Copertine generative: ogni articolo riceve un'immagine disegnata su canvas a partire
// dal suo seme e dal tema, così il mockup non dipende da immagini esterne.
(function () {
  const cache = new Map();
  const TAU = Math.PI * 2;

  function rng(seed) {
    let t = seed >>> 0;
    return function () {
      t += 0x6d2b79f5;
      let r = Math.imul(t ^ (t >>> 15), 1 | t);
      r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
      return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
    };
  }

  const hsl = (h, s, l, a = 1) => `hsla(${h}, ${s}%, ${l}%, ${a})`;

  function sky(ctx, w, h, hue, r) {
    const g = ctx.createLinearGradient(0, 0, w * 0.35, h);
    g.addColorStop(0, hsl(hue + 18, 52, 24));
    g.addColorStop(1, hsl(hue - 14, 58, 8));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    const gx = w * (0.15 + r() * 0.7);
    const gy = h * (0.1 + r() * 0.4);
    const glow = ctx.createRadialGradient(gx, gy, 0, gx, gy, w * 0.75);
    glow.addColorStop(0, hsl(hue + 40, 80, 62, 0.32));
    glow.addColorStop(1, hsl(hue + 40, 80, 62, 0));
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, w, h);
  }

  function stars(ctx, w, h, r, density) {
    const n = Math.round((w * h) / 1000 * density);
    for (let i = 0; i < n; i++) {
      ctx.fillStyle = `rgba(255, 255, 255, ${0.25 + r() * 0.65})`;
      ctx.beginPath();
      ctx.arc(r() * w, r() * h, r() * 1.1 + 0.25, 0, TAU);
      ctx.fill();
    }
  }

  function glint(ctx, x, y, s, alpha) {
    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(x - s, y); ctx.lineTo(x + s, y);
    ctx.moveTo(x, y - s); ctx.lineTo(x, y + s);
    ctx.stroke();
  }

  const painters = {
    planet(ctx, w, h, hue, r) {
      sky(ctx, w, h, hue, r);
      stars(ctx, w, h, r, 0.9);
      const R = Math.min(w, h) * (0.3 + r() * 0.14);
      const cx = w * (0.52 + r() * 0.26);
      const cy = h * (0.5 + r() * 0.32);
      const ring = r() > 0.3;
      const ringStroke = () => {
        ctx.strokeStyle = hsl(hue + 40, 70, 82, 0.55);
        ctx.lineWidth = Math.max(1.5, R * 0.05);
      };
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-0.32);
      if (ring) { ringStroke(); ctx.beginPath(); ctx.ellipse(0, 0, R * 1.62, R * 0.36, 0, Math.PI, TAU); ctx.stroke(); }
      ctx.restore();
      const g = ctx.createRadialGradient(cx - R * 0.4, cy - R * 0.45, R * 0.08, cx, cy, R);
      g.addColorStop(0, hsl(hue + 30, 72, 74));
      g.addColorStop(0.55, hsl(hue, 52, 42));
      g.addColorStop(1, hsl(hue - 20, 60, 12));
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.fill();
      ctx.save();
      ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.clip();
      for (let i = 0; i < 5; i++) {
        ctx.fillStyle = hsl(hue + 10, 60, 82, 0.05 + r() * 0.07);
        ctx.fillRect(cx - R, cy - R + (i + 0.6) * R * 0.36, R * 2, R * (0.06 + r() * 0.07));
      }
      ctx.restore();
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-0.32);
      if (ring) { ringStroke(); ctx.beginPath(); ctx.ellipse(0, 0, R * 1.62, R * 0.36, 0, 0, Math.PI); ctx.stroke(); }
      ctx.restore();
      const mx = w * (0.12 + r() * 0.25);
      const my = h * (0.2 + r() * 0.3);
      ctx.fillStyle = hsl(hue + 50, 30, 80, 0.9);
      ctx.beginPath(); ctx.arc(mx, my, R * 0.12, 0, TAU); ctx.fill();
    },

    nebula(ctx, w, h, hue, r) {
      ctx.fillStyle = hsl(hue - 20, 50, 7);
      ctx.fillRect(0, 0, w, h);
      for (let i = 0; i < 7; i++) {
        const x = w * r();
        const y = h * r();
        const rad = Math.max(w, h) * (0.25 + r() * 0.4);
        const g = ctx.createRadialGradient(x, y, 0, x, y, rad);
        g.addColorStop(0, hsl(hue + (r() * 80 - 40), 80, 58, 0.34));
        g.addColorStop(1, hsl(hue, 80, 50, 0));
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, w, h);
      }
      stars(ctx, w, h, r, 1.4);
      for (let i = 0; i < 4; i++) glint(ctx, r() * w, r() * h, 3 + r() * 5, 0.8);
    },

    grid(ctx, w, h, hue, r) {
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, hsl(hue + 25, 55, 12));
      g.addColorStop(0.58, hsl(hue + 5, 60, 22));
      g.addColorStop(1, hsl(hue - 10, 60, 8));
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      stars(ctx, w, h * 0.5, r, 0.7);
      const horizon = h * (0.52 + r() * 0.08);
      const sx = w * (0.3 + r() * 0.4);
      const sun = ctx.createRadialGradient(sx, horizon, 0, sx, horizon, w * 0.32);
      sun.addColorStop(0, hsl(hue + 150, 90, 72, 0.85));
      sun.addColorStop(0.3, hsl(hue + 150, 90, 62, 0.3));
      sun.addColorStop(1, hsl(hue + 150, 90, 60, 0));
      ctx.fillStyle = sun;
      ctx.fillRect(0, 0, w, horizon);
      ctx.strokeStyle = hsl(hue, 90, 70, 0.55);
      ctx.lineWidth = 1;
      for (let i = -12; i <= 12; i++) {
        ctx.beginPath();
        ctx.moveTo(sx + i * 6, horizon);
        ctx.lineTo(sx + i * w * 0.18, h);
        ctx.stroke();
      }
      for (let j = 1; j < 9; j++) {
        const y = horizon + (h - horizon) * Math.pow(j / 8, 1.9);
        ctx.globalAlpha = 0.25 + j * 0.07;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    },

    bars(ctx, w, h, hue, r) {
      sky(ctx, w, h, hue, r);
      stars(ctx, w, h, r, 0.4);
      const units = 4 + Math.floor(r() * 3);
      const bw = w * 0.62;
      const bh = (h * 0.62) / units;
      const x0 = (w - bw) / 2 + (r() - 0.5) * w * 0.08;
      const y0 = h * 0.2;
      for (let i = 0; i < units; i++) {
        const y = y0 + i * bh;
        ctx.fillStyle = hsl(hue - 10, 30, 14 + (i % 2) * 3, 0.92);
        ctx.beginPath();
        ctx.roundRect(x0, y + 1.5, bw, bh - 3, Math.min(6, bh * 0.25));
        ctx.fill();
        ctx.strokeStyle = hsl(hue + 20, 60, 70, 0.22);
        ctx.lineWidth = 1;
        ctx.stroke();
        const leds = 2 + Math.floor(r() * 3);
        for (let k = 0; k < leds; k++) {
          const lit = r();
          ctx.fillStyle = lit > 0.85 ? hsl(40, 95, 62) : hsl(hue + 15, 90, 62, 0.4 + lit * 0.6);
          ctx.beginPath();
          ctx.arc(x0 + bw * 0.08 + k * Math.max(7, bh * 0.28), y + bh / 2, Math.max(1.6, bh * 0.08), 0, TAU);
          ctx.fill();
        }
        ctx.fillStyle = hsl(hue + 20, 30, 60, 0.18);
        for (let s = 0; s < 6; s++) ctx.fillRect(x0 + bw * 0.55 + s * bw * 0.06, y + bh * 0.3, bw * 0.03, bh * 0.4);
      }
    },

    hills(ctx, w, h, hue, r) {
      const g = ctx.createLinearGradient(0, 0, 0, h);
      g.addColorStop(0, hsl(hue - 100, 45, 18));
      g.addColorStop(0.6, hsl(hue, 70, 55));
      g.addColorStop(1, hsl(hue + 20, 85, 70));
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);
      stars(ctx, w, h * 0.35, r, 0.5);
      ctx.fillStyle = hsl(hue + 25, 90, 82, 0.95);
      ctx.beginPath(); ctx.arc(w * (0.25 + r() * 0.5), h * 0.52, Math.min(w, h) * 0.12, 0, TAU); ctx.fill();
      for (let layer = 0; layer < 3; layer++) {
        const base = h * (0.6 + layer * 0.13);
        const amp = h * (0.08 - layer * 0.015);
        const f = 1.5 + r() * 2;
        const ph = r() * TAU;
        ctx.fillStyle = hsl(hue - 90 + layer * 8, 40, 20 - layer * 5, 0.92);
        ctx.beginPath();
        ctx.moveTo(0, h);
        for (let x = 0; x <= w; x += 4) ctx.lineTo(x, base - Math.sin((x / w) * f * Math.PI + ph) * amp);
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fill();
      }
    }
  };

  function cover(seed, topicKey, w, h) {
    const key = `${seed}-${topicKey}-${w}x${h}`;
    if (cache.has(key)) return cache.get(key);
    const topic = window.GF_DATA.topics[topicKey];
    const canvas = document.createElement("canvas");
    const scale = 2;
    canvas.width = w * scale;
    canvas.height = h * scale;
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    const r = rng(seed * 9973);
    painters[topic.art](ctx, w, h, topic.hue + Math.round((r() - 0.5) * 30), r);
    const url = canvas.toDataURL("image/jpeg", 0.86);
    cache.set(key, url);
    return url;
  }

  function paintStars(canvas, seed = 7) {
    // offsetWidth/Height ignorano lo zoom della cornice, a differenza di getBoundingClientRect.
    const rect = { width: canvas.offsetWidth, height: canvas.offsetHeight };
    if (!rect.width) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    const r = rng(seed);
    stars(ctx, rect.width, rect.height, r, 0.4);
    for (let i = 0; i < 3; i++) glint(ctx, rect.width * (0.72 + r() * 0.22), rect.height * (0.5 + r() * 0.3), 3 + r() * 3, 0.7);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.10)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(rect.width * 0.86, rect.height * 0.1, rect.width * 0.55, rect.height * 0.42, -0.35, 0, TAU);
    ctx.stroke();
  }

  window.GF_ART = { cover, paintStars };
})();

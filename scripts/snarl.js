(function () {
  // ---------- audio play/pause ----------
  const audio = document.getElementById('snarl');
  const controls = document.getElementById('audio-controls');
  const mutedBtn = document.getElementById('audio-muted');
  const playingBtn = document.getElementById('audio-playing');

  mutedBtn.addEventListener('click', () => {
    audio.play().then(() => controls.classList.remove('muted')).catch(() => {});
  });
  playingBtn.addEventListener('click', () => {
    audio.pause();
    controls.classList.add('muted');
  });
  audio.addEventListener('ended', () => controls.classList.add('muted'));

  // ---------- SPA-style navigation so audio survives ----------
  // Swap only the non-persistent children of <body> when the user clicks
  // an internal link. The audio element + controls carry data-persist and
  // stay mounted, so playback is uninterrupted.

  function shouldIntercept(a, e) {
    if (!a || !a.href) return false;
    if (e.defaultPrevented) return false;
    if (e.button !== 0) return false;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return false;
    if (a.target && a.target !== '' && a.target !== '_self') return false;
    if (a.hasAttribute('download')) return false;
    if (a.dataset.noswap !== undefined) return false;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin) return false;
    // Only intercept .html pages (or bare directory / no extension) on our site.
    if (url.pathname && /\.(png|jpe?g|gif|webp|svg|pdf|zip|mp3|m4a|mp4|mov|txt|json|xml|csv)$/i.test(url.pathname)) return false;
    return true;
  }

  // Prefer fetch (fast — HTML only). Fall back to a hidden iframe if fetch
  // is blocked (e.g. file:// origins). Final fallback is a full navigation.
  async function loadDoc(url) {
    try {
      const res = await fetch(url, { credentials: 'same-origin' });
      if (!res.ok) throw new Error(res.status);
      const html = await res.text();
      return new DOMParser().parseFromString(html, 'text/html');
    } catch {
      // iframe fallback
    }
    return new Promise((resolve, reject) => {
      const frame = document.createElement('iframe');
      frame.style.cssText = 'position:absolute;width:0;height:0;border:0;visibility:hidden;';
      frame.setAttribute('aria-hidden', 'true');
      let done = false;
      const cleanup = () => { if (frame.parentNode) frame.parentNode.removeChild(frame); };
      frame.addEventListener('load', () => {
        if (done) return;
        done = true;
        try {
          const doc = frame.contentDocument;
          if (!doc) throw new Error('no contentDocument');
          resolve(doc);
        } catch (err) {
          reject(err);
        } finally {
          cleanup();
        }
      });
      frame.addEventListener('error', () => { cleanup(); reject(new Error('iframe error')); });
      frame.src = url;
      document.body.appendChild(frame);
    });
  }

  async function navigate(url, push = true) {
    let doc;
    try {
      doc = await loadDoc(url);
    } catch {
      location.href = url;
      return;
    }
    if (doc.title) document.title = doc.title;

    // Remove current non-persistent body children.
    Array.from(document.body.children).forEach((el) => {
      if (!el.hasAttribute('data-persist')) el.remove();
    });

    // Insert incoming non-persistent body children in order.
    // Skip scripts already loaded (they're persistent), and execute any
    // new inline / src scripts by cloning them into the live document.
    Array.from(doc.body.children).forEach((el) => {
      if (el.hasAttribute('data-persist')) return;
      if (el.tagName === 'SCRIPT') {
        const s = document.createElement('script');
        for (const attr of el.attributes) s.setAttribute(attr.name, attr.value);
        s.text = el.textContent;
        document.body.appendChild(s);
      } else {
        document.body.appendChild(document.importNode(el, true));
      }
    });

    if (push) history.pushState({ spa: true }, '', url);
    window.scrollTo(0, 0);
  }

  document.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!shouldIntercept(a, e)) return;
    const url = new URL(a.href, location.href).href;
    if (url === location.href) { e.preventDefault(); return; }
    e.preventDefault();
    navigate(url, true);
  });

  window.addEventListener('popstate', () => {
    navigate(location.href, false);
  });
})();

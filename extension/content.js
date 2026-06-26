// Bili 投资研究总结 — Content Script
// Injects a "🔬 投资总结" button on B站 video pages and renders result in a floating panel.

const API_BASE = 'http://127.0.0.1:8765';

// ---- Helpers ----

function getBvid() {
  const m = window.location.pathname.match(/\/video\/(BV[a-zA-Z0-9]{10})/);
  return m ? m[1] : null;
}

function isVideoPage() {
  return /\/video\/BV/.test(window.location.pathname);
}

// ---- Markdown rendering (inject marked.js from CDN once) ----

let markedLoaded = false;
function loadMarked() {
  return new Promise((resolve) => {
    if (markedLoaded) { resolve(); return; }
    if (typeof marked !== 'undefined') { markedLoaded = true; resolve(); return; }
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/marked/marked.min.js';
    s.onload = () => { markedLoaded = true; resolve(); };
    s.onerror = () => resolve(); // fallback: plain text
    document.head.appendChild(s);
  });
}

// ---- Server check ----

async function checkServer() {
  try {
    const r = await fetch(`${API_BASE}/api/stats`);
    return r.ok;
  } catch { return false; }
}

// ---- Summary Panel (Shadow DOM) ----

class SummaryPanel {
  constructor() {
    this.host = document.createElement('div');
    this.host.id = 'bs-summary-host';
    this.shadow = this.host.attachShadow({ mode: 'open' });
    this.panel = null;
    this._dragging = false;
    this._offsetX = 0;
    this._offsetY = 0;
  }

  _injectStyles() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = chrome.runtime.getURL('content.css');
    this.shadow.appendChild(link);
  }

  showLoading() {
    this._ensurePanel();
    const body = this.shadow.querySelector('.bs-panel-body');
    body.innerHTML = `
      <div class="bs-loading">
        <div class="spinner"></div>
        <p>正在生成投资研究总结…</p>
        <small>提取字幕、调用 DeepSeek、生成 18 节分析报告</small>
      </div>`;
    this._show();
  }

  showResult(markdown) {
    this._ensurePanel();
    const body = this.shadow.querySelector('.bs-panel-body');
    body.innerHTML = '<div class="bs-loading"><div class="spinner"></div><p>渲染中…</p></div>';
    this._show();

    loadMarked().then(() => {
      try {
        const html = typeof marked !== 'undefined'
          ? marked.parse(markdown)
          : `<pre>${escapeHtml(markdown)}</pre>`;
        body.innerHTML = html;
      } catch (e) {
        body.innerHTML = `<pre>${escapeHtml(markdown)}</pre>`;
      }
    });
  }

  showError(msg) {
    this._ensurePanel();
    const body = this.shadow.querySelector('.bs-panel-body');
    body.innerHTML = `
      <div class="bs-error">
        <h4>❌ 总结失败</h4>
        <p>${escapeHtml(msg)}</p>
        ${msg.includes('Failed to fetch') || msg.includes('NetworkError')
          ? '<p style="margin-top:1rem"><small>请确保后台服务已启动：<br/><code>cd ~/Desktop/cc && python3 server.py</code></small></p>'
          : ''}
      </div>`;
    this._show();
  }

  close() {
    if (this.host.parentNode) this.host.remove();
  }

  // --- internal ---

  _ensurePanel() {
    if (this.shadow.querySelector('.bs-panel')) return;
    this._injectStyles();

    const container = document.createElement('div');
    container.className = 'bili-summary-container';
    container.innerHTML = `
      <div class="bs-panel">
        <div class="bs-panel-header">
          <h3>📊 投资研究总结</h3>
          <div class="bs-panel-actions">
            <button id="bs-btn-min" title="收起">−</button>
            <button id="bs-btn-close" title="关闭">×</button>
          </div>
        </div>
        <div class="bs-panel-body"></div>
      </div>`;
    this.shadow.appendChild(container);

    // Drag
    const header = this.shadow.querySelector('.bs-panel-header');
    header.addEventListener('mousedown', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      this._dragging = true;
      const rect = this.shadow.querySelector('.bs-panel').getBoundingClientRect();
      this._offsetX = e.clientX - rect.left;
      this._offsetY = e.clientY - rect.top;
    });
    document.addEventListener('mousemove', (e) => {
      if (!this._dragging) return;
      const panel = this.shadow.querySelector('.bs-panel');
      panel.style.left = (e.clientX - this._offsetX) + 'px';
      panel.style.top = (e.clientY - this._offsetY) + 'px';
      panel.style.right = 'auto';
    });
    document.addEventListener('mouseup', () => { this._dragging = false; });

    // Buttons
    this.shadow.querySelector('#bs-btn-close').addEventListener('click', () => this.close());
    this.shadow.querySelector('#bs-btn-min').addEventListener('click', () => {
      const body = this.shadow.querySelector('.bs-panel-body');
      body.style.display = body.style.display === 'none' ? '' : 'none';
    });
  }

  _show() {
    if (!this.host.parentNode) document.body.appendChild(this.host);
  }
}

// ---- Trigger Button ----

class TriggerButton {
  constructor() {
    this.host = document.createElement('div');
    this.host.id = 'bs-trigger-host';
    this.shadow = this.host.attachShadow({ mode: 'open' });
    this.btn = null;
    this._rendered = false;
  }

  inject() {
    if (this._rendered) return;

    // Find injection point: near the video title / owner area
    // B站 layout: #video_toolbar or .video-info-container or .video-title
    const targets = [
      document.querySelector('.video-title'),
      document.querySelector('.video-info-title'),
      document.querySelector('#video_toolbar'),
      document.querySelector('.up-info-container'),
    ].filter(Boolean);

    const target = targets[0];
    if (!target) { setTimeout(() => this.inject(), 1000); return; }

    this._render();
    target.parentNode.insertBefore(this.host, target.nextSibling);
    this._rendered = true;
  }

  setLoading(loading) {
    const b = this.shadow.querySelector('.bs-trigger-btn');
    if (!b) return;
    b.disabled = loading;
    b.innerHTML = loading
      ? '<span class="spinner"></span>生成中…'
      : '🔬 投资总结';
  }

  // --- internal ---

  _render() {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = chrome.runtime.getURL('content.css');
    this.shadow.appendChild(link);

    const btn = document.createElement('button');
    btn.className = 'bs-trigger-btn';
    btn.textContent = '🔬 投资总结';
    btn.addEventListener('click', () => this._onClick());
    this.shadow.appendChild(btn);
    this.btn = btn;
  }

  async _onClick() {
    const bvid = getBvid();
    if (!bvid) return;

    this.setLoading(true);
    const panel = new SummaryPanel();
    panel.showLoading();

    try {
      const resp = await fetch(`${API_BASE}/api/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: bvid }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      panel.showResult(data.markdown);
    } catch (e) {
      panel.showError(e.message);
    } finally {
      this.setLoading(false);
    }
  }
}

// ---- SPA Navigation Detection ----

let currentPath = window.location.pathname;
let triggerBtn = null;

function onPageChange() {
  const wasVideo = /\/video\/BV/.test(currentPath);
  const isVideo = isVideoPage();

  // Remove old button if navigating away from video
  if (wasVideo && !isVideo && triggerBtn) {
    triggerBtn.host.remove();
    triggerBtn = null;
  }

  // Inject if navigating to a video page
  if (isVideo && !triggerBtn) {
    triggerBtn = new TriggerButton();
    // Wait for DOM to settle
    setTimeout(() => triggerBtn.inject(), 1500);
  }

  currentPath = window.location.pathname;
}

// Monitor for SPA navigation
function watchNavigation() {
  // 1. popstate
  window.addEventListener('popstate', onPageChange);

  // 2. PushState monkey-patch
  const origPush = history.pushState;
  history.pushState = function (...args) {
    origPush.apply(this, args);
    onPageChange();
  };
  const origReplace = history.replaceState;
  history.replaceState = function (...args) {
    origReplace.apply(this, args);
    onPageChange();
  };

  // 3. MutationObserver as fallback for URL changes
  let lastUrl = window.location.href;
  const obs = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      onPageChange();
    }
  });
  obs.observe(document.body, { childList: true, subtree: true });
}

// ---- Init ----

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

async function init() {
  if (isVideoPage()) {
    // Pre-warm: check server
    const online = await checkServer();
    if (!online) {
      console.log('📡 bili-summary 服务未启动。请运行: python3 server.py');
      // Still inject the button — click will show the error with instructions
    }

    triggerBtn = new TriggerButton();
    // Wait for B站 DOM to fully render
    setTimeout(() => triggerBtn.inject(), 2000);
  }

  watchNavigation();
}

init();

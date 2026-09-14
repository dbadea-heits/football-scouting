/* season-toggle.js — Football Intelligence season switcher
 *
 * Toggles between 2025-26 (historical, hardcoded in HTML) and
 * 2026-27 (live, loaded from data/season-2627.js preload or data/season-2627.json fetch).
 *
 * Usage:
 *   - Add <script src="data/season-2627.js"></script> BEFORE this script on each page.
 *   - Add <script src="season-toggle.js"></script> to each page.
 *   - Add data-player="player-id" to <body> on report pages.
 *   - Add data-player="player-id" to each .report-card on index.html.
 *   - Render toggle buttons with class .season-btn + data-season attribute.
 *   - Call window.setSeason(season) from button onclick handlers.
 */
(function () {
  'use strict';

  var LAST     = '2025-26';
  var CURR     = '2026-27';
  var LS_KEY   = 'fi-season';
  var SESS_KEY = 'fi-season-data';

  var _originals = null;

  /* ── Preference ───────────────────────────────────────────── */
  function getSeason() {
    try { return localStorage.getItem(LS_KEY) || LAST; } catch (e) { return LAST; }
  }

  function storeSeason(s) {
    try { localStorage.setItem(LS_KEY, s); } catch (e) {}
  }

  /* ── Data loading — preloaded JS (file://) or fetch (http/s) ── */
  function fetchData() {
    return new Promise(function (resolve) {
      /* Prefer inline global set by data/season-2627.js <script> tag.
         Works on file:// where fetch() is blocked by the browser. */
      if (window.FI_SEASON_DATA) { resolve(window.FI_SEASON_DATA); return; }

      try {
        var cached = sessionStorage.getItem(SESS_KEY);
        if (cached) { resolve(JSON.parse(cached)); return; }
      } catch (e) {}

      fetch('data/season-2627.json')
        .then(function (r) { return r.json(); })
        .then(function (d) {
          try { sessionStorage.setItem(SESS_KEY, JSON.stringify(d)); } catch (e) {}
          resolve(d);
        })
        .catch(function (err) {
          console.warn('[season-toggle] Could not load season data:', err);
          resolve(null);
        });
    });
  }

  /* ── Save / restore DOM originals ────────────────────────── */
  function saveOriginals() {
    if (_originals) return;
    _originals = {};

    /* Signal row on report pages */
    document.querySelectorAll('.signals > div').forEach(function (div, i) {
      var n = div.querySelector('.num');
      var p = div.querySelector('.pctl');
      if (n) _originals['sig-' + i + '-num']  = n.textContent;
      if (p) _originals['sig-' + i + '-pctl'] = p.textContent;
    });

    /* Card stat values on index hub */
    /* Card stat values + mins on index hub */
    document.querySelectorAll('.report-card[data-player]').forEach(function (card) {
      var pid = card.dataset.player;
      card.querySelectorAll('.card-stat-val').forEach(function (v, i) {
        _originals['card-' + pid + '-' + i + '-val'] = v.textContent;
        _originals['card-' + pid + '-' + i + '-cls'] = v.className;
      });
      var m = card.querySelector('.card-mins');
      if (m) _originals['card-' + pid + '-mins'] = m.textContent;
    });
  }

  function restoreOriginals() {
    if (!_originals) return;

    document.querySelectorAll('.signals > div').forEach(function (div, i) {
      var n = div.querySelector('.num');
      var p = div.querySelector('.pctl');
      var vn = _originals['sig-' + i + '-num'];
      var vp = _originals['sig-' + i + '-pctl'];
      if (n && vn != null) n.textContent = vn;
      if (p && vp != null) p.textContent = vp;
    });

    document.querySelectorAll('.report-card[data-player]').forEach(function (card) {
      var pid = card.dataset.player;
      card.querySelectorAll('.card-stat-val').forEach(function (v, i) {
        var ov = _originals['card-' + pid + '-' + i + '-val'];
        var oc = _originals['card-' + pid + '-' + i + '-cls'];
        if (ov != null) v.textContent = ov;
        if (oc != null) v.className   = oc;
      });
      var m = card.querySelector('.card-mins');
      var om = _originals['card-' + pid + '-mins'];
      if (m && om != null) m.textContent = om;
    });

    /* Remove injected current-season metrics block */
    document.querySelectorAll('.metrics-current').forEach(function (el) { el.remove(); });
  }

  /* ── Apply one player's current-season data ───────────────── */
  function applyPlayerData(pd) {
    /* Signal row */
    document.querySelectorAll('.signals > div').forEach(function (div, i) {
      var sig = pd.signals && pd.signals[i];
      if (!sig) return;
      var n = div.querySelector('.num');
      var p = div.querySelector('.pctl');
      if (n) n.textContent = sig.num;
      if (p) p.textContent = sig.pctl;
    });

    /* Inject current-season block into Full Metrics accordion */
    if (pd.current_block && pd.current_block.length > 0) {
      var allDetails = document.querySelectorAll('details');
      var metricsEl = null;
      for (var i = 0; i < allDetails.length; i++) {
        var lbl = allDetails[i].querySelector('summary .label');
        if (lbl && lbl.textContent.trim() === 'Full Metrics') {
          metricsEl = allDetails[i];
          break;
        }
      }
      if (metricsEl) {
        var body = metricsEl.querySelector('.body');
        if (body && !body.querySelector('.metrics-current')) {
          var wrapper = document.createElement('div');
          wrapper.className = 'metrics-current';
          var rows = pd.current_block.map(function (r) {
            return '<div class="mrow"><span>' + r.label + '</span>' +
                   '<span class="mv">' + r.val + '</span></div>';
          }).join('');
          wrapper.innerHTML = '<p class="mgroup">2026-27 · Current Season</p>' + rows;
          body.insertBefore(wrapper, body.firstChild);
        }
      }
    }
  }

  /* ── Sync toggle button state ─────────────────────────────── */
  function syncButtons(season) {
    document.querySelectorAll('.season-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.dataset.season === season);
    });
    document.body.dataset.season = season;
  }

  /* ── Main apply ──────────────────────────────────────────── */
  function applySeason(season) {
    storeSeason(season);
    syncButtons(season);

    if (season === CURR) {
      fetchData().then(function (data) {
        if (!data) return;
        saveOriginals();

        /* Single-player report pages */
        var pid = document.body.dataset.player;
        if (pid && data.players[pid]) {
          applyPlayerData(data.players[pid]);
        }

        /* Hub index: multiple cards */
        document.querySelectorAll('.report-card[data-player]').forEach(function (card) {
          var cpid = card.dataset.player;
          var pd = data.players[cpid];
          if (!pd || !pd.card) return;
          card.querySelectorAll('.card-stat-val').forEach(function (v, i) {
            var s = pd.card[i];
            if (!s) return;
            v.textContent = s.val;
            v.className = 'card-stat-val' + (s.cls ? ' ' + s.cls : '');
          });
          var m = card.querySelector('.card-mins');
          if (m && pd.mins != null) m.textContent = pd.mins;
        });
      });
    } else {
      restoreOriginals();
    }
  }

  /* ── Public API ──────────────────────────────────────────── */
  window.setSeason = applySeason;

  /* ── Boot on DOMContentLoaded ────────────────────────────── */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { applySeason(getSeason()); });
  } else {
    applySeason(getSeason());
  }
})();

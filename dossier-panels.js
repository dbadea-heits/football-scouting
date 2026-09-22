/* dossier-panels.js — desktop report section inspector */
(function () {
  'use strict';

  var breakpoint = window.matchMedia('(min-width: 1280px)');
  var panel = document.querySelector('.rail-inspector');
  if (!panel) return;

  var panelTitle = panel.querySelector('.panel-title');
  var panelContent = panel.querySelector('.panel-content');
  var closeButton = panel.querySelector('.panel-close');
  var details = Array.prototype.slice.call(document.querySelectorAll('.col details'));
  var active = null;

  function setPanelState(isActive) {
    panel.classList.toggle('is-active', isActive);
    panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
  }

  function restoreActive() {
    if (!active) return;
    if (active.placeholder.parentNode) {
      active.placeholder.parentNode.insertBefore(active.body, active.placeholder.nextSibling);
    }
    active.placeholder.remove();
    active = null;
    panelTitle.textContent = '';
    panelContent.textContent = '';
    setPanelState(false);
  }

  var SWITCH_MS = 150;

  function mountDetail(detail) {
    restoreActive();
    details.forEach(function (other) {
      if (other !== detail) other.open = false;
    });

    var body = detail.querySelector('.body');
    if (!body) return;

    var summaryLabel = detail.querySelector('summary .label');
    var placeholder = document.createComment('Expanded section placeholder');
    body.parentNode.insertBefore(placeholder, body);
    panelContent.appendChild(body);
    panelTitle.textContent = summaryLabel ? summaryLabel.textContent.trim() : 'Section details';
    active = { detail: detail, body: body, placeholder: placeholder };
    setPanelState(true);
  }

  function fadeIn() {
    panelContent.classList.add('is-switching');
    void panelContent.offsetHeight; /* flush so opacity:0 commits before the class lifts */
    requestAnimationFrame(function () {
      panelContent.classList.remove('is-switching');
    });
  }

  function openInPanel(detail) {
    if (!breakpoint.matches) return;
    if (active && active.detail === detail) return;

    if (panel.classList.contains('is-active')) {
      /* another section is already showing — fade it out, then swap and fade in */
      panelContent.classList.add('is-switching');
      window.setTimeout(function () {
        mountDetail(detail);
        fadeIn();
      }, SWITCH_MS);
    } else {
      mountDetail(detail);
      fadeIn();
    }
  }

  function closeFromDetail(detail) {
    if (!active || active.detail !== detail) return;
    panelContent.classList.add('is-switching');
    window.setTimeout(restoreActive, SWITCH_MS);
  }

  function syncLayout() {
    if (!breakpoint.matches) {
      restoreActive();
      return;
    }
    var openDetail = details.find(function (detail) { return detail.open; });
    if (openDetail) openInPanel(openDetail);
  }

  details.forEach(function (detail) {
    detail.addEventListener('toggle', function () {
      if (detail.open) openInPanel(detail);
      else closeFromDetail(detail);
    });
  });

  closeButton.addEventListener('click', function () {
    if (active) active.detail.open = false;
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && active) active.detail.open = false;
  });

  if (breakpoint.addEventListener) breakpoint.addEventListener('change', syncLayout);
  else breakpoint.addListener(syncLayout);
  syncLayout();
})();

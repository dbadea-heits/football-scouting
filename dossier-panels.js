/* dossier-panels.js — desktop report section inspector */
(function () {
  'use strict';

  var breakpoint = window.matchMedia('(min-width: 1280px)');
  var panel = document.querySelector('.rail-inspector');
  if (!panel) return;

  var scrim = document.querySelector('.drawer-scrim');
  var panelTitle = panel.querySelector('.panel-title');
  var panelContent = panel.querySelector('.panel-content');
  var closeButton = panel.querySelector('.panel-close');
  var details = Array.prototype.slice.call(document.querySelectorAll('.col details'));
  var active = null;

  function setPanelState(isActive) {
    panel.classList.toggle('is-active', isActive);
    panel.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    if (scrim) {
      scrim.classList.toggle('is-active', isActive);
      scrim.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    }
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

  function openInPanel(detail) {
    if (!breakpoint.matches) return;
    if (active && active.detail === detail) return;

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

  function closeFromDetail(detail) {
    if (active && active.detail === detail) restoreActive();
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
  if (scrim) {
    scrim.addEventListener('click', function () {
      if (active) active.detail.open = false;
    });
  }
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && active) active.detail.open = false;
  });

  if (breakpoint.addEventListener) breakpoint.addEventListener('change', syncLayout);
  else breakpoint.addListener(syncLayout);
  syncLayout();
})();

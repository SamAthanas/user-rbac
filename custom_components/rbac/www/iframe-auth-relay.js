/**
 * Rewrites the RBAC panel iframe to a one-time authenticated URL (Companion app).
 */
(function () {
  "use strict";

  const ORIGIN = window.location.origin;
  const RBAC_PANEL_RE = /\/api\/rbac\/panel/;

  function getAccessToken() {
    try {
      const el = document.querySelector("home-assistant");
      const hass = (el && el.hass) || window.hass;
      return hass && hass.auth && hass.auth.accessToken;
    } catch (e) {
      return null;
    }
  }

  async function fetchPanelUrl() {
    const accessToken = getAccessToken();
    if (!accessToken) {
      return null;
    }
    try {
      const response = await fetch("/api/rbac/panel-token", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + accessToken,
          "Content-Type": "application/json",
        },
        credentials: "same-origin",
      });
      if (!response.ok) {
        return null;
      }
      const data = await response.json();
      return data.url || null;
    } catch (e) {
      return null;
    }
  }

  async function redirectIframeWithToken(frame) {
    const src = frame.getAttribute("src") || "";
    if (!RBAC_PANEL_RE.test(src) || /[?&]t=/.test(src)) {
      return;
    }
    const panelUrl = await fetchPanelUrl();
    if (panelUrl && frame.src !== ORIGIN + panelUrl && !frame.src.endsWith(panelUrl)) {
      frame.src = panelUrl;
    }
  }

  function relayToIframes() {
    document.querySelectorAll("iframe").forEach((frame) => {
      redirectIframeWithToken(frame);
    });
  }

  window.addEventListener("message", async (event) => {
    if (event.origin !== ORIGIN || !event.data) {
      return;
    }
    if (event.data.type === "rbac-panel-token-request") {
      const panelUrl = await fetchPanelUrl();
      if (panelUrl && event.source && event.source.postMessage) {
        event.source.postMessage(
          { type: "rbac-panel-redirect", url: panelUrl },
          ORIGIN
        );
      }
    }
  });

  const observer = new MutationObserver(relayToIframes);

  function start() {
    const root = document.querySelector("home-assistant") || document.body;
    observer.observe(root, { childList: true, subtree: true });
    relayToIframes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }

  window.addEventListener("popstate", relayToIframes);
  setInterval(relayToIframes, 2000);
})();

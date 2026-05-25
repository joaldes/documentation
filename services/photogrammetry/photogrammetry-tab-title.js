/**
 * photogrammetry-tab-title (v5.24)
 *
 * Tiny Lovelace custom element that drives `document.title` from an HA sensor
 * so the Chrome tab title / OS taskbar shows live capture progress without
 * needing to focus the dashboard tab.
 *
 * Usage in a dashboard view:
 *
 *   - type: custom:photogrammetry-tab-title
 *     entity: sensor.photogrammetry_progress
 *     idle_title: "Photogrammetry"
 *     active_format: "{pct}% • Photogrammetry"
 *
 * Behaviour:
 *   - Numeric state in (0, 100): title = active_format with {pct} replaced.
 *   - Idle / unknown / unavailable / 0 / >=100: title = idle_title.
 *   - Prior `document.title` is snapshotted in connectedCallback (per
 *     DOM-lifecycle) and restored in disconnectedCallback so navigating
 *     away from the dashboard cleans up. Saving in setConfig would let
 *     a later-mounted instance corrupt the saved prior — don't do that.
 *
 * Deploy as: <HA-config>/www/photogrammetry-tab-title.js
 * Register : Settings → Dashboards → ⋮ → Resources → Add
 *            URL  /local/photogrammetry-tab-title.js
 *            Type JavaScript Module
 */
class PhotogrammetryTabTitle extends HTMLElement {
  setConfig(cfg) {
    if (!cfg || !cfg.entity) throw new Error("entity required");
    this._cfg = {
      idle_title: "Photogrammetry",
      active_format: "{pct}% • Photogrammetry",
      ...cfg,
    };
    this.style.display = "none";
  }

  connectedCallback() {
    this._priorTitle = document.title;
  }

  set hass(hass) {
    if (!this._cfg) return;
    const s = hass && hass.states && hass.states[this._cfg.entity];
    const raw = s ? parseFloat(s.state) : NaN;
    if (Number.isFinite(raw) && raw > 0 && raw < 100) {
      document.title = this._cfg.active_format.replace("{pct}", raw.toFixed(0));
    } else {
      document.title = this._cfg.idle_title;
    }
  }

  disconnectedCallback() {
    if (this._priorTitle !== undefined) document.title = this._priorTitle;
  }

  getCardSize() {
    return 0;
  }
}

customElements.define("photogrammetry-tab-title", PhotogrammetryTabTitle);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "photogrammetry-tab-title",
  name: "Photogrammetry Tab Title",
  description: "Reflects a sensor's % into the browser tab title.",
});

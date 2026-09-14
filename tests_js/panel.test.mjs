import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const source = await readFile(new URL("../custom_components/aqara_talk/frontend/panel.js", import.meta.url), "utf8");

function fixture() {
  class Element {
    constructor(tag = "div") { this.tagName = tag; this.children = []; this.listeners = new Map(); this.isConnected = true; this.value = ""; }
    attachShadow() { return (this.shadowRoot = new Element()); }
    append(child) { this.children.push(child); child.parent = this; if (this.tagName === "select" && !this.value) this.value = child.value; }
    remove() { this.removed = true; if (this.parent) this.parent.children = this.parent.children.filter((item) => item !== this); }
    replaceChildren() { this.children = []; }
    setAttribute() {}
    addEventListener(name, callback) { this.listeners.set(name, callback); }
    removeEventListener(name) { this.listeners.delete(name); }
    focus() { this.focused = true; }
    select() { this.selected = true; }
    set innerHTML(value) { this.html = value; this.children = []; }
  }
  const registry = new Map();
  const waiting = new Map();
  const context = vm.createContext({
    HTMLElement: Element, URL, console, setTimeout, clearTimeout,
    navigator: {},
    window: { location: { href: "https://ha.example/aqara-talk" }, isSecureContext: true },
    document: { createElement: (tag) => new Element(tag), head: new Element("head") },
    customElements: {
      get: (name) => registry.get(name),
      define: (name, value) => { registry.set(name, value); waiting.get(name)?.(); },
      whenDefined: (name) => registry.has(name) ? Promise.resolve() : new Promise((resolve) => waiting.set(name, resolve)),
    },
  });
  vm.runInContext(source, context);
  const Panel = registry.get("aqara-talk-panel");
  const panel = new Panel();
  panel._started = true;
  panel._player = new Element();
  panel._notice = new Element();
  return { context, panel, Element, ensureCard: vm.runInContext("ensureCard", context) };
}

test("already registered card skips resource request; errors distinguish registry and missing resources", async () => {
  const { context, ensureCard } = fixture();
  context.customElements.define("webrtc-camera", class {});
  await ensureCard({ callWS: () => assert.fail("unnecessary registry read") }, "webrtc-camera");
  await assert.rejects(ensureCard({ callWS: async () => { throw Error(); } }, "advanced-camera-card"), /resource_unavailable/);
  await assert.rejects(ensureCard({ callWS: async () => [] }, "advanced-camera-card"), /resource_missing/);
  await assert.rejects(ensureCard({ callWS: async () => [] }, "unknown-card"), /card_failed/);
});

test("loads exact registered filename including query once and waits for element registration", async () => {
  const { context, ensureCard } = fixture();
  const hass = { callWS: async () => [
    { url: "/hacsfiles/advanced-camera-card.js.evil" },
    { url: "/hacsfiles/advanced-camera-card/advanced-camera-card.js?v=42" },
  ] };
  const first = ensureCard(hass, "advanced-camera-card");
  const second = ensureCard(hass, "advanced-camera-card");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(context.document.head.children.length, 1);
  assert.equal(context.document.head.children[0].src, "/hacsfiles/advanced-camera-card/advanced-camera-card.js?v=42");
  context.customElements.define("advanced-camera-card", class {});
  await Promise.all([first, second]);
});

test("failed script can be retried", async () => {
  const { context, ensureCard } = fixture();
  const hass = { callWS: async () => [{ url: "/local/webrtc-camera.js" }] };
  const load = ensureCard(hass, "webrtc-camera");
  await new Promise((resolve) => setImmediate(resolve));
  context.document.head.children[0].onerror();
  await assert.rejects(load, /resource_failed/);
  const retry = ensureCard(hass, "webrtc-camera");
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(context.document.head.children.length, 1);
  context.customElements.define("webrtc-camera", class {});
  await retry;
});

test("card gets current hass, rebuild replaces it, disconnect removes it", async () => {
  const { panel, context, Element } = fixture();
  context.customElements.define("webrtc-camera", class {});
  context.window.loadCardHelpers = async () => ({ createCardElement: () => new Element("webrtc-camera") });
  const setup = { status: "ready_to_test", card: { type: "custom:webrtc-camera" } };
  panel.hass = { language: "en" };
  panel._setup = setup;
  await panel.mountCard(setup, 0);
  const first = panel._card;
  const nextHass = { language: "pl" };
  panel.hass = nextHass;
  assert.equal(first.hass, nextHass);
  first.listeners.get("ll-rebuild")();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(first.removed, true);
  assert.notEqual(panel._card, first);
  assert.equal(panel._player.children.length, 1);
  const second = panel._card;
  panel.isConnected = false;
  panel.disconnectedCallback();
  assert.equal(second.removed, true);
  assert.equal(second.listeners.size, 0);
  assert.equal(panel._card, null);
});

test("selection generation prevents a pending helper from mounting stale media", async () => {
  const { panel, context, Element } = fixture();
  context.customElements.define("webrtc-camera", class {});
  let finish;
  context.window.loadCardHelpers = () => new Promise((resolve) => { finish = resolve; });
  panel.hass = {};
  const mounting = panel.mountCard({ card: { type: "custom:webrtc-camera" } }, 0);
  await new Promise((resolve) => setImmediate(resolve));
  ++panel._generation;
  finish({ createCardElement: () => new Element() });
  await mounting;
  assert.equal(panel._player.children.length, 0);
});

test("setup failure status never creates player and snippet stays text; clipboard falls back", async () => {
  const { panel, Element } = fixture();
  panel._picker = { value: "entry" };
  panel._check = {};
  panel._status = new Element();
  panel._content = new Element();
  panel.hass = { language: "pl", callWS: async () => ({ status: "integration_missing", runtime_yaml: "<script>unsafe</script>", card: { type: "custom:webrtc-camera" } }) };
  panel.mountCard = () => assert.fail("must not mount without backing integration");
  await panel.refresh();
  assert.match(panel._status.textContent, /Brakuje wymaganej integracji/);
  assert.equal(panel._content.children[0].children.find(child => child.tagName.toLowerCase() === "pre").textContent, "<script>unsafe</script>");
  assert.equal(panel._check.disabled, false);
  await panel.copy("exact config");
  const area = panel._notice.children[0];
  assert.equal(area.value, "exact config");
  assert.equal(area.readOnly, true);
  assert.equal(area.selected, true);
});

test("all backend statuses have both translations", () => {
  const { context } = fixture();
  assert.equal(vm.runInContext("JSON.stringify(Object.keys(TEXT.en).sort()) === JSON.stringify(Object.keys(TEXT.pl).sort())", context), true);
  for (const status of ["unconfigured", "ready_to_test", "talk_stream_missing", "video_stream_missing", "camera_missing", "integration_missing", "frigate_client_incompatible", "cannot_connect", "invalid_response", "unauthorized", "invalid_url", "runtime_changed", "camera_unavailable", "video_camera_mismatch", "talk_camera_mismatch", "redirect_not_allowed"]) {
    assert.equal(vm.runInContext(`typeof TEXT.en.${status}`, context), "string");
  }
});

const TEXT = {
  en: {
    choose: "Device", configure: "Configure", add: "Add device", recheck: "Recheck",
    loading: "Checking configuration…", empty: "Add an Aqara Talk device to begin.",
    failed: "Could not read setup. Check your connection and administrator access, then retry.",
    snippet: "Runtime configuration", copy: "Copy", copyCard: "Copy card JSON", streams: "Available streams",
    copied: "Copied.", select: "Select and copy the text below.",
    boundary: "The runtime needs read access to the bridge and settings directories in the generated command. HACS installs them in Home Assistant; mount both directories read-only in an external runtime. Merge this YAML with existing streams, then restart and recheck.",
    frigateHelp: "Frigate includes Python and FFmpeg. Enable its go2rtc exec option and verify the generated Home Assistant app paths; Docker installations need their own mounts and FFmpeg path.",
    go2rtcHelp: "Provide Python 3 and FFmpeg in the go2rtc runtime and allow this bridge executable. The built-in Home Assistant go2rtc cannot host this custom exec configuration.",
    guide: "Runtime setup instructions",
    test: "Ready for a call test. Video and configuration checks do not verify two-way sound. Use the card controls to start and end a call.",
    insecure: "Microphone access requires HTTPS or localhost. Open Home Assistant securely before testing a call.",
    resource_missing: "The player card resource is not registered. Install the card with HACS, add its Lovelace resource, then recheck.",
    resource_unavailable: "Cannot read Lovelace resources. Check administrator access and resource configuration, then recheck.",
    resource_failed: "The registered player resource did not load. Check its URL and browser console, then recheck.",
    card_failed: "The player could not be created. Check the installed card version and configuration, then recheck.",
    unconfigured: "Select a camera and configure its runtime through Configure.",
    ready_to_test: "Configuration ready",
    talk_stream_missing: "The talk stream is missing. Apply the runtime configuration below, restart the runtime and recheck.",
    video_stream_missing: "The selected video stream is missing. Check available streams and select the correct stream through Configure.",
    camera_unavailable: "The camera is offline. Restore its connection and recheck.",
    video_camera_mismatch: "The video stream targets another camera. Reconfigure the video stream and camera address.",
    camera_missing: "The camera entity is unavailable. Restore it or select a camera through Configure.",
    integration_missing: "The required backing integration is missing. Install/configure Frigate or WebRTC Camera for the selected player.",
    frigate_client_incompatible: "The installed Frigate integration cannot provide discovery. Reload or update it, then recheck.",
    runtime_changed: "The camera moved to a different Frigate instance. Reconfigure Aqara Talk before testing a call.",
    talk_camera_mismatch: "The talk stream targets another camera. Reconfigure and select the matching stream or leave it empty.",
    redirect_not_allowed: "The API redirects to another address. Configure its final URL and recheck.",
    cannot_connect: "Cannot connect to the runtime. Check its address, network and service, then recheck.",
    invalid_response: "The runtime returned an unexpected response. Check the API address and runtime version.",
    unauthorized: "The runtime rejected access. Repair authentication in its integration or runtime settings.",
    invalid_url: "The runtime URL is invalid. Configure a supported HTTP or HTTPS API address.",
  },
  pl: {
    choose: "Urządzenie", configure: "Konfiguruj", add: "Dodaj urządzenie", recheck: "Sprawdź ponownie",
    loading: "Sprawdzanie konfiguracji…", empty: "Dodaj urządzenie Aqara Talk, aby rozpocząć.",
    failed: "Nie można odczytać konfiguracji. Sprawdź połączenie i uprawnienia administratora, potem ponów próbę.",
    snippet: "Konfiguracja środowiska", copy: "Kopiuj", copyCard: "Kopiuj JSON karty", streams: "Dostępne strumienie",
    copied: "Skopiowano.", select: "Zaznacz i skopiuj tekst poniżej.",
    boundary: "Serwer wymaga odczytu katalogów mostu i ustawień wskazanych w poleceniu. HACS instaluje je w HA; na zewnętrznym serwerze zamontuj oba katalogi tylko do odczytu. Połącz ten YAML z istniejącymi strumieniami, zrestartuj serwer i sprawdź ponownie.",
    frigateHelp: "Frigate zawiera Python i FFmpeg. Włącz opcję go2rtc exec i sprawdź wygenerowane ścieżki aplikacji HA. Instalacja Docker wymaga własnych montowań i ścieżki FFmpeg.",
    go2rtcHelp: "Zapewnij Python 3 i FFmpeg na serwerze go2rtc i zezwól na uruchamianie mostu. Wbudowany w HA go2rtc nie obsługuje tej konfiguracji exec.",
    guide: "Instrukcja konfiguracji serwera",
    test: "Gotowe do próby rozmowy. Obraz i sprawdzenie konfiguracji nie potwierdzają dźwięku w obu kierunkach. Rozpocznij i zakończ rozmowę przyciskami karty.",
    insecure: "Mikrofon wymaga HTTPS lub localhost. Przed próbą rozmowy otwórz Home Assistanta przez bezpieczne połączenie.",
    resource_missing: "Zasób karty odtwarzacza nie jest zarejestrowany. Zainstaluj kartę przez HACS, dodaj jej zasób Lovelace i ponów sprawdzenie.",
    resource_unavailable: "Nie można odczytać zasobów Lovelace. Sprawdź uprawnienia administratora i konfigurację zasobów, potem ponów sprawdzenie.",
    resource_failed: "Zarejestrowany zasób odtwarzacza nie załadował się. Sprawdź jego adres i konsolę przeglądarki, potem ponów sprawdzenie.",
    card_failed: "Nie można utworzyć odtwarzacza. Sprawdź wersję zainstalowanej karty i jej konfigurację, potem ponów sprawdzenie.",
    unconfigured: "Wybierz kamerę i skonfiguruj jej środowisko przez Konfiguruj.",
    ready_to_test: "Konfiguracja gotowa",
    talk_stream_missing: "Brakuje strumienia rozmowy. Zastosuj konfigurację poniżej, uruchom środowisko ponownie i ponów sprawdzenie.",
    video_stream_missing: "Brakuje wybranego strumienia obrazu. Sprawdź dostępne strumienie i wybierz właściwy przez Konfiguruj.",
    camera_unavailable: "Kamera jest offline. Przywróć jej połączenie i sprawdź ponownie.",
    video_camera_mismatch: "Strumień obrazu wskazuje inną kamerę. Zrekonfiguruj strumień i adres kamery.",
    camera_missing: "Encja kamery jest niedostępna. Przywróć ją lub wybierz kamerę przez Konfiguruj.",
    integration_missing: "Brakuje wymaganej integracji. Zainstaluj i skonfiguruj Frigate lub WebRTC Camera dla wybranego odtwarzacza.",
    frigate_client_incompatible: "Zainstalowana integracja Frigate nie obsługuje wykrywania. Przeładuj lub zaktualizuj ją i sprawdź ponownie.",
    runtime_changed: "Kamera została przeniesiona do innej instancji Frigate. Przed rozmową zrekonfiguruj Aqara Talk.",
    talk_camera_mismatch: "Strumień rozmowy wskazuje inną kamerę. W rekonfiguracji wybierz właściwy strumień lub pozostaw pole puste.",
    redirect_not_allowed: "API przekierowuje pod inny adres. Podaj adres docelowy i sprawdź ponownie.",
    cannot_connect: "Brak połączenia ze środowiskiem. Sprawdź adres, sieć i usługę, potem ponów sprawdzenie.",
    invalid_response: "Środowisko zwróciło nieoczekiwaną odpowiedź. Sprawdź adres API i wersję środowiska.",
    unauthorized: "Środowisko odmówiło dostępu. Napraw uwierzytelnianie w jego integracji lub ustawieniach.",
    invalid_url: "Adres środowiska jest nieprawidłowy. Podaj obsługiwany adres API HTTP lub HTTPS.",
  },
};

const resourceLoads = new Map();
const CARD_FILES = {
  "advanced-camera-card": "advanced-camera-card.js",
  "webrtc-camera": "webrtc-camera.js",
};

async function ensureCard(hass, type) {
  if (!CARD_FILES[type]) throw new Error("card_failed");
  if (customElements.get(type)) return;
  let resources;
  try { resources = await hass.callWS({ type: "lovelace/resources" }); }
  catch { throw new Error("resource_unavailable"); }
  if (!Array.isArray(resources)) throw new Error("resource_unavailable");
  const resource = resources.find((item) => {
    try {
      const url = new URL(item.url, window.location.href);
      return ["http:", "https:"].includes(url.protocol)
        && url.pathname.split("/").pop() === CARD_FILES[type];
    } catch { return false; }
  });
  if (!resource) throw new Error("resource_missing");
  if (!resourceLoads.has(resource.url)) {
    const loading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      let settled = false;
      const timer = setTimeout(() => finish(false), 15000);
      const finish = (ok) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        script.onerror = null;
        if (ok) resolve();
        else { script.remove(); reject(new Error("resource_failed")); }
      };
      script.type = "module";
      script.src = resource.url;
      script.onerror = () => finish(false);
      customElements.whenDefined(type).then(() => finish(true));
      document.head.append(script);
    });
    resourceLoads.set(resource.url, loading);
    loading.catch(() => resourceLoads.delete(resource.url));
  }
  await resourceLoads.get(resource.url);
}

class AqaraTalkPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._generation = 0;
    this._rebuild = () => {
      const setup = this._setup;
      const generation = ++this._generation;
      this.clearCard();
      if (setup?.status === "ready_to_test") this.mountCard(setup, generation);
    };
  }

  set hass(value) {
    this._hass = value;
    if (this._card) this._card.hass = value;
    if (this.isConnected && !this._started) this.start();
  }

  connectedCallback() { if (this._hass && !this._started) this.start(); }
  disconnectedCallback() {
    ++this._generation;
    this.clearCard();
    this._started = false;
  }

  t(key) { return TEXT[this._hass?.language?.startsWith("pl") ? "pl" : "en"][key] || TEXT.en.failed; }
  node(tag, text, parent) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (parent) parent.append(node);
    return node;
  }

  async start() {
    this._started = true;
    this.shadowRoot.innerHTML = `<style>
      :host{display:block;height:100%;overflow:auto;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif)}
      main{max-width:900px;margin:auto;padding:24px;box-sizing:border-box}h1{font-size:26px;margin:0 0 20px}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
      button,select,a{font:inherit}button,select{min-height:44px;padding:8px 14px;border:1px solid var(--divider-color,#888);border-radius:10px;background:var(--card-background-color);color:inherit}button{cursor:pointer}button:disabled{opacity:.6;cursor:wait}a{color:var(--primary-color);padding:10px 0}
      label{display:flex;gap:10px;align-items:center}select{max-width:100%}p{line-height:1.5}section,details{margin-top:20px;padding:18px;border:1px solid var(--divider-color,#888);border-radius:16px;background:var(--card-background-color)}summary{cursor:pointer;min-height:32px;font-weight:600}pre{overflow:auto;white-space:pre;line-height:1.5}textarea{width:100%;box-sizing:border-box;min-height:150px;font:inherit}#player{margin-top:20px}#player:empty{display:none}.warning{border-left:4px solid var(--warning-color,#e6a23c);padding-left:12px}#notice:empty{display:none}@media(max-width:500px){main{padding:16px}label{width:100%}select{flex:1;min-width:0}}
    </style>`;
    const main = this.node("main", undefined, this.shadowRoot);
    this.node("h1", "Aqara Talk", main);
    const nav = this.node("nav", undefined, main);
    const label = this.node("label", this.t("choose"), nav);
    this._picker = this.node("select", undefined, label);
    this._picker.onchange = () => this.refresh();
    this._check = this.node("button", this.t("recheck"), nav);
    this._check.onclick = () => this.refresh();
    const configure = this.node("a", this.t("configure"), nav);
    configure.href = "/config/integrations/integration/aqara_talk";
    const add = this.node("a", this.t("add"), nav);
    add.href = "/config/integrations/dashboard/add?domain=aqara_talk";
    this._status = this.node("p", this.t("loading"), main);
    this._status.setAttribute("role", "status");
    this._content = this.node("div", undefined, main);
    this._player = this.node("div", undefined, main);
    this._player.id = "player";
    this._notice = this.node("p", undefined, main);
    this._notice.id = "notice";
    this._notice.setAttribute("role", "status");
    const generation = ++this._generation;
    this._check.disabled = true;
    try {
      const result = await this._hass.callWS({ type: "aqara_talk/list" });
      if (!this.current(generation)) return;
      for (const entry of result.entries) {
        const option = this.node("option", entry.title, this._picker);
        option.value = entry.entry_id;
      }
      if (result.entries.length) await this.refresh();
      else this._status.textContent = this.t("empty");
    } catch { if (this.current(generation)) this._status.textContent = this.t("failed"); }
    finally { if (this.current(generation)) this._check.disabled = false; }
  }

  current(generation) { return this.isConnected && generation === this._generation; }
  clearCard() {
    if (this._card) {
      this._card.removeEventListener("ll-rebuild", this._rebuild);
      this._card.remove();
      this._card = null;
    }
  }

  async refresh() {
    if (!this._picker.value) { this.start(); return; }
    const generation = ++this._generation;
    this.clearCard();
    this._setup = null;
    this._content.replaceChildren();
    this._notice.textContent = "";
    this._status.textContent = this.t("loading");
    this._check.disabled = true;
    try {
      const setup = await this._hass.callWS({ type: "aqara_talk/setup", entry_id: this._picker.value });
      if (!this.current(generation)) return;
      this._setup = setup;
      this._status.textContent = this.t(setup.status);
      if (setup.streams?.length && setup.status !== "ready_to_test") {
        this.node("p", `${this.t("streams")}: ${setup.streams.join(", ")}`, this._content);
      }
      if (setup.runtime_yaml) {
        const details = this.node("details", undefined, this._content);
        this.node("summary", this.t("snippet"), details);
        this.node("p", this.t("boundary"), details);
        this.node("p", this.t(setup.runtime_kind === "frigate" ? "frigateHelp" : "go2rtcHelp"), details);
        const guide = this.node("a", this.t("guide"), details);
        guide.href = "https://github.com/fszalaj/aqara-talk/blob/main/docs/setup.md";
        guide.target = "_blank";
        guide.rel = "noopener noreferrer";
        this.node("pre", setup.runtime_yaml, details);
        const copy = this.node("button", this.t("copy"), details);
        copy.onclick = () => this.copy(setup.runtime_yaml);
      }
      if (setup.card) {
        const copy = this.node("button", this.t("copyCard"), this._content);
        copy.onclick = () => this.copy(JSON.stringify(setup.card, null, 2));
      }
      if (setup.status === "ready_to_test") {
        this.node("p", this.t("test"), this._content);
        if (!window.isSecureContext) this.node("p", this.t("insecure"), this._content).className = "warning";
        await this.mountCard(setup, generation);
      }
    } catch { if (this.current(generation)) this._status.textContent = this.t("failed"); }
    finally { if (this.current(generation)) this._check.disabled = false; }
  }

  async mountCard(setup, generation) {
    try {
      if (!setup.card) throw new Error("card_failed");
      const type = setup.card.type?.replace(/^custom:/, "");
      await ensureCard(this._hass, type);
      if (!this.current(generation)) return;
      const helpers = await window.loadCardHelpers();
      if (!this.current(generation)) return;
      const card = helpers.createCardElement(setup.card);
      if (!card || card.tagName?.toLowerCase() === "hui-error-card") throw new Error("card_failed");
      card.hass = this._hass;
      card.addEventListener("ll-rebuild", this._rebuild);
      this._card = card;
      this._player.append(card);
    } catch (error) {
      if (!this.current(generation)) return;
      this._notice.textContent = this.t(error.message in TEXT.en ? error.message : "card_failed");
      if (error.message === "resource_missing") {
        const link = this.node("a", "HACS", this._notice);
        link.href = "/hacs";
      }
    }
  }

  async copy(text) {
    const generation = this._generation;
    try {
      await navigator.clipboard.writeText(text);
      if (this.current(generation)) this._notice.textContent = this.t("copied");
    } catch {
      if (!this.current(generation)) return;
      this._notice.textContent = this.t("select");
      const area = this.node("textarea", undefined, this._notice);
      area.value = text;
      area.readOnly = true;
      area.setAttribute("aria-label", this.t("select"));
      area.focus();
      area.select();
    }
  }
}

if (!customElements.get("aqara-talk-panel")) customElements.define("aqara-talk-panel", AqaraTalkPanel);

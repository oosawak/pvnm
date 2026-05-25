(function () {
  "use strict";

  const assets = window.PVNM_AUDIO_ASSETS || {};
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  const userAgent = typeof navigator === "object"
    ? String(navigator.userAgent || "")
    : "";
  const preferHtmlBgm = Boolean(window.Capacitor) || /Android/i.test(userAgent);
  let audioContext = null;
  let audioUnlocked = false;
  let unlockGestureCount = 0;
  let lastUnlockError = "";
  let backendName = preferHtmlBgm ? "html" : (AudioContextCtor ? "webaudio" : "html");
  let lastBgmInfo = {
    path: "",
    url: "",
    status: "none",
    backend: backendName,
    error: "",
    webError: "",
    htmlError: "",
  };

  let bgm = null;
  let bgmUrl = "";
  let webBgm = null;
  let webBgmToken = 0;
  let pendingBgm = null;
  let appActive = typeof document === "object"
    ? document.visibilityState !== "hidden"
    : true;
  let lifecyclePaused = false;
  let lifecycleHtmlBgmPaused = false;
  let lifecycleWebBgmPaused = false;
  const sePlayers = new Set();
  const seNodes = new Set();
  const decodedBuffers = new Map();
  const debugLogLimit = 300;
  let memoryDebugLog = [];

  function debugLogKey() {
    const namespace = String(
      window.PVNM_STORAGE_NAMESPACE || "pvnm:debug:"
    );
    return namespace + "__debug_log.json";
  }

  function readDebugLogEntries() {
    try {
      const raw = window.localStorage.getItem(debugLogKey());
      const entries = raw ? JSON.parse(raw) : [];
      return Array.isArray(entries) ? entries : [];
    } catch (_err) {
      return memoryDebugLog.slice();
    }
  }

  function writeDebugLogEntries(entries) {
    const trimmed = entries.slice(-debugLogLimit);
    memoryDebugLog = trimmed.slice();
    try {
      window.localStorage.setItem(debugLogKey(), JSON.stringify(trimmed));
    } catch (_err) {
      /* keep memory fallback */
    }
  }

  function debugLog(type, detail) {
    const entry = {
      t: new Date().toISOString(),
      type: String(type || "event"),
      detail: detail || {},
    };
    const entries = readDebugLogEntries();
    entries.push(entry);
    writeDebugLogEntries(entries);
  }

  function startupMark(label, detail) {
    try {
      const api = window.PVNM_STARTUP;
      const mark = api && api.mark;
      if (typeof mark === "function") {
        mark(label, detail || {});
      }
    } catch (_err) {
      /* ignore */
    }
  }

  function debugLogText() {
    return readDebugLogEntries()
      .map(function (entry) {
        let detail = "";
        try {
          detail = JSON.stringify(entry.detail || {}, null, 2);
        } catch (_err) {
          detail = String(entry.detail || "");
        }
        return "[" + (entry.t || "-") + "] " +
          (entry.type || "event") + "\n" + detail;
      })
      .join("\n\n");
  }

  function normalizePath(path) {
    let value = String(path || "")
      .replace(/\\/g, "/")
      .replace(/^file:\/\//, "");
    value = safeDecode(value);
    try {
      value = value.normalize("NFC");
    } catch (_err) {
      /* ignore */
    }
    value = value.replace(/\/+/g, "/");
    while (value.includes("/./")) {
      value = value.replace(/\/\.\//g, "/");
    }
    value = value.replace(/^\.\//, "").replace(/^\/+/, "/");
    return value;
  }

  function trimLeadingSlash(path) {
    return String(path || "").replace(/^\/+/, "");
  }

  function pathCandidates(path) {
    const normalized = normalizePath(path);
    const decoded = normalizePath(safeDecode(normalized));
    const candidates = new Set([
      normalized,
      decoded,
      trimLeadingSlash(normalized),
      trimLeadingSlash(decoded),
    ]);
    for (const value of Array.from(candidates)) {
      const marker = "/assets/";
      const idx = value.indexOf(marker);
      if (idx >= 0) {
        candidates.add(value.slice(idx + 1));
      }
    }
    return Array.from(candidates).filter(Boolean);
  }

  function assetKeys() {
    return Object.keys(assets).map(function (key) {
      return {
        raw: key,
        normalized: trimLeadingSlash(normalizePath(key)),
      };
    });
  }

  function resolveAsset(path) {
    const candidates = pathCandidates(path);
    for (const candidate of candidates) {
      if (Object.prototype.hasOwnProperty.call(assets, candidate)) {
        const url = assets[candidate];
        debugLog("audio.resolve.exact", { path, candidate, url });
        return url;
      }
    }
    const keys = assetKeys();
    for (const candidate of candidates) {
      const cleanCandidate = trimLeadingSlash(candidate);
      for (const item of keys) {
        const key = item.normalized;
        if (
          cleanCandidate === key ||
          cleanCandidate.endsWith("/" + key) ||
          cleanCandidate.endsWith(key)
        ) {
          const url = assets[item.raw];
          debugLog("audio.resolve.normalized", {
            path,
            candidate: cleanCandidate,
            key,
            rawKey: item.raw,
            url,
          });
          return url;
        }
      }
    }

    const basename = trimLeadingSlash(candidates[0] || "").split("/").pop();
    if (basename) {
      const matches = keys.filter(function (item) {
        return item.normalized.split("/").pop() === basename;
      });
      if (matches.length === 1) {
        const url = assets[matches[0].raw];
        debugLog("audio.resolve.basename", {
          path,
          basename,
          rawKey: matches[0].raw,
          url,
        });
        return url;
      }
    }
    const rawKeys = Object.keys(assets);
    if (rawKeys.length === 1) {
      const url = assets[rawKeys[0]];
      debugLog("audio.resolve.single-fallback", {
        path,
        candidates,
        key: rawKeys[0],
        url,
      });
      return url;
    }
    debugLog("audio.resolve.miss", {
      path,
      candidates,
      keys: rawKeys,
    });
    return candidates[0] || normalizePath(path);
  }

  function absoluteAudioUrl(url) {
    const raw = String(url || "");
    if (
      raw.startsWith("data:") ||
      raw.startsWith("blob:") ||
      raw.startsWith("http://") ||
      raw.startsWith("https://")
    ) {
      return raw;
    }
    try {
      return new URL(raw, window.location.href).href;
    } catch (_err) {
      return raw;
    }
  }

  function safeDecode(value) {
    try {
      return decodeURIComponent(value);
    } catch (_err) {
      return value;
    }
  }

  function clampVolume(volume) {
    const v = Number(volume);
    if (!Number.isFinite(v)) {
      return 0.7;
    }
    return Math.max(0, Math.min(1, v));
  }

  function getAudioContext() {
    if (!AudioContextCtor) {
      return null;
    }
    if (!audioContext) {
      audioContext = new AudioContextCtor();
    }
    return audioContext;
  }

  function emitAudioEvent(name, detail) {
    try {
      window.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    } catch (_err) {
      /* ignore */
    }
  }

  function playSilentBuffer(ctx) {
    try {
      const buffer = ctx.createBuffer(1, 1, 44100);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start(0);
    } catch (_err) {
      /* ignore */
    }
  }

  function markUnlocked(ctx) {
    const wasUnlocked = audioUnlocked;
    audioUnlocked = Boolean(ctx && ctx.state === "running");
    if (audioUnlocked) {
      lastUnlockError = "";
      if (!wasUnlocked) {
        startupMark("audio.unlock.done", {
          backend: backendName,
          contextState: ctx.state,
        });
        emitAudioEvent("pvnmaudiounlock", {
          unlocked: true,
          backend: backendName,
          contextState: ctx.state,
        });
      }
      replayPendingBgm();
    }
  }

  function unlockAudio() {
    unlockGestureCount += 1;
    startupMark("audio.unlock.gesture", { count: unlockGestureCount });
    const ctx = getAudioContext();
    if (!ctx) {
      replayPendingBgm();
      return false;
    }
    if (audioUnlocked && ctx.state === "running") {
      replayPendingBgm();
      return true;
    }

    try {
      const resumed = ctx.state === "suspended" ? ctx.resume() : Promise.resolve();
      Promise.resolve(resumed)
        .then(function () {
          playSilentBuffer(ctx);
          markUnlocked(ctx);
        })
        .catch(function (err) {
          lastUnlockError = String(err && err.message ? err.message : err);
          startupMark("audio.unlock.error", { error: lastUnlockError });
          emitAudioEvent("pvnmaudiounlock", {
            unlocked: false,
            backend: backendName,
            error: lastUnlockError,
          });
        });
      playSilentBuffer(ctx);
      markUnlocked(ctx);
      return audioUnlocked;
    } catch (err) {
      lastUnlockError = String(err && err.message ? err.message : err);
      startupMark("audio.unlock.error", { error: lastUnlockError });
      return false;
    }
  }

  function replayPendingBgm() {
    if (!pendingBgm) {
      return;
    }
    if (!appActive) {
      return;
    }
    const args = pendingBgm;
    pendingBgm = null;
    window.PVNM_AUDIO.playBgm(args.path, args.volume, args.loop, args.start);
  }

  function setLastBgmInfo(update) {
    lastBgmInfo = Object.assign({}, lastBgmInfo, update || {});
    debugLog("audio.bgm." + String(lastBgmInfo.status || "status"), {
      path: lastBgmInfo.path,
      url: lastBgmInfo.url,
      status: lastBgmInfo.status,
      backend: lastBgmInfo.backend,
      error: lastBgmInfo.error,
      webError: lastBgmInfo.webError,
      htmlError: lastBgmInfo.htmlError,
      href: String((window.location && window.location.href) || ""),
      assetCount: Object.keys(assets).length,
    });
  }

  function shortError(err) {
    return String(err && err.message ? err.message : err || "");
  }

  function loadBuffer(url) {
    const cached = decodedBuffers.get(url);
    if (cached) {
      return cached;
    }
    debugLog("audio.fetch", { url });
    const promise = fetch(url)
      .then(function (response) {
        if (!response.ok) {
          throw new Error(
            "HTTP " + response.status + " loading audio: " +
            (response.url || url)
          );
        }
        return response.arrayBuffer();
      })
      .then(function (arrayBuffer) {
        const ctx = getAudioContext();
        if (!ctx) {
          throw new Error("AudioContext unavailable");
        }
        return ctx.decodeAudioData(arrayBuffer.slice(0));
      });
    decodedBuffers.set(url, promise);
    return promise;
  }

  function stopWebBgm() {
    webBgmToken += 1;
    if (!webBgm) {
      return;
    }
    try {
      if (webBgm.source) {
        webBgm.source.onended = null;
        webBgm.source.stop(0);
        webBgm.source.disconnect();
      }
    } catch (_err) {
      /* ignore */
    }
    try {
      if (webBgm.gain) {
        webBgm.gain.disconnect();
      }
    } catch (_err2) {
      /* ignore */
    }
    webBgm = null;
  }

  function setBgmVolume(volume) {
    const vol = clampVolume(volume);
    if (webBgm && webBgm.gain) {
      try {
        webBgm.gain.gain.value = vol;
      } catch (_err) {
        /* ignore */
      }
    }
    if (bgm) {
      try {
        bgm.volume = vol;
      } catch (_err2) {
        /* ignore */
      }
    }
  }

  function playWebBgm(path, volume, loop, start) {
    const ctx = getAudioContext();
    if (!ctx) {
      return false;
    }
    if (ctx.state !== "running") {
      pendingBgm = { path, volume, loop, start };
      unlockAudio();
      return true;
    }

    const url = resolveAsset(path);
    const audioUrl = absoluteAudioUrl(url);
    const vol = clampVolume(volume);
    const startSec = Math.max(0, Number(start) || 0);
    backendName = "webaudio";
    startupMark("audio.bgm.loading", {
      backend: "webaudio",
      path,
      url: audioUrl,
    });
    setLastBgmInfo({
      path,
      url: audioUrl,
      status: "loading",
      backend: "webaudio",
      error: "",
      webError: "",
      htmlError: "",
    });
    if (webBgm && webBgm.url === audioUrl && webBgm.playing && startSec <= 0) {
      webBgm.loop = Boolean(loop);
      if (webBgm.source) {
        webBgm.source.loop = Boolean(loop);
      }
      if (webBgm.gain) {
        webBgm.gain.gain.value = vol;
      }
      return true;
    }

    stopHtmlBgm();
    stopWebBgm();
    const token = webBgmToken;
    webBgm = {
      url: audioUrl,
      path,
      source: null,
      gain: null,
      startContextTime: 0,
      offset: startSec,
      duration: 0,
      loop: Boolean(loop),
      loading: true,
      playing: false,
    };

    loadBuffer(audioUrl)
      .then(function (buffer) {
        if (!webBgm || webBgmToken !== token || webBgm.url !== audioUrl) {
          return;
        }
        const source = ctx.createBufferSource();
        const gain = ctx.createGain();
        const duration = Number(buffer.duration) || 0;
        const offset = duration > 0
          ? (Boolean(loop) ? startSec % duration : Math.min(startSec, duration))
          : 0;

        source.buffer = buffer;
        source.loop = Boolean(loop);
        gain.gain.value = vol;
        source.connect(gain);
        gain.connect(ctx.destination);
        source.onended = function () {
          if (webBgm && webBgm.source === source && !webBgm.loop) {
            webBgm.playing = false;
          }
        };
        webBgm.source = source;
        webBgm.gain = gain;
        webBgm.startContextTime = ctx.currentTime;
        webBgm.offset = offset;
        webBgm.duration = duration;
        webBgm.loop = Boolean(loop);
        webBgm.loading = false;
        webBgm.playing = true;
        setLastBgmInfo({
          path,
          url: audioUrl,
          status: "playing",
          backend: "webaudio",
          error: "",
        });
        startupMark("audio.bgm.playing", {
          backend: "webaudio",
          path,
          url: audioUrl,
        });
        source.start(0, offset);
        emitAudioEvent("pvnmaudioplay", {
          backend: "webaudio",
          path,
          url: audioUrl,
        });
      })
      .catch(function (err) {
        decodedBuffers.delete(audioUrl);
        setLastBgmInfo({
          path,
          url: audioUrl,
          status: "webaudio-error",
          backend: "webaudio",
          error: shortError(err),
          webError: shortError(err),
        });
        startupMark("audio.bgm.error", {
          backend: "webaudio",
          path,
          url: audioUrl,
          error: shortError(err),
        });
        console.warn("[PVNM_AUDIO] WebAudio BGM failed; falling back", err);
        if (!webBgm || webBgmToken !== token || webBgm.url !== audioUrl) {
          return;
        }
        webBgm = null;
        playHtmlBgm(path, volume, loop, start);
      });
    return true;
  }

  function stopHtmlBgm() {
    if (!bgm) {
      return;
    }
    try {
      bgm.pause();
      bgm.currentTime = 0;
    } catch (_err) {
      /* ignore */
    }
    bgm = null;
    bgmUrl = "";
  }

  function setStartTime(audio, start) {
    const t = Math.max(0, Number(start) || 0);
    if (t <= 0) {
      return;
    }
    try {
      audio.currentTime = t;
    } catch (_err) {
      audio.addEventListener("loadedmetadata", function onLoaded() {
        audio.removeEventListener("loadedmetadata", onLoaded);
        try {
          audio.currentTime = t;
        } catch (_err2) {
          /* ignore */
        }
      });
    }
  }

  function safePlayHtml(audio, retryArgs) {
    const result = audio.play();
    if (result && typeof result.catch === "function") {
      result.catch(function () {
        pendingBgm = retryArgs || null;
      });
    }
  }

  function playHtmlBgm(path, volume, loop, start) {
    backendName = preferHtmlBgm ? "html" : (audioContext ? "webaudio+html" : "html");
    const url = resolveAsset(path);
    const audioUrl = absoluteAudioUrl(url);
    const vol = clampVolume(volume);
    const startSec = Math.max(0, Number(start) || 0);
    startupMark("audio.bgm.loading", {
      backend: backendName,
      path,
      url: audioUrl,
    });
    setLastBgmInfo({
      path,
      url: audioUrl,
      status: "html-loading",
      backend: backendName,
      error: "",
      htmlError: "",
    });

    if (bgm && bgmUrl === audioUrl && !bgm.ended && startSec <= 0) {
      bgm.volume = vol;
      bgm.loop = Boolean(loop);
      safePlayHtml(bgm, { path, volume, loop, start });
      return;
    }

    stopWebBgm();
    stopHtmlBgm();
    bgm = new Audio(audioUrl);
    bgmUrl = audioUrl;
    bgm.preload = "auto";
    bgm.loop = Boolean(loop);
    bgm.volume = vol;
    bgm.addEventListener("playing", function () {
      setLastBgmInfo({
        path,
        url: audioUrl,
        status: "playing",
        backend: backendName,
        error: "",
      });
      startupMark("audio.bgm.playing", {
        backend: backendName,
        path,
        url: audioUrl,
      });
    });
    bgm.addEventListener("error", function () {
      const code = bgm && bgm.error ? bgm.error.code : "";
      startupMark("audio.bgm.error", {
        backend: backendName,
        path,
        url: audioUrl,
        error: code ? "HTMLAudio error " + code : "HTMLAudio error",
      });
      setLastBgmInfo({
        path,
        url: audioUrl,
        status: "html-error",
        backend: backendName,
        error: code ? "HTMLAudio error " + code : "HTMLAudio error",
        htmlError: code ? "HTMLAudio error " + code : "HTMLAudio error",
      });
    });
    setStartTime(bgm, startSec);
    safePlayHtml(bgm, { path, volume, loop, start });
  }

  function cleanupSePlayers() {
    for (const player of Array.from(sePlayers)) {
      if (player.ended || player.paused) {
        sePlayers.delete(player);
      }
    }
  }

  function cleanupSeNodes() {
    for (const node of Array.from(seNodes)) {
      if (node._pvnmEnded) {
        seNodes.delete(node);
      }
    }
  }

  function stopAllSeInternal() {
    for (const source of Array.from(seNodes)) {
      try {
        source.onended = null;
        source.stop(0);
        source.disconnect();
      } catch (_err) {
        /* ignore */
      }
    }
    seNodes.clear();
    for (const player of Array.from(sePlayers)) {
      try {
        player.pause();
        player.currentTime = 0;
      } catch (_err2) {
        /* ignore */
      }
    }
    sePlayers.clear();
  }

  function playWebSe(path, volume, repeat) {
    if (!appActive) {
      return true;
    }
    const ctx = getAudioContext();
    if (!ctx || ctx.state !== "running") {
      return false;
    }
    const url = absoluteAudioUrl(resolveAsset(path));
    loadBuffer(url)
      .then(function (buffer) {
        cleanupSeNodes();
        const source = ctx.createBufferSource();
        const gain = ctx.createGain();
        source.buffer = buffer;
        source.loop = Number(repeat) > 0;
        gain.gain.value = clampVolume(volume);
        source.connect(gain);
        gain.connect(ctx.destination);
        source.onended = function () {
          source._pvnmEnded = true;
          try {
            source.disconnect();
            gain.disconnect();
          } catch (_err) {
            /* ignore */
          }
          seNodes.delete(source);
        };
        seNodes.add(source);
        source.start(0);
      })
      .catch(function () {
        playHtmlSe(path, volume, repeat);
      });
    return true;
  }

  function playHtmlSe(path, volume, repeat) {
    if (!appActive) {
      return;
    }
    cleanupSePlayers();
    const player = new Audio(absoluteAudioUrl(resolveAsset(path)));
    player.preload = "auto";
    player.loop = Number(repeat) > 0;
    player.volume = clampVolume(volume);
    player.addEventListener("ended", function () {
      sePlayers.delete(player);
    });
    sePlayers.add(player);
    const result = player.play();
    if (result && typeof result.catch === "function") {
      result.catch(function () {
      sePlayers.delete(player);
      });
    }
  }

  function pauseForLifecycle(reason) {
    appActive = false;
    if (lifecyclePaused) {
      return;
    }
    lifecyclePaused = true;
    lifecycleHtmlBgmPaused = Boolean(bgm && !bgm.paused && !bgm.ended);
    lifecycleWebBgmPaused = Boolean(webBgm && webBgm.playing);
    stopAllSeInternal();
    if (lifecycleHtmlBgmPaused && bgm) {
      try {
        bgm.pause();
      } catch (_err) {
        /* ignore */
      }
    }
    if (lifecycleWebBgmPaused && audioContext
        && audioContext.state === "running") {
      try {
        const result = audioContext.suspend();
        if (result && typeof result.catch === "function") {
          result.catch(function () {});
        }
      } catch (_err2) {
        /* ignore */
      }
    }
    debugLog("audio.lifecycle.pause", {
      reason: reason || "",
      htmlBgm: lifecycleHtmlBgmPaused,
      webBgm: lifecycleWebBgmPaused,
      pendingBgm: Boolean(pendingBgm),
    });
  }

  function resumeForLifecycle(reason) {
    appActive = true;
    const hadLifecyclePause = lifecyclePaused;
    lifecyclePaused = false;
    debugLog("audio.lifecycle.resume", {
      reason: reason || "",
      htmlBgm: lifecycleHtmlBgmPaused,
      webBgm: lifecycleWebBgmPaused,
      pendingBgm: Boolean(pendingBgm),
    });

    if (pendingBgm) {
      lifecycleHtmlBgmPaused = false;
      lifecycleWebBgmPaused = false;
      replayPendingBgm();
      return;
    }

    if (hadLifecyclePause && lifecycleHtmlBgmPaused && bgm) {
      safePlayHtml(bgm, null);
    }
    if (hadLifecyclePause && lifecycleWebBgmPaused
        && audioContext && audioContext.state === "suspended") {
      try {
        const result = audioContext.resume();
        Promise.resolve(result)
          .then(function () {
            markUnlocked(audioContext);
          })
          .catch(function () {});
      } catch (_err) {
        /* ignore */
      }
    }
    lifecycleHtmlBgmPaused = false;
    lifecycleWebBgmPaused = false;
  }

  function capacitorAppPlugin() {
    try {
      const cap = window.Capacitor;
      const plugins = cap && cap.Plugins;
      return plugins && plugins.App ? plugins.App : null;
    } catch (_err) {
      return null;
    }
  }

  function registerLifecycleHandlers() {
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        pauseForLifecycle("visibility:hidden");
      } else if (document.visibilityState === "visible") {
        resumeForLifecycle("visibility:visible");
      }
    });
    window.addEventListener("pagehide", function () {
      pauseForLifecycle("pagehide");
    });
    window.addEventListener("pageshow", function () {
      if (document.visibilityState !== "hidden") {
        resumeForLifecycle("pageshow");
      }
    });
    try {
      const app = capacitorAppPlugin();
      if (app && typeof app.addListener === "function") {
        app.addListener("appStateChange", function (state) {
          if (state && state.isActive === false) {
            pauseForLifecycle("capacitor:inactive");
          } else if (state && state.isActive === true) {
            resumeForLifecycle("capacitor:active");
          }
        });
        app.addListener("pause", function () {
          pauseForLifecycle("capacitor:pause");
        });
        app.addListener("resume", function () {
          resumeForLifecycle("capacitor:resume");
        });
      }
    } catch (err) {
      debugLog("audio.lifecycle.register_error", { error: shortError(err) });
    }
  }

  window.addEventListener("pointerdown", unlockAudio, {
    passive: true,
    capture: true,
  });
  window.addEventListener("touchstart", unlockAudio, {
    passive: true,
    capture: true,
  });
  window.addEventListener("keydown", unlockAudio, { capture: true });

  window.PVNM_DEBUG_LOG = {
    add(type, detail) {
      let value = detail;
      if (typeof detail === "string") {
        try {
          value = JSON.parse(detail);
        } catch (_err) {
          value = { text: detail };
        }
      }
      debugLog(type, value || {});
    },

    getText() {
      return debugLogText();
    },

    getJson() {
      return JSON.stringify(readDebugLogEntries(), null, 2);
    },

    clear() {
      memoryDebugLog = [];
      try {
        window.localStorage.removeItem(debugLogKey());
      } catch (_err) {
        /* ignore */
      }
    },

    key() {
      return debugLogKey();
    },

    download(filename) {
      const text = debugLogText();
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "pvnm_debug_log.txt";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  };

  window.PVNM_AUDIO = {
    playBgm(path, volume, loop, start) {
      if (!appActive) {
        pendingBgm = { path, volume, loop, start };
        setLastBgmInfo({
          path,
          url: "",
          status: "lifecycle-pending",
          backend: backendName,
          error: "",
        });
        return;
      }
      if (preferHtmlBgm) {
        playHtmlBgm(path, volume, loop, start);
        return;
      }
      if (AudioContextCtor && playWebBgm(path, volume, loop, start)) {
        return;
      }
      playHtmlBgm(path, volume, loop, start);
    },

    stopBgm() {
      pendingBgm = null;
      stopWebBgm();
      stopHtmlBgm();
      setLastBgmInfo({ status: "stopped", error: "" });
    },

    setBgmVolume(volume) {
      setBgmVolume(volume);
    },

    getBgmCurrentTime() {
      if (webBgm) {
        if (!webBgm.playing || !audioContext) {
          return Number(webBgm.offset) || 0;
        }
        const duration = Number(webBgm.duration) || 0;
        const elapsed = Math.max(
          0,
          audioContext.currentTime - webBgm.startContextTime
        );
        const time = (Number(webBgm.offset) || 0) + elapsed;
        if (webBgm.loop && duration > 0) {
          return time % duration;
        }
        return duration > 0 ? Math.min(time, duration) : time;
      }
      if (!bgm) {
        return 0;
      }
      return Number(bgm.currentTime) || 0;
    },

    isBgmPlaying() {
      if (webBgm) {
        return Boolean(webBgm.playing);
      }
      return Boolean(bgm && !bgm.paused && !bgm.ended);
    },

    playSe(path, volume, repeat) {
      if (AudioContextCtor && playWebSe(path, volume, repeat)) {
        return;
      }
      playHtmlSe(path, volume, repeat);
    },

    stopAllSe() {
      stopAllSeInternal();
    },

    unlock() {
      return unlockAudio();
    },

    isUnlocked() {
      return audioUnlocked;
    },

    getBackendName() {
      return backendName;
    },

    getAudioContextState() {
      return audioContext ? audioContext.state : "none";
    },

    getUnlockGestureCount() {
      return unlockGestureCount;
    },

    getLastUnlockError() {
      return lastUnlockError;
    },

    getLastBgmInfo() {
      return JSON.stringify(lastBgmInfo);
    },

    getAssetCount() {
      return Object.keys(assets).length;
    },

    resolveAudioPath(path) {
      return resolveAsset(path);
    },

    hasPendingBgm() {
      return Boolean(pendingBgm);
    },

    isAppActive() {
      return appActive;
    },

    isLifecyclePaused() {
      return lifecyclePaused;
    },
  };

  registerLifecycleHandlers();
  window.PVNM_AUDIO_READY = true;
})();

(function () {
  "use strict";

  if (window.PVNM_INPUT_READY) {
    return;
  }

  let pendingBack = 0;
  let totalBack = 0;
  let lastBackEvent = null;
  let lastPointerEvent = null;
  let pointerEventCount = 0;
  let touchEventCount = 0;
  let clickEventCount = 0;
  let capacitorBackRegistered = false;
  let registerAttempts = 0;
  let exitRestartArmed = false;
  let exitHiddenAt = 0;

  function eventPoint(event) {
    const touch = event && event.touches && event.touches.length
      ? event.touches[0]
      : null;
    const source = touch || event || {};
    return {
      x: Math.round(Number(source.clientX) || 0),
      y: Math.round(Number(source.clientY) || 0),
      pointerType: String(event && event.pointerType ? event.pointerType : ""),
      button: Number(event && Number.isFinite(event.button) ? event.button : -1),
    };
  }

  function recordPointer(kind, event) {
    if (kind === "touchstart") {
      touchEventCount += 1;
    } else if (kind === "click") {
      clickEventCount += 1;
    } else {
      pointerEventCount += 1;
    }
    const point = eventPoint(event);
    lastPointerEvent = {
      kind,
      x: point.x,
      y: point.y,
      pointerType: point.pointerType,
      button: point.button,
      at: Date.now(),
      pointerCount: pointerEventCount,
      touchCount: touchEventCount,
      clickCount: clickEventCount,
    };
  }

  function emitBack(source, detail) {
    pendingBack += 1;
    totalBack += 1;
    lastBackEvent = {
      source: source || "unknown",
      detail: detail || null,
      at: Date.now(),
      pending: pendingBack,
      total: totalBack,
    };

    try {
      window.dispatchEvent(
        new CustomEvent("pvnmbackbutton", { detail: lastBackEvent })
      );
    } catch (_err) {
      /* ignore */
    }
  }

  function registerCapacitorBackButton() {
    if (capacitorBackRegistered) {
      return true;
    }
    registerAttempts += 1;
    try {
      const cap = window.Capacitor;
      const plugins = cap && cap.Plugins;
      const app = plugins && plugins.App;
      if (!app || typeof app.addListener !== "function") {
        return false;
      }
      app.addListener("backButton", function (event) {
        emitBack("capacitor", event || null);
      });
      capacitorBackRegistered = true;
      return true;
    } catch (err) {
      console.warn("[PVNM_INPUT] Capacitor backButton registration failed", err);
      return false;
    }
  }

  function scheduleRegistrationRetry() {
    if (registerCapacitorBackButton() || registerAttempts >= 20) {
      return;
    }
    window.setTimeout(scheduleRegistrationRetry, 250);
  }

  function capacitorAppPlugin() {
    const cap = window.Capacitor;
    const plugins = cap && cap.Plugins;
    return plugins && plugins.App ? plugins.App : null;
  }

  function restartLocation() {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("pvnm_restart", String(Date.now()));
      window.location.replace(url.href);
    } catch (_err) {
      try {
        window.location.reload();
      } catch (_err2) {
        /* ignore */
      }
    }
  }

  function scheduleRestart(delayMs) {
    window.setTimeout(function () {
      if (exitRestartArmed) {
        restartLocation();
      }
    }, delayMs || 50);
  }

  function showExitCover() {
    try {
      if (document.getElementById("pvnm-exit-cover")) {
        return;
      }
      const cover = document.createElement("div");
      cover.id = "pvnm-exit-cover";
      Object.assign(cover.style, {
        position: "fixed",
        inset: "0",
        zIndex: "2147483647",
        background: "#000",
      });
      document.documentElement.appendChild(cover);
    } catch (_err) {
      /* ignore */
    }
  }

  function armRestartOnResume(app) {
    if (exitRestartArmed) {
      return;
    }
    exitRestartArmed = true;

    const markHidden = function () {
      exitHiddenAt = Date.now();
    };
    const restartIfReturning = function () {
      if (!exitRestartArmed || exitHiddenAt <= 0) {
        return;
      }
      scheduleRestart(50);
    };

    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") {
        markHidden();
      } else if (document.visibilityState === "visible") {
        restartIfReturning();
      }
    });
    window.addEventListener("pagehide", markHidden);
    window.addEventListener("focus", restartIfReturning);

    try {
      if (app && typeof app.addListener === "function") {
        app.addListener("appStateChange", function (state) {
          if (state && state.isActive === false) {
            markHidden();
          } else if (state && state.isActive === true) {
            restartIfReturning();
          }
        });
      }
    } catch (_err) {
      /* browser fallback listeners above are enough */
    }
  }

  function fallbackExitApp(app) {
    if (!app || typeof app.exitApp !== "function") {
      return false;
    }
    window.setTimeout(function () {
      try {
        app.exitApp();
      } catch (_err) {
        /* ignore */
      }
    }, 250);
    return true;
  }

  window.PVNM_INPUT = {
    triggerBack(source) {
      emitBack(source || "manual", null);
      return true;
    },

    consumeBackPressed() {
      if (pendingBack <= 0) {
        return false;
      }
      pendingBack -= 1;
      return true;
    },

    getPendingBackCount() {
      return pendingBack;
    },

    getTotalBackCount() {
      return totalBack;
    },

    getLastBackEvent() {
      return lastBackEvent ? JSON.stringify(lastBackEvent) : "";
    },

    isCapacitorAvailable() {
      return Boolean(window.Capacitor);
    },

    isCapacitorBackRegistered() {
      return capacitorBackRegistered;
    },

    requestExitApp() {
      try {
        const app = capacitorAppPlugin();
        if (!app) {
          return false;
        }
        showExitCover();
        armRestartOnResume(app);
        if (typeof app.minimizeApp === "function") {
          window.setTimeout(function () {
            try {
              const result = app.minimizeApp();
              if (result && typeof result.catch === "function") {
                result.catch(function () {
                  fallbackExitApp(app);
                });
              }
            } catch (_err) {
                fallbackExitApp(app);
            }
          }, 250);
          return true;
        }
        if (fallbackExitApp(app)) {
          return true;
        }
      } catch (err) {
        console.warn("[PVNM_INPUT] App.exitApp failed", err);
      }
      return false;
    },

    getLastPointerEvent() {
      return lastPointerEvent ? JSON.stringify(lastPointerEvent) : "";
    },

    getPointerEventCount() {
      return pointerEventCount;
    },

    getTouchEventCount() {
      return touchEventCount;
    },

    getClickEventCount() {
      return clickEventCount;
    },
  };

  window.addEventListener("pointerdown", function (event) {
    recordPointer("pointerdown", event);
  }, { passive: true, capture: true });
  window.addEventListener("touchstart", function (event) {
    recordPointer("touchstart", event);
  }, { passive: true, capture: true });
  window.addEventListener("click", function (event) {
    recordPointer("click", event);
  }, { passive: true, capture: true });

  window.PVNM_INPUT_READY = true;
  scheduleRegistrationRetry();
})();

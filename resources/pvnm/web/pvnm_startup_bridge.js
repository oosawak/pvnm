(function () {
  "use strict";

  if (window.PVNM_STARTUP_READY) {
    return;
  }

  const maxMarks = 240;
  const marks = [];

  function nowMs() {
    try {
      return Number(performance.now()) || 0;
    } catch (_err) {
      return 0;
    }
  }

  function roundMs(value) {
    return Math.round((Number(value) || 0) * 10) / 10;
  }

  function normalizeDetail(detail) {
    if (detail == null) {
      return {};
    }
    if (typeof detail === "string") {
      try {
        return JSON.parse(detail);
      } catch (_err) {
        return { text: detail };
      }
    }
    return detail;
  }

  function logEntry(entry) {
    try {
      console.info(
        "[PVNM_STARTUP] " +
          entry.ms +
          "ms +" +
          entry.deltaMs +
          "ms " +
          entry.label
      );
    } catch (_err) {
      /* ignore */
    }
    try {
      const api = window.PVNM_DEBUG_LOG;
      const add = api && api.add;
      if (typeof add === "function") {
        add("startup", entry);
      }
    } catch (_err) {
      /* keep startup timing best-effort */
    }
  }

  function lastMark() {
    return marks.length ? marks[marks.length - 1] : null;
  }

  function mark(label, detail) {
    const previous = lastMark();
    const ms = roundMs(nowMs());
    const entry = {
      label: String(label || "event"),
      ms,
      deltaMs: previous ? roundMs(ms - previous.ms) : ms,
      detail: normalizeDetail(detail),
    };
    marks.push(entry);
    while (marks.length > maxMarks) {
      marks.shift();
    }
    logEntry(entry);
    try {
      window.dispatchEvent(
        new CustomEvent("pvnm-startup-mark", { detail: entry })
      );
    } catch (_err) {
      /* event dispatch is best-effort */
    }
    try {
      if (
        entry.label === "python.first_draw.done" &&
        window.PVNM_LOADING &&
        typeof window.PVNM_LOADING.hide === "function"
      ) {
        window.PVNM_LOADING.hide();
      }
    } catch (_err) {
      /* loading overlay is optional */
    }
    return ms;
  }

  function summary() {
    const last = lastMark();
    return {
      elapsedMs: roundMs(nowMs()),
      count: marks.length,
      lastLabel: last ? last.label : "-",
      lastMs: last ? last.ms : 0,
      lastDeltaMs: last ? last.deltaMs : 0,
    };
  }

  window.PVNM_STARTUP = {
    mark,

    getSummary() {
      return JSON.stringify(summary());
    },

    getMarksJson() {
      return JSON.stringify(marks, null, 2);
    },

    getText() {
      return marks
        .map(function (entry) {
          return (
            String(entry.ms).padStart(8, " ") +
            "ms +" +
            String(entry.deltaMs).padStart(6, " ") +
            "ms " +
            entry.label +
            " " +
            JSON.stringify(entry.detail || {})
          );
        })
        .join("\n");
    },

    clear() {
      marks.length = 0;
      mark("startup.clear");
    },

    elapsedMs() {
      return roundMs(nowMs());
    },

    lastLabel() {
      const last = lastMark();
      return last ? last.label : "";
    },
  };

  window.PVNM_STARTUP_READY = true;
  mark("web.bridge_ready", {
    readyState: String(document.readyState || ""),
    href: String((window.location && window.location.href) || ""),
  });

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      function () {
        mark("web.dom_content_loaded");
      },
      { once: true }
    );
  } else {
    mark("web.dom_already_ready", {
      readyState: String(document.readyState || ""),
    });
  }

  window.addEventListener(
    "load",
    function () {
      mark("web.window_load");
    },
    { once: true }
  );
})();

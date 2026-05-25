(function () {
  "use strict";

  function getChromeVersion(userAgent) {
    var match = String(userAgent || "").match(/(?:Chrome|Chromium|CriOS)\/([0-9.]+)/);
    return match ? match[1] : "";
  }

  function hasModernSyntax() {
    try {
      // Pyxel Web 2.9.5 uses optional chaining/nullish coalescing in pyxel.js.
      // Older Android System WebView versions fail while parsing the file,
      // before PVNM or Pyodide can show a useful error.
      new Function("var a={b:1}; return a?.b ?? 0;");
      return true;
    } catch (_err) {
      return false;
    }
  }

  function check() {
    var missing = [];
    if (!window.Promise) {
      missing.push("Promise");
    }
    if (!window.fetch) {
      missing.push("fetch");
    }
    if (!window.WebAssembly) {
      missing.push("WebAssembly");
    }
    if (!window.TextDecoder) {
      missing.push("TextDecoder");
    }
    if (!hasModernSyntax()) {
      missing.push("modern JavaScript syntax");
    }
    return {
      ok: missing.length === 0,
      missing: missing,
      userAgent: String(navigator.userAgent || ""),
      chromeVersion: getChromeVersion(navigator.userAgent)
    };
  }

  function htmlEscape(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showUnsupported(result) {
    var detected = result.chromeVersion
      ? "Chrome/WebView " + result.chromeVersion
      : "unknown WebView";
    var missing = result.missing.length ? result.missing.join(", ") : "unknown";
    var markup =
      '<style id="pvnm-webview-unsupported-style">' +
      'html,body{margin:0;width:100%;min-height:100%;background:#111;color:#f2f2f2;' +
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}' +
      'body{box-sizing:border-box;padding:22px;overflow:auto;}' +
      '.pvnm-unsupported{box-sizing:border-box;max-width:860px;margin:0 auto;' +
      'border:2px solid #747a86;background:#202226;padding:24px;line-height:1.5;}' +
      '.pvnm-unsupported h1{font-size:28px;margin:0 0 16px;}' +
      '.pvnm-unsupported p{font-size:19px;margin:10px 0;}' +
      '.pvnm-unsupported code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;' +
      'font-size:16px;color:#b8d6ff;overflow-wrap:anywhere;word-break:break-word;}' +
      '.pvnm-unsupported .muted{color:#aeb3bd;}' +
      '</style>' +
      '<main class="pvnm-unsupported" role="main">' +
      '<h1>PVNM cannot start on this device</h1>' +
      '<p>この端末の Android System WebView が古いため、PVNM Android/Web版を起動できません。</p>' +
      '<p>Android System WebView または Chrome を更新してから、アプリを再起動してください。</p>' +
      '<p class="muted">Detected: <code>' + htmlEscape(detected) + '</code></p>' +
      '<p class="muted">Missing support: <code>' + htmlEscape(missing) + '</code></p>' +
      '<p class="muted">User agent: <code>' + htmlEscape(result.userAgent) + '</code></p>' +
      '</main>';

    try {
      document.write(markup);
    } catch (_err) {
      window.addEventListener("DOMContentLoaded", function () {
        document.body.innerHTML = markup;
      });
    }
  }

  function escapeScriptSrc(src) {
    return String(src || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "%3C");
  }

  function loadPyxelScript(src) {
    var result = check();
    window.PVNM_WEBVIEW_COMPAT_RESULT = result;
    if (!result.ok) {
      showUnsupported(result);
      window.launchPyxel = function () {
        if (window.console && console.warn) {
          console.warn("PVNM launch skipped: unsupported WebView", result);
        }
      };
      return false;
    }
    document.write(
      '<scr' + 'ipt src="' + escapeScriptSrc(src) + '"></scr' + 'ipt>'
    );
    return true;
  }

  window.PVNM_WEBVIEW_COMPAT = {
    check: check,
    loadPyxelScript: loadPyxelScript
  };
  window.PVNM_WEBVIEW_COMPAT_READY = true;
}());

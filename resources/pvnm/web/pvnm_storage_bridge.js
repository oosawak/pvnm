(function () {
  if (window.PVNM_STORAGE_READY) {
    return;
  }

  const pathBase = (() => {
    try {
      return window.location.pathname.replace(/\/[^/]*$/, "/");
    } catch (_e) {
      return "/";
    }
  })();
  const namespace = String(
    window.PVNM_STORAGE_NAMESPACE || `pvnm:${pathBase}:`
  );

  const scopedKey = (key) => {
    const value = String(key || "pvnm_data.json")
      .replace(/\\/g, "/")
      .replace(/^\/+/, "");
    return `${namespace}${value || "pvnm_data.json"}`;
  };

  const storageAvailable = () => {
    try {
      const testKey = `${namespace}__test__`;
      window.localStorage.setItem(testKey, "1");
      window.localStorage.removeItem(testKey);
      return true;
    } catch (err) {
      console.warn("[PVNM_STORAGE] localStorage unavailable", err);
      return false;
    }
  };

  const available = storageAvailable();

  window.PVNM_STORAGE = {
    isAvailable() {
      return available;
    },

    getNamespace() {
      return namespace;
    },

    getScopedKey(key) {
      return scopedKey(key);
    },

    getItem(key) {
      if (!available) {
        return null;
      }
      try {
        return window.localStorage.getItem(scopedKey(key));
      } catch (err) {
        console.warn("[PVNM_STORAGE] getItem failed", err);
        return null;
      }
    },

    setItem(key, value) {
      if (!available) {
        return false;
      }
      try {
        window.localStorage.setItem(scopedKey(key), String(value));
        return true;
      } catch (err) {
        console.warn("[PVNM_STORAGE] setItem failed", err);
        return false;
      }
    },

    removeItem(key) {
      if (!available) {
        return false;
      }
      try {
        window.localStorage.removeItem(scopedKey(key));
        return true;
      } catch (err) {
        console.warn("[PVNM_STORAGE] removeItem failed", err);
        return false;
      }
    },

    clearNamespace() {
      if (!available) {
        return false;
      }
      try {
        const keys = [];
        for (let i = 0; i < window.localStorage.length; i += 1) {
          const key = window.localStorage.key(i);
          if (key && key.startsWith(namespace)) {
            keys.push(key);
          }
        }
        keys.forEach((key) => window.localStorage.removeItem(key));
        return true;
      } catch (err) {
        console.warn("[PVNM_STORAGE] clearNamespace failed", err);
        return false;
      }
    },
  };

  window.PVNM_STORAGE_READY = true;
})();

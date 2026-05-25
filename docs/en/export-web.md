# Web HTML Export

Web HTML export creates a browser-playable build.

Japanese version: [Web HTMLエクスポート](../ja/export-web.md)

## Output

Running `[WEB HTML]` creates files like these:

| Output | Purpose |
| --- | --- |
| `.html` | Startup HTML |
| `<name>_assets/` | Assets required by the Web build |
| `pyxel/` | Localized Pyxel Web runtime |

The HTML file alone cannot load the assets or runtime. Keep `.html`, `<name>_assets/`, and `pyxel/` in the same relative layout when distributing.

If the project contains `assets/images/ui/loading.png`, it is used as the Web startup loading image. See [Assets and Audio](assets-and-audio.md).

## Uses

| Use | Description |
| --- | --- |
| GitHub Pages | Let players run the game from a web page |
| itch.io and similar sites | Distribute as a browser game |
| Local testing | Check browser behavior locally |

## Local Testing

Because of browser restrictions, testing through a local server is more stable than opening the HTML file directly.

```bash
python3 -m http.server 8133
```

Then open `http://127.0.0.1:8133/<exported-html-name>` in a browser.

## Distribution

For GitHub Pages, keep `.html`, `<name>_assets/`, and `pyxel/` together. For GitHub Releases, zip those files while preserving the same folder layout.

## Before Publishing

Web builds can behave differently from desktop builds for audio, storage, and EXTRAS unlock state. Test the deployed page from start to ending before publishing.

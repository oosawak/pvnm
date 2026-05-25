# Third-Party Notices

PVNM itself is released under the MIT License. Third-party fonts, runtimes, and libraries are provided under their own licenses.

This file summarizes the main third-party components that may be included in the PVNM source distribution, generated exports, or packaged builds. The exact files included depend on the export format.

## Bundled in this repository

| Component | Location | License | Notes |
| --- | --- | --- | --- |
| efont-unicode-bdf | `assets/fonts/efont-unicode-bdf/` | BSD-style 3-clause font license plus upstream notices | Main notice: `assets/fonts/efont-unicode-bdf/COPYRIGHT`. Keep the upstream README files in the directory when redistributing the fonts. |
| Pyxel web runtime | `resources/pvnm/web/pyxel_runtime/pyxel/` | MIT | License text: `resources/pvnm/web/pyxel_runtime/pyxel/LICENSE`. |
| Pyodide runtime | `resources/pvnm/web/pyxel_runtime/pyodide/` | MPL-2.0 | Used for Web/Pyxel runtime support. See the upstream Pyodide project for complete license information. |

## Runtime and build dependencies

These packages are installed from Python package indexes or bundled into generated applications by build tools, depending on the target format.

| Component | Used for | License information |
| --- | --- | --- |
| Pyxel | PVNM runtime and Pyxel app/web runtime | MIT |
| pygame | Audio/input/runtime support used by Pyxel on desktop | LGPL |
| NumPy | Image cache and palette data processing | BSD-3-Clause and additional permissive notices in package metadata |
| Pillow | Image loading and conversion | MIT-CMU |
| PyInstaller | Windows executable packaging | GPLv2-or-later with PyInstaller bootloader exception |

When shipping a binary distribution, include this notice file and preserve license files that are already included in vendored directories. For dependencies bundled by PyInstaller or other packaging tools, keep generated license metadata when available.

## efont-unicode-bdf

The main efont notice in `assets/fonts/efont-unicode-bdf/COPYRIGHT` permits redistribution and use in source and binary forms, with or without modification, as long as its conditions are preserved.

The font directory also contains upstream README files for included font sources, including:

- `README.baekmuk`
- `README.contrib`
- `README.etl-unicode`
- `README.naga10`
- `README.shinonome`
- `README.ucs-fonts`

Keep these files with the font directory. They document origin and license notes for parts of the font set.

## Pyxel and Pyodide

PVNM includes Pyxel web runtime files and Pyodide runtime files under `resources/pvnm/web/pyxel_runtime/` so exported Web and Android projects can run without depending on a remote CDN.

Pyxel's bundled license file is kept at:

```text
resources/pvnm/web/pyxel_runtime/pyxel/LICENSE
```

Pyodide is licensed under the Mozilla Public License 2.0. If you redistribute PVNM with the vendored Pyodide runtime, include this notice and keep the runtime files together.

## Exported PVNM works

Games made with PVNM are your own works. PVNM's MIT License does not automatically apply to your game text, images, music, characters, or other original content.

However, exported works may include runtime files from PVNM, Pyxel, Pyodide, fonts, and Python packages depending on the export format. Keep the relevant notices with the distribution when those files are included.

PVNM exports may include files such as:

- `PVNM_LICENSE.txt`
- `PVNM_THIRD_PARTY_NOTICES.md`
- `PVNM_EXPORT_LICENSE_README.txt`

These files describe PVNM and bundled third-party components. They are not a substitute for your game's own license, copyright notice, terms of use, or asset credits.

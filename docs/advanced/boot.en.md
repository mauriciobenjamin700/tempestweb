# Mode A boot & caching

!!! abstract "What you will learn"
    What happens between the user opening the URL and your `view()` showing up in
    Mode A (WASM/Pyodide), how to make that time **visible** with the loading
    screen, and how a server uses `immutable.json` to stop re-downloading what did
    not change.

In Mode A, Python runs **inside the browser**. Before the first screen, the page
needs: the Pyodide runtime (~6 MB), the `pydantic` wheels, the tempestweb Python
package + your `app.py`, and the JS client that draws the DOM. On a phone over
4G that takes seconds — and, up to 0.140, the page stayed **blank** the whole
time. 😬

## What the build emits

```bash
tempestweb build --mode wasm
```

```text
dist/wasm/
├── index.html                          ← revalidated (no-cache)
├── bootstrap.js                        ← revalidated
├── app.py                              ← revalidated
├── immutable.json                      ← the cache contract (below)
├── client-3f9c0a1b2c4d5e6f/
│   └── tempestweb-wasm.js              ← the whole client, one file, immutable
├── tempestweb-pkg.8c1d0e2f3a4b5c6d.zip ← the Python payload, immutable
├── manifest.webmanifest, sw.js, icons/ ← PWA layer
└── client/offline/{store,sync}.js      ← only with the service worker on
```

Three things changed from the old layout, each going after one slice of boot
time.

### 1. The client is **one** file

The `bootstrap.js` used to statically import a tree of **81 modules** (~600 KB),
and the browser had to resolve the whole tree before running a single line —
only then did Pyodide start downloading. Now the build copies a single bundle,
`tempestweb-wasm.js` (~190 KB, ~60 KB gzipped), generated at release time.

!!! info "Technical details — where the bundle comes from"
    The bundle is produced by `scripts/bundle-client.mjs` (esbuild, a **pinned**
    npm devDependency) and committed under `client/bundle/`. `tempestweb build`
    only copies the file: esbuild never becomes a dependency of the Python
    package. The modules in `client/` are still plain, build-free JavaScript —
    Mode B, Mode C and the tests read the sources directly.

    `tempestweb dev` uses the sources (`client/wasm-entry.js`), not the bundle:
    editing a client module shows up on the next reload without re-bundling.

### 2. Everything downloads at once

`bootstrap.js` no longer has a static `import`. Before its first `await` it
starts, in parallel:

- Pyodide (`pyodide.mjs` → `.wasm` + stdlib);
- the wheels `loadPackage` is going to ask for (read from the same
  `pyodide-lock.json`, by the same URL, so `loadPackage` finds them in the HTTP
  cache);
- the Python payload and `app.py`;
- the client bundle.

And `index.html` already names all of them in `<link rel="preload">` /
`<link rel="modulepreload">`, so the downloads start while the HTML is still
being parsed. The boot then consumes each promise in the same order as always —
the Python side did not change.

### 3. Content-hashed names

The bundle lives under `client-<hash>/` and the payload is called
`tempestweb-pkg.<hash>.zip`, where `<hash>` is the first 16 hex digits of the
SHA-256 **of the file itself**. The name changes exactly when the content does —
so the server can tell the browser to keep them for a year and never ask again.

!!! note "Why a content hash, and not the tempestweb version?"
    The bundle only changes with the version, but the payload does not: it
    carries your app's `[wasm] modules` and whatever the packaging step decides
    to include. A content hash works for both and never lies.

## The `immutable.json` contract

The build writes at the artifact root:

```json
{
  "immutable": [
    "client-3f9c0a1b2c4d5e6f/**",
    "tempestweb-pkg.8c1d0e2f3a4b5c6d.zip"
  ],
  "generator": "tempestweb 0.141.0"
}
```

It is the format the
[tempest-fastapi-sdk](https://pypi.org/project/tempest-fastapi-sdk/)'s
`make_web_app_router` reads:

| Rule | Value |
| --- | --- |
| File | `immutable.json`, at the build root |
| `immutable` | a list of globs relative to the root |
| `**` | crosses directories |
| `*`, `?` | match inside one segment (do not cross `/`) |
| What matches | `Cache-Control: public, max-age=31536000, immutable` |
| Everything else | `no-cache` (revalidated by ETag) |
| Other keys | ignored (`generator` is only for human readers) |

The server **never** marks `index.html`, `bootstrap.js`, `sw.js`, `register.js`,
`manifest.webmanifest` or `immutable.json` itself as immutable, even if a glob
matches. They have fixed names and point at the hashed ones — that is why they
stay revalidated, and a new deploy shows up on the next visit.

!!! tip "Serving without the SDK"
    Any server works: read `immutable.json` once at startup and apply the header
    per path. In nginx, a `location ~ ^/client-[0-9a-f]{16}/` and a
    `location ~ ^/tempestweb-pkg\.[0-9a-f]{16}\.zip$` with
    `add_header Cache-Control "public, max-age=31536000, immutable";` do the
    same.

## The loading screen

The generated `index.html` now opens with a loading screen written in **plain
HTML and CSS** — painted on the first frame, before any script, WASM or font.
It follows `prefers-color-scheme` (light/dark), slows the spinner down under
`prefers-reduced-motion`, and walks through three stages:

| Stage | When | Default text |
| --- | --- | --- |
| `runtime` | downloading Pyodide | `Downloading the runtime…` |
| `python` | Python starting, wheels and payload loading | `Starting Python…` |
| `app` | importing `app.py` and building the first screen | `Building the app…` |

When the app mounts, the screen goes away. If the boot fails, it **stays**,
stops spinning and shows the error — instead of a blank page or an endless
spinner.

Customize it in `tempestweb.toml`:

```toml
[loading]
title = "My Panel"                    # default: [pwa] name, then the project name
runtime_text = "Downloading the runtime…"
python_text = "Starting Python…"
app_text = "Building the app…"
error_text = "The app failed to start."
background = "#0b1220"                # optional: applies to both schemes
foreground = "#e6e8eb"
accent = "#4f8cff"                    # spinner and dots
```

Or turn it off:

```toml
[loading]
enabled = false
```

!!! warning "A wrong key is an error, not silence"
    A key the screen does not know (`enable = false`, missing the `d`) fails the
    build with a `ConfigError` listing the valid keys. So does a colour with a
    `;`, a brace, a quote or a `<` — it is written inside a `<style>`.

## What it buys

Measured on the tempest-webtunnel dashboard, 390×844 phone, Fast 4G, 4× CPU
slowdown, Pyodide v314 from jsDelivr, server answering `no-cache`:

| | Before (0.139.0) | After |
| --- | --- | --- |
| Requests | 95 (85 same-origin) | 22 (6 same-origin) |
| Client JS | 81 modules, ~600 KB | 1 file, ~190 KB |
| Pyodide download starts at | 2.9 s | 0.2 s |
| App mounted — cold | 34.8 s | 33.4 s |
| App mounted — warm (3 runs) | 26.1–27.3 s | 23.3–23.9 s |
| First pixel | blank page until mount | loading screen on frame 1 |

!!! note "Read the numbers honestly"
    The total-time gain is a few seconds, not tens: a cold boot is dominated by
    **CPU** — compiling Pyodide's WASM (~17 s on that machine) and importing the
    app in Python. What this page fixes is the **network and serial waiting**
    time, plus the fact that the wait is now visible. The measurements were
    taken on a shared machine; values vary between runs, so the comparisons
    above are pairs measured side by side.

## Recap

- The Mode A client is **one** file, generated at release time and copied by
  the build.
- `bootstrap.js` starts **every** download before its first `await`, and
  `index.html` hints them with preload.
- Content-hashed names + `immutable.json` let the server cache the heavy parts
  for a year, while `index.html`/`bootstrap.js`/`app.py` stay revalidated.
- The loading screen shows up on the first frame, names the stage, shows the
  error when the boot fails, and is configured under `[loading]`. 🚀

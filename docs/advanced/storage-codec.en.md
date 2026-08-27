# Compressing what stays in the store (`native.storage.configure`)

!!! tip "What you'll learn"
    How to decide — **with a number, not by reflex** — whether it is worth
    compressing what your app keeps in the browser, and how to turn it on without
    wiping what is already on your users' devices. 📏

!!! danger "Measure your own payload before turning this on"
    This page exists because the intuitive answer is wrong. The gain is **not**
    what the compression ratio suggests, because **IndexedDB already compresses
    what it stores**. Turning the codec on by reflex trades CPU for far less disk
    than it looks like.

## What was measured

Real Chrome 150, driven by Playwright, virgin origin,
`CompressionStream("deflate")`. Each payload was written twice into separate
databases — once as a string, once as deflated bytes — with
`navigator.storage.estimate()` read before and after, waiting for the value to
settle.

| Payload | In memory | Deflate | **On disk, no codec** | IDB compressed it by |
| --- | --- | --- | --- | --- |
| catalogue, 5,000 rows | 976.9 KB | 120.6 KB | **222.1 KB** | **4.4×** |
| very repetitive history | 539.1 KB | 21.4 KB | **64.1 KB** | **8.4×** |
| random base64 noise | 143.6 KB | 93.6 KB | **126.5 KB** | 1.1× |

The codec is not competing with raw text: it is competing with the LevelDB under
IndexedDB. So the real saving is what is left over:

| Payload | No codec | With codec | **Real saving** |
| --- | --- | --- | --- |
| catalogue, 5,000 rows | 222.1 KB | 122.1 KB | **−45.0%** |
| repetitive history | 64.1 KB | 22.6 KB | **−64.8%** |
| base64 noise | 126.5 KB | 95.0 KB | **−24.9%** |

And what it costs, with the **CPU throttled 6×** to approximate a weak device.
The columns are what the codec **adds** to the path that already existed:

| Payload | read + (1×) | read + (6×) | write + (1×) | write + (6×) |
| --- | --- | --- | --- | --- |
| mutation queue (28 KB) | +0.3 ms | +2.8 ms | +0.8 ms | +4.8 ms |
| catalogue (~1 MB) | +2.1 ms | **+12.4 ms** | +13.0 ms | **+75.8 ms** |
| catalogue (~4 MB) | +6.1 ms | **+33.8 ms** | +49.7 ms | **+295.1 ms** |

## The conclusion, in one line

**Reading is cheap; writing is what hurts.** +12 ms per read to save 45% of 1 MB
is a good trade. 295 ms to write 4 MB on a weak device is a dropped frame you can
see.

| Turn it on if | Do not turn it on if |
| --- | --- |
| the app holds **tens of megabytes** of repetitive collection | the app holds drafts, a queue and preferences |
| writes are rare (syncing a catalogue once a day) | writes are hot (every interaction saves) |
| you measured **your** payload and the number worked out | you are enabling it "because compression is good" |

## Turning it on

```python
from tempestweb import native
from tempestweb.native.storage import CODEC_DEFLATE


async def prepare_store() -> None:
    """Turn the codec on and record what the browser managed to do."""
    result = await native.storage.configure(codec=CODEC_DEFLATE)
    print(result.requested, result.active, result.supported)
```

`configure` **never raises** for lack of support. It answers three fields:

| Field | What it says |
| --- | --- |
| `requested` | what you asked for |
| `active` | what the next writes will actually use |
| `supported` | whether this browser can run the requested codec |

!!! warning "Safari below 16.4 has no `CompressionStream`"
    On that device, `configure(codec="deflate")` answers
    `active="json", supported=False` and the store keeps working with plain text.
    A store that cannot compress is still a store; an exception here would be a
    dead screen on a real device your app has to serve.

## Turning it on and off wipes nothing

The point that makes the option safe: **decoding is always on; only encoding is
opt-in.** A stored value carries the name of the codec that wrote it, so the
reader never consults the current setting.

| Situation | What happens |
| --- | --- |
| Record written **before** the codec was on | still readable after turning it on |
| Record written **with** the codec, read after turning it off | still readable |
| Envelope naming a codec this browser cannot read | becomes a **cache miss** (`None`), not an exception |
| Corrupt bytes | become a cache miss, not an exception |

The first two rows were measured in real Chrome, writing a 565 KB catalogue:

```text
written with codec json      → stored as a string
written with codec deflate   → stored as {$twcodec, bytes}, 21.6 KB
read the old record with the codec ON        → intact ✅
read the compressed record with the codec OFF → intact ✅
```

Without those two, enabling the option would wipe the cache of everyone already
in the field — silently.

## What is out of scope

- **The mutation queue is not compressed.** It is small, hot and critical: it is
  not where quota hurts, and it is where write latency shows most. The codec is
  for `native.storage`, which is where the large collection lives — including
  whatever [`tempestweb.query`](../tutorial/query.md) persists.
- **The `localStorage` fallback does not compress.** It holds strings, not bytes;
  where IndexedDB is absent, `active` comes back `"json"`.
- **The store's schema does not change.** This is a codec, not a migration.

## Recap

- IndexedDB **already compresses**: the codec saves 45–65% of what is left, not
  87%.
- Reading costs little (+12 ms/MB on a weak device); writing costs a lot
  (+76 ms/MB, +295 ms at 4 MB).
- Default `"json"`, opt-in via `native.storage.configure(codec="deflate")`.
- An unsupported codec **falls back to `"json"` and reports**, never raises.
- Turning it on and off is safe in both directions, because decoding is always
  on.

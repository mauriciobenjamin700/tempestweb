"""tempestweb.native — typed Python wrappers over browser Web APIs (Track N).

The web sibling of ``tempestroid.native``: each device/web capability is a typed
Python awaitable that application code calls without caring whether its Python runs
in the browser (Mode A / WASM) or on the server (Mode B). The single seam that
differs between the modes is the installed :class:`NativeBridge` — see
:mod:`tempestweb.native.dispatch` for the full Mode-A vs Mode-B explanation and
``client/native/*.js`` for the browser glue.

Capabilities are exposed two ways. Import the module for the plan-facing namespaced
calls::

    from tempestweb import native

    res = await native.http.request("GET", "/api/items")
    pos = await native.geolocation.get()
    await native.audio.play("/audio/plim.wav", volume=0.4)
    result = await native.share(title="Hi", url="https://example.com")
    photo = await native.camera.capture()

or import the symbols directly::

    from tempestweb.native import request, get_position, ShareResult

Capabilities:

* **http** (N0) — :func:`~tempestweb.native.http.request` (retry + backoff +
  idempotency), :func:`~tempestweb.native.http.upload`,
  :func:`~tempestweb.native.http.poll`,
  :func:`~tempestweb.native.http.generate_idempotency_key`.
* **audio** (N1) — :func:`~tempestweb.native.audio.play` / ``stop``.
* **share** (N2) — :func:`~tempestweb.native.share.share` /
  :func:`~tempestweb.native.share.is_share_supported`.
* **geolocation / clipboard / storage** (N3) —
  :func:`~tempestweb.native.geolocation.get`, ``clipboard.read``/``write``,
  ``storage.put``/``get``/``list_keys``/``remove`` (layered over IndexedDB).
* **camera** (N4) — :func:`~tempestweb.native.camera.capture`.
* **notifications** — :func:`~tempestweb.native.notifications.notify` /
  ``request_permission``.
"""

from tempestweb.native import (
    audio,
    camera,
    clipboard,
    cookies,
    file,
    geolocation,
    http,
    install,
    notifications,
    offline,
    onnx,
    storage,
)
from tempestweb.native.audio import PlayResult
from tempestweb.native.bridges import FFIBridge, ProxyBridge
from tempestweb.native.camera import Photo, capture
from tempestweb.native.clipboard import read, write
from tempestweb.native.contract import (
    CAPABILITIES,
    MODE_C_CAPABILITIES,
    Capability,
    capability_names,
    mode_c_capability_names,
)
from tempestweb.native.dispatch import (
    NATIVE_RESULT_PREFIX,
    BrowserUnavailableError,
    NativeBridge,
    NativeError,
    current_bridge,
    install_bridge,
    native_call,
    resolve_native_result,
    send_native_call,
    uninstall_bridge,
)
from tempestweb.native.file import PickedFile, SaveResult
from tempestweb.native.file import pick as file_pick
from tempestweb.native.file import save as file_save
from tempestweb.native.geolocation import Position, get_position
from tempestweb.native.http import (
    HttpResponse,
    RetryOptions,
    generate_idempotency_key,
    poll,
    request,
    upload,
)
from tempestweb.native.install import InstallState
from tempestweb.native.install import prompt as install_prompt
from tempestweb.native.install import state as install_state
from tempestweb.native.notifications import (
    NotificationPermission,
    notify,
    request_permission,
    subscribe,
    unsubscribe,
)
from tempestweb.native.offline import Mutation, ReplayResult
from tempestweb.native.offline import enqueue as offline_enqueue
from tempestweb.native.offline import pending as offline_pending
from tempestweb.native.offline import replay as offline_replay
from tempestweb.native.offline import size as offline_size
from tempestweb.native.onnx import OnnxModel, Tensor
from tempestweb.native.share import (
    ShareOutcome,
    ShareResult,
    is_share_supported,
    share,
)
from tempestweb.native.storage import (
    get as storage_get,
)
from tempestweb.native.storage import (
    list_keys,
    put,
    remove,
)

__all__ = [
    # capability namespaces (plan-facing: native.http.request, native.audio.play, ...)
    "audio",
    "camera",
    "clipboard",
    "cookies",
    "file",
    "geolocation",
    "http",
    "install",
    "notifications",
    "offline",
    "onnx",
    "storage",
    # capability contract (the single source of truth across surfaces)
    "CAPABILITIES",
    "MODE_C_CAPABILITIES",
    "Capability",
    "capability_names",
    "mode_c_capability_names",
    # dispatch core + bridges (the Mode-A vs Mode-B seam)
    "NATIVE_RESULT_PREFIX",
    "BrowserUnavailableError",
    "FFIBridge",
    "NativeBridge",
    "NativeError",
    "ProxyBridge",
    "current_bridge",
    "install_bridge",
    "native_call",
    "resolve_native_result",
    "send_native_call",
    "uninstall_bridge",
    # http (N0)
    "HttpResponse",
    "RetryOptions",
    "generate_idempotency_key",
    "poll",
    "request",
    "upload",
    # audio (N1)
    "PlayResult",
    # share (N2)
    "ShareOutcome",
    "ShareResult",
    "is_share_supported",
    "share",
    # geolocation (N3)
    "Position",
    "get_position",
    # clipboard (N3)
    "read",
    "write",
    # storage (N3)
    "list_keys",
    "put",
    "remove",
    "storage_get",
    # camera (N4)
    "Photo",
    "capture",
    # onnx (onnxruntime-web bridge)
    "OnnxModel",
    "Tensor",
    # file (share/download output + pick input)
    "PickedFile",
    "SaveResult",
    "file_pick",
    "file_save",
    # install (PWA install prompt)
    "InstallState",
    "install_prompt",
    "install_state",
    # offline (durable mutation queue + replay)
    "Mutation",
    "ReplayResult",
    "offline_enqueue",
    "offline_pending",
    "offline_replay",
    "offline_size",
    # notifications
    "NotificationPermission",
    "notify",
    "request_permission",
    "subscribe",
    "unsubscribe",
]

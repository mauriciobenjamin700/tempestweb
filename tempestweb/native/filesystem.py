"""Native filesystem capability over the File System Access Web API.

:func:`open_file` sends a ``filesystem.open_file`` ``native_call`` and gets back
one or more files, each carrying an opaque handle id; ``client/native/
filesystem.js`` calls ``window.showOpenFilePicker`` and stores each live
``FileSystemFileHandle`` in a registry keyed by that id. :func:`write_file` sends
``filesystem.write_file`` with the id so the client can write back through the
matching handle, and :func:`save_file` calls ``window.showSaveFilePicker`` to
create a new file. The Python side never touches the handle — it only shuttles the
id and the base64 bytes.
"""

from __future__ import annotations

from dataclasses import dataclass

from tempestweb.native.dispatch import send_native_call

__all__ = ["FileHandle", "open_file", "save_file", "write_file"]


@dataclass(frozen=True)
class FileHandle:
    """A handle to a file opened or created through the File System Access API.

    Attributes:
        id: The opaque handle id; the client holds the live ``FileSystemFileHandle``
            in a registry keyed by this id.
        name: The file name (e.g. ``"report.pdf"``).
        mime_type: The file MIME type, or ``""`` when unknown.
        data_base64: The file bytes, base64-encoded; ``""`` for handles returned by
            :func:`save_file` (which creates an empty file).
    """

    id: str
    name: str
    mime_type: str
    data_base64: str


async def open_file(accept: str = "", multiple: bool = False) -> list[FileHandle]:
    """Open one or more files through the system file picker.

    Args:
        accept: A comma-separated list of accepted MIME types / extensions; all
            files are accepted when empty.
        multiple: Whether to allow selecting more than one file.

    Returns:
        The opened files as :class:`FileHandle` objects (an empty list when the
        user cancels the picker).

    Raises:
        NativeError: If the API is unavailable (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "filesystem.open_file",
        {"accept": accept, "multiple": multiple},
    )
    return [
        FileHandle(
            id=str(f.get("id", "")),
            name=str(f.get("name", "")),
            mime_type=str(f.get("mime_type", "")),
            data_base64=str(f.get("data_base64", "")),
        )
        for f in value.get("files", [])
    ]


async def write_file(handle_id: str, data_base64: str) -> None:
    """Write bytes back to a previously opened file.

    Args:
        handle_id: The opaque id from a :class:`FileHandle` returned by
            :func:`open_file` or :func:`save_file`.
        data_base64: The bytes to write, base64-encoded.

    Raises:
        NativeError: If the handle id is unknown (``not_found``), the write is
            refused (``permission_denied``), or the API is unavailable
            (``unavailable``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    await send_native_call(
        "filesystem.write_file",
        {"id": handle_id, "data_base64": data_base64},
    )


async def save_file(
    filename: str,
    data_base64: str,
    mime_type: str = "application/octet-stream",
) -> FileHandle:
    """Create a new file through the system save picker and write bytes to it.

    Args:
        filename: The suggested file name for the save dialog.
        data_base64: The initial file bytes, base64-encoded.
        mime_type: The file MIME type (defaults to
            ``"application/octet-stream"``).

    Returns:
        A :class:`FileHandle` for the created file. Its ``data_base64`` is empty —
        the bytes live in the file, not on the handle.

    Raises:
        NativeError: If the API is unavailable (``unavailable``) or the save is
            refused (``permission_denied``).
        BrowserUnavailableError: If called with no native bridge installed.
    """
    value = await send_native_call(
        "filesystem.save_file",
        {"filename": filename, "data_base64": data_base64, "mime_type": mime_type},
    )
    return FileHandle(
        id=str(value.get("id", "")),
        name=str(value.get("name", "")),
        mime_type=mime_type,
        data_base64="",
    )

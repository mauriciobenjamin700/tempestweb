"""`imaging`: the handle that keeps pixels off the bridge, and the strict options.

Two things are pinned. First, **`source` goes over the wire as a handle**, not as
bytes — `test_a_photo_is_addressed_by_handle_not_by_bytes` is the whole reason
this family exists, because in Mode B sending the bytes would push a 4 MB photo
over the network twice just to shrink it.

Second, **option models forbid extras**. `compress(photo, maxWidth=1600)` has to
raise: silently ignoring a misspelled option uploads a full-size photo and says
nothing, which is discovered by whoever pays for the bandwidth.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tempestweb.native import imaging, install_bridge, uninstall_bridge
from tempestweb.native.camera import Photo


class ScriptedBridge:
    """A fake bridge answering with scripted ``native_result`` values."""

    def __init__(self, script: list[Any]) -> None:
        self.script: list[Any] = script
        self.calls: list[dict[str, Any]] = []

    async def call(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(envelope)
        outcome = self.script.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return {"ok": True, "value": outcome}


COMPRESSED = {
    "ref": "blob:tw:7",
    "mime_type": "image/webp",
    "width": 1600,
    "height": 1200,
    "size_kb": 182.4,
    "quality": 0.71,
    "attempts": 4,
    "within_budget": True,
}


@pytest.fixture(autouse=True)
def _clean_bridge() -> Any:
    uninstall_bridge()
    yield
    uninstall_bridge()


# --------------------------------------------------------------------------
# The handle is the point
# --------------------------------------------------------------------------


async def test_a_photo_is_addressed_by_handle_not_by_bytes() -> None:
    """The bytes must not appear in the envelope. That is the whole design."""
    bridge = ScriptedBridge([COMPRESSED])
    install_bridge(bridge)
    photo = Photo(mime_type="image/jpeg", width=4000, height=3000, ref="blob:tw:1")

    await imaging.compress(photo, max_kb=200, max_width=1600)

    args = bridge.calls[0]["args"]
    assert args["source"] == "blob:tw:1"
    assert "data_base64" not in str(args)


async def test_a_bare_handle_is_accepted_as_the_source() -> None:
    install_bridge(ScriptedBridge([COMPRESSED]))
    result = await imaging.compress("blob:tw:1", max_kb=200)
    assert result.ref == "blob:tw:7"


async def test_a_result_can_be_the_source_of_the_next_call() -> None:
    """Chaining must not round-trip the bytes between the two steps."""
    bridge = ScriptedBridge(
        [COMPRESSED, {"ref": "blob:tw:8", "width": 800, "height": 600, "size_kb": 60.0}]
    )
    install_bridge(bridge)

    small = await imaging.compress("blob:tw:1", max_kb=200)
    await imaging.transform(small, width=800)

    assert bridge.calls[1]["args"]["source"] == "blob:tw:7"


async def test_a_photo_without_a_handle_falls_back_to_its_payload() -> None:
    """A photo captured before handles existed still works."""
    bridge = ScriptedBridge([COMPRESSED])
    install_bridge(bridge)
    photo = Photo(mime_type="image/png", data_base64="AQID")

    await imaging.compress(photo, max_kb=200)

    source = bridge.calls[0]["args"]["source"]
    assert isinstance(source, dict)
    assert source["data_base64"] == "AQID"


def test_as_upload_hands_the_handle_to_http_upload() -> None:
    """The last leg: the server gets the bytes, Python never does."""
    result = imaging.CompressedImage.model_validate(COMPRESSED)
    descriptor = result.as_upload("foto.jpg")

    assert descriptor == {
        "name": "foto.jpg",
        "type": "image/webp",
        "blob_id": "blob:tw:7",
    }


# --------------------------------------------------------------------------
# Options are strict; payloads are not
# --------------------------------------------------------------------------


def test_a_misspelled_option_raises_instead_of_being_dropped() -> None:
    with pytest.raises(ValidationError):
        imaging.CompressOptions(maxWidth=1600)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        imaging.TransformOptions(rotation=90)  # type: ignore[call-arg]


async def test_a_misspelled_inline_override_raises_too() -> None:
    """The inline spelling is the one people actually use."""
    install_bridge(ScriptedBridge([COMPRESSED]))
    with pytest.raises(ValidationError):
        await imaging.compress("blob:tw:1", maxWidth=1600)


def test_a_browser_payload_ignores_a_field_python_does_not_know() -> None:
    """The opposite rule: a newer client must not break an older Python."""
    result = imaging.CompressedImage.model_validate(
        {**COMPRESSED, "colour_profile": "display-p3"}
    )
    assert result.size_kb == 182.4


def test_the_option_models_are_frozen() -> None:
    from pydantic import ValidationError as PydanticValidationError

    options = imaging.CompressOptions(max_kb=200)
    with pytest.raises(PydanticValidationError):
        options.max_kb = 100  # type: ignore[misc]


# --------------------------------------------------------------------------
# What each capability answers
# --------------------------------------------------------------------------


async def test_compress_reports_where_the_search_landed() -> None:
    install_bridge(ScriptedBridge([COMPRESSED]))

    result = await imaging.compress("blob:tw:1", max_kb=200, max_width=1600)

    assert result.size_kb == 182.4
    assert result.quality == 0.71
    assert result.attempts == 4
    assert result.within_budget


async def test_an_impossible_budget_is_reported_not_raised() -> None:
    """`within_budget=False` is an answer the app decides about."""
    install_bridge(
        ScriptedBridge([{**COMPRESSED, "within_budget": False, "size_kb": 412.0}])
    )

    result = await imaging.compress("blob:tw:1", max_kb=200)

    assert not result.within_budget
    assert result.size_kb == 412.0


async def test_thumbnails_come_back_one_per_size() -> None:
    install_bridge(
        ScriptedBridge(
            [
                {
                    "thumbnails": [
                        {"ref": "blob:tw:2", "size": 96, "width": 96, "height": 72},
                        {"ref": "blob:tw:3", "size": 256, "width": 256, "height": 192},
                    ]
                }
            ]
        )
    )

    result = await imaging.thumbnails("blob:tw:1", [96, 256])

    assert [t.size for t in result] == [96, 256]
    assert result[0].ref == "blob:tw:2"


async def test_no_thumbnails_is_an_empty_list_not_an_error() -> None:
    install_bridge(ScriptedBridge([{"thumbnails": []}]))
    assert await imaging.thumbnails("blob:tw:1", []) == []


async def test_a_truncated_thumbnail_answer_is_an_empty_list() -> None:
    install_bridge(ScriptedBridge([{}]))
    assert await imaging.thumbnails("blob:tw:1", [96]) == []


async def test_transform_sends_every_option_it_was_given() -> None:
    bridge = ScriptedBridge([{"ref": "blob:tw:9", "width": 400, "height": 400}])
    install_bridge(bridge)

    await imaging.transform(
        "blob:tw:1",
        width=400,
        rotate=90,
        flip_horizontal=True,
        crop=imaging.CropBox(x=10, y=20, width=100, height=100),
    )

    args = bridge.calls[0]["args"]
    assert args["rotate"] == 90
    assert args["flip_horizontal"] is True
    assert args["crop"] == {"x": 10, "y": 20, "width": 100, "height": 100}


async def test_info_asks_for_the_shape_only() -> None:
    install_bridge(
        ScriptedBridge(
            [
                {
                    "mime_type": "image/jpeg",
                    "width": 4000,
                    "height": 3000,
                    "size_kb": 3890.2,
                }
            ]
        )
    )

    result = await imaging.info("blob:tw:1")

    assert (result.width, result.height) == (4000, 3000)
    assert result.size_kb == 3890.2


async def test_read_is_the_escape_hatch_and_decodes() -> None:
    install_bridge(
        ScriptedBridge(
            [{"data_base64": "AQID", "mime_type": "image/png", "size_kb": 0.1}]
        )
    )

    result = await imaging.read("blob:tw:1")

    assert result.to_bytes() == b"\x01\x02\x03"


async def test_release_answers_how_many_went() -> None:
    bridge = ScriptedBridge([{"released": 1}, {"released": 0}, {"released": 5}])
    install_bridge(bridge)

    assert await imaging.release("blob:tw:1") == 1
    assert await imaging.release("blob:tw:1") == 0
    assert await imaging.release(all=True) == 5
    assert bridge.calls[2]["args"] == {"all": True}


# --------------------------------------------------------------------------
# Contract
# --------------------------------------------------------------------------


def test_the_six_capabilities_reach_mode_c() -> None:
    from tempestweb.native import contract

    mode_c = {cap.name for cap in contract.MODE_C_CAPABILITIES}
    expected = {
        "imaging.compress",
        "imaging.thumbnails",
        "imaging.transform",
        "imaging.info",
        "imaging.read",
        "imaging.release",
    }

    assert expected <= mode_c

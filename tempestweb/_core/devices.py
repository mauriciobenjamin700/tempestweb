"""Screen-size presets for common Android devices.

The simulator window has no physical screen to borrow dimensions from, so it
defaults to a generic phone size. This enum lets a developer pin the simulator
(and any layout test) to the *logical* viewport of a real device — the
density-independent pixel (``dp``) size Compose lays out against, i.e.
``physical_px / density``, **not** the raw hardware resolution.

Each member carries ``width`` / ``height`` (in ``dp``) and a human ``label``;
``.size`` returns the ``(width, height)`` tuple for ``host.resize(*size)``.

Example:
    >>> from tempestweb._core.devices import Device
    >>> Device.PIXEL_7.size
    (412, 915)
    >>> Device.REDMI_NOTE_12.label
    "Xiaomi Redmi Note 12"
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Device", "DEFAULT_DEVICE", "resolve_device"]


class Device(Enum):
    """A named Android device screen preset, sized in logical ``dp``.

    Each member's value is its unique ``label``; the viewport lives in the
    ``width`` / ``height`` attributes (and ``.size``). Sizes are
    ``physical_px / density`` — what Compose lays out against — sourced from each
    vendor's published spec / the standard device-metrics tables. The enum value
    is the label, **not** the size, because many phones share the same viewport
    and equal enum values would silently collapse into aliases.

    Attributes:
        width: Logical viewport width in density-independent pixels (``dp``).
        height: Logical viewport height in density-independent pixels (``dp``).
        label: Human-readable device name (the member's value).
    """

    width: int
    height: int
    label: str

    # Google Pixel
    PIXEL_4 = (353, 745, "Google Pixel 4")
    PIXEL_5 = (393, 851, "Google Pixel 5")
    PIXEL_6 = (412, 915, "Google Pixel 6")
    PIXEL_6_PRO = (412, 892, "Google Pixel 6 Pro")
    PIXEL_7 = (412, 915, "Google Pixel 7")
    PIXEL_7_PRO = (412, 892, "Google Pixel 7 Pro")
    PIXEL_8 = (412, 915, "Google Pixel 8")
    PIXEL_8_PRO = (448, 998, "Google Pixel 8 Pro")
    # Samsung Galaxy S
    GALAXY_S8 = (360, 740, "Samsung Galaxy S8")
    GALAXY_S9 = (360, 740, "Samsung Galaxy S9")
    GALAXY_S10 = (360, 760, "Samsung Galaxy S10")
    GALAXY_S20 = (360, 800, "Samsung Galaxy S20")
    GALAXY_S21 = (360, 800, "Samsung Galaxy S21")
    GALAXY_S22 = (360, 780, "Samsung Galaxy S22")
    GALAXY_S23 = (360, 780, "Samsung Galaxy S23")
    GALAXY_S24 = (384, 824, "Samsung Galaxy S24")
    GALAXY_S24_ULTRA = (384, 832, "Samsung Galaxy S24 Ultra")
    # Samsung Galaxy A (mid-range, very common)
    GALAXY_A51 = (412, 914, "Samsung Galaxy A51")
    GALAXY_A52 = (412, 914, "Samsung Galaxy A52")
    GALAXY_A54 = (360, 800, "Samsung Galaxy A54")
    # Xiaomi Redmi Note
    REDMI_NOTE_10 = (393, 873, "Xiaomi Redmi Note 10")
    REDMI_NOTE_11 = (393, 873, "Xiaomi Redmi Note 11")
    REDMI_NOTE_12 = (393, 873, "Xiaomi Redmi Note 12")
    REDMI_NOTE_13 = (393, 873, "Xiaomi Redmi Note 13")
    # Xiaomi Redmi / Poco
    REDMI_11 = (393, 873, "Xiaomi Redmi 11")
    REDMI_12 = (393, 873, "Xiaomi Redmi 12")
    POCO_X5 = (393, 873, "Xiaomi Poco X5")
    # Xiaomi flagship
    XIAOMI_13 = (393, 873, "Xiaomi 13")
    XIAOMI_14 = (393, 873, "Xiaomi 14")
    # Motorola
    MOTO_G_POWER = (412, 915, "Motorola Moto G Power")
    MOTO_G52 = (393, 873, "Motorola Moto G52")
    # OnePlus
    ONEPLUS_9 = (412, 919, "OnePlus 9")
    ONEPLUS_11 = (412, 919, "OnePlus 11")

    def __new__(cls, width: int, height: int, label: str) -> Device:
        """Build a member keyed by its unique ``label``.

        Args:
            width: Logical viewport width in ``dp``.
            height: Logical viewport height in ``dp``.
            label: Human-readable device name (also the member's value).

        Returns:
            The constructed enum member.
        """
        obj: Device = object.__new__(cls)
        obj._value_ = label
        obj.width = width
        obj.height = height
        obj.label = label
        return obj

    @property
    def size(self) -> tuple[int, int]:
        """The viewport as a ``(width, height)`` tuple.

        Returns:
            The ``(width, height)`` pair in ``dp``, ready for
            ``host.resize(*device.size)``.
        """
        return (self.width, self.height)


# The simulator's default when no device is chosen — a generic mid-size phone.
DEFAULT_DEVICE: Device = Device.REDMI_NOTE_12


def resolve_device(name: str) -> Device | None:
    """Resolve a user-supplied device name to a :class:`Device` preset.

    Matching is forgiving: the enum member name or its human label, compared
    case-insensitively with ``-``/``_``/spaces normalized away. So ``"pixel-7"``,
    ``"PIXEL_7"``, ``"pixel 7"`` and ``"Google Pixel 7"`` all resolve to
    :attr:`Device.PIXEL_7`.

    Args:
        name: The device identifier to resolve.

    Returns:
        The matching :class:`Device`, or ``None`` when no preset matches.
    """

    def _norm(value: str) -> str:
        return value.lower().replace("-", "").replace("_", "").replace(" ", "")

    target = _norm(name)
    for member in Device:
        if _norm(member.name) == target or _norm(member.label) == target:
            return member
    return None

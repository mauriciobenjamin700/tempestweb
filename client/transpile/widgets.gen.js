// widgets.gen.js — GENERATED from tempest_core by tempestweb transpile (Mode C).
// One native-JS IR builder per buildable core widget. Handlers are stashed in a
// non-wire `__handlers` map (DOM event type -> closure); the runtime dispatches from it.
// Regenerate: python -m tests.conformance._transpile_widgets. Do not edit.

import { resolveWidgetStyle, Style } from "./widget-support.js";
export { Edge, Style } from "./widget-support.js";

// `Style` is re-exported for apps; reference it so linters see the import as used.
void Style;

/**
 * Build a `ActionSheet` IR node (type `ActionSheet`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ActionSheet({ key = null, focusOrder = null, focusable = null, items = [], semantics = null, tag = null, title = null, attrs = {}, style = null, onSelect = null } = {}) {
  return {
    type: "ActionSheet",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      items: items,
      on_select: null,
      semantics: semantics,
      style: style,
      tag: tag,
      title: title,
    },
    children: [],
    __handlers: { "select": onSelect },
  };
}

/**
 * Build a `AnimatedList` IR node (type `AnimatedList`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function AnimatedList({ key = null, direction = "column", enterCurve = "ease-out", enterDurationMs = 300, exitCurve = "ease-in", exitDurationMs = 300, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "AnimatedList",
    key,
    props: {
      attrs,
      direction: direction,
      enter_curve: enterCurve,
      enter_duration_ms: enterDurationMs,
      exit_curve: exitCurve,
      exit_duration_ms: exitDurationMs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `Autocomplete` IR node (type `Autocomplete`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Autocomplete({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, leadingIcon = null, options = [], placeholder = "", semantics = null, size = "md", tag = null, trailingIcon = null, value = "", attrs = {}, style = null, onChange = null, onSelect = null } = {}) {
  return {
    type: "Autocomplete",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      leading_icon: leadingIcon,
      on_change: null,
      on_select: null,
      options: options,
      placeholder: placeholder,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("Autocomplete", fieldVariant, size, colorScheme, style),
      tag: tag,
      trailing_icon: trailingIcon,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange, "select": onSelect },
  };
}

/**
 * Build a `BackdropFilter` IR node (type `BackdropFilter`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function BackdropFilter({ key = null, focusOrder = null, focusable = null, radius = 8.0, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "BackdropFilter",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      radius: radius,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `Blur` IR node (type `Blur`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Blur({ key = null, focusOrder = null, focusable = null, radius = 8.0, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Blur",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      radius: radius,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `BottomSheet` IR node (type `BottomSheet`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function BottomSheet({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onDismiss = null } = {}) {
  return {
    type: "BottomSheet",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_dismiss: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "dismiss": onDismiss },
  };
}

/**
 * Build a `Button` IR node (type `Button`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Button({ label, key = null, colorScheme = "primary", focusOrder = null, focusable = null, semantics = null, size = "md", tag = null, variant = "solid", attrs = {}, style = null, onClick = null } = {}) {
  return {
    type: "Button",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      on_click: null,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("Button", variant, size, colorScheme, style),
      tag: tag,
      variant: variant,
    },
    children: [],
    __handlers: { "click": onClick },
  };
}

/**
 * Build a `CameraPreview` IR node (type `CameraPreview`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function CameraPreview({ key = null, facing = "back", focusOrder = null, focusable = null, frameIntervalMs = 300, semantics = null, tag = null, attrs = {}, style = null, onFrame = null } = {}) {
  return {
    type: "CameraPreview",
    key,
    props: {
      attrs,
      facing: facing,
      focus_order: focusOrder,
      focusable: focusable,
      frame_interval_ms: frameIntervalMs,
      on_frame: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
    __handlers: { "frame": onFrame },
  };
}

/**
 * Build a `Canvas` IR node (type `Canvas`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Canvas({ key = null, commands = [], focusOrder = null, focusable = null, height = null, semantics = null, tag = null, width = null, attrs = {}, style = null } = {}) {
  return {
    type: "Canvas",
    key,
    props: {
      attrs,
      commands: commands,
      focus_order: focusOrder,
      focusable: focusable,
      height: height,
      semantics: semantics,
      style: style,
      tag: tag,
      width: width,
    },
    children: [],
  };
}

/**
 * Build a `Checkbox` IR node (type `Checkbox`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Checkbox({ key = null, checked = false, colorScheme = "primary", focusOrder = null, focusable = null, label = "", semantics = null, size = "md", tag = null, attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "Checkbox",
    key,
    props: {
      attrs,
      checked: checked,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      on_change: null,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("Checkbox", "_", size, colorScheme, style),
      tag: tag,
    },
    children: [],
    __handlers: { "input": onChange, "change": onChange },
  };
}

/**
 * Build a `ClipPath` IR node (type `ClipPath`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ClipPath({ key = null, focusOrder = null, focusable = null, radius = 8.0, semantics = null, shape = "rounded_rect", tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "ClipPath",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      radius: radius,
      semantics: semantics,
      shape: shape,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `Column` IR node (type `Column`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Column({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Column",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `Container` IR node (type `Container`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Container({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Container",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `DatePicker` IR node (type `DatePicker`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function DatePicker({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, label = "", semantics = null, size = "md", tag = null, value = "", attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "DatePicker",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      on_change: null,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("DatePicker", fieldVariant, size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `Dialog` IR node (type `Dialog`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Dialog({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, title = null, attrs = {}, style = null, children = [], onDismiss = null } = {}) {
  return {
    type: "Dialog",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_dismiss: null,
      semantics: semantics,
      style: style,
      tag: tag,
      title: title,
    },
    children: children,
    __handlers: { "dismiss": onDismiss },
  };
}

/**
 * Build a `Dismissible` IR node (type `Dismissible`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Dismissible({ key = null, direction = "left", focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onDismiss = null } = {}) {
  return {
    type: "Dismissible",
    key,
    props: {
      attrs,
      direction: direction,
      focus_order: focusOrder,
      focusable: focusable,
      on_dismiss: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "dismiss": onDismiss },
  };
}

/**
 * Build a `DoubleTapHandler` IR node (type `DoubleTapHandler`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function DoubleTapHandler({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onDoubleTap = null } = {}) {
  return {
    type: "DoubleTapHandler",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_double_tap: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "double_tap": onDoubleTap },
  };
}

/**
 * Build a `DragTarget` IR node (type `DragTarget`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function DragTarget({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onDrop = null } = {}) {
  return {
    type: "DragTarget",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_drop: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "drop": onDrop },
  };
}

/**
 * Build a `Draggable` IR node (type `Draggable`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Draggable({ key = null, dragData = "", focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onDrag = null } = {}) {
  return {
    type: "Draggable",
    key,
    props: {
      attrs,
      drag_data: dragData,
      focus_order: focusOrder,
      focusable: focusable,
      on_drag: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "drag": onDrag },
  };
}

/**
 * Build a `Dropdown` IR node (type `Dropdown`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Dropdown({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, leadingIcon = null, options = [], placeholder = "Select…", semantics = null, size = "md", tag = null, trailingIcon = null, value = null, attrs = {}, style = null, onSelect = null } = {}) {
  return {
    type: "Dropdown",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      leading_icon: leadingIcon,
      on_select: null,
      options: options,
      placeholder: placeholder,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("Dropdown", fieldVariant, size, colorScheme, style),
      tag: tag,
      trailing_icon: trailingIcon,
      value: value,
    },
    children: [],
    __handlers: { "select": onSelect },
  };
}

/**
 * Build a `FilePicker` IR node (type `FilePicker`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function FilePicker({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, label = "Choose file", semantics = null, size = "md", tag = null, value = "", attrs = {}, style = null, onSelect = null } = {}) {
  return {
    type: "FilePicker",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      on_select: null,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("FilePicker", fieldVariant, size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "select": onSelect },
  };
}

/**
 * Build a `Form` IR node (type `Form`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Form({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, onSubmit = null } = {}) {
  return {
    type: "Form",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_submit: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
    __handlers: { "submit": onSubmit },
  };
}

/**
 * Build a `FormField` IR node (type `FormField`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function FormField({ name, key = null, error = "", focusOrder = null, focusable = null, label = "", semantics = null, tag = null, validators = [], attrs = {}, style = null, children = [], onValidate = null } = {}) {
  return {
    type: "FormField",
    key,
    props: {
      attrs,
      error: error,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      name: name,
      on_validate: null,
      semantics: semantics,
      style: style,
      tag: tag,
      validators: validators,
    },
    children: children,
    __handlers: { "validate": onValidate },
  };
}

/**
 * Build a `GestureDetector` IR node (type `GestureDetector`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function GestureDetector({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onTap = null, onDoubleTap = null, onLongPress = null, onSwipe = null } = {}) {
  return {
    type: "GestureDetector",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_double_tap: null,
      on_long_press: null,
      on_swipe: null,
      on_tap: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "tap": onTap, "double_tap": onDoubleTap, "long_press": onLongPress, "swipe": onSwipe },
  };
}

/**
 * Build a `Icon` IR node (type `Icon`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Icon({ name, key = null, focusOrder = null, focusable = null, semantics = null, size = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Icon",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      name: name,
      semantics: semantics,
      size: size,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `Image` IR node (type `Image`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Image({ src, key = null, alt = "", fit = "contain", focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Image",
    key,
    props: {
      alt: alt,
      attrs,
      fit: fit,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      src: src,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `Input` IR node (type `Input`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Input({ key = null, colorScheme = "primary", error = "", fieldVariant = "outline", focusOrder = null, focusable = null, keyboard = "text", leadingIcon = null, maxLength = null, pattern = null, placeholder = "", secure = false, semantics = null, size = "md", tag = null, trailingIcon = null, value = "", attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "Input",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      error: error,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      keyboard: keyboard,
      leading_icon: leadingIcon,
      max_length: maxLength,
      on_change: null,
      pattern: pattern,
      placeholder: placeholder,
      secure: secure,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("Input", fieldVariant, size, colorScheme, style),
      tag: tag,
      trailing_icon: trailingIcon,
      value: value,
    },
    children: [],
    __handlers: { "input": onChange, "change": onChange },
  };
}

/**
 * Build a `InteractiveViewer` IR node (type `InteractiveViewer`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function InteractiveViewer({ key = null, focusOrder = null, focusable = null, maxScale = 4.0, minScale = 0.5, semantics = null, tag = null, attrs = {}, style = null, children = [], onInteraction = null } = {}) {
  return {
    type: "InteractiveViewer",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      max_scale: maxScale,
      min_scale: minScale,
      on_interaction: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "interaction": onInteraction },
  };
}

/**
 * Build a `KeyboardAvoidingView` IR node (type `KeyboardAvoidingView`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function KeyboardAvoidingView({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "KeyboardAvoidingView",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `MapView` IR node (type `MapView`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function MapView({ key = null, focusOrder = null, focusable = null, latitude = 0.0, longitude = 0.0, markers = [], semantics = null, tag = null, zoom = 12.0, attrs = {}, style = null } = {}) {
  return {
    type: "MapView",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      latitude: latitude,
      longitude: longitude,
      markers: markers,
      semantics: semantics,
      style: style,
      tag: tag,
      zoom: zoom,
    },
    children: [],
  };
}

/**
 * Build a `MaskedInput` IR node (type `MaskedInput`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function MaskedInput({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, keyboard = "text", mask = "", placeholder = "", semantics = null, size = "md", tag = null, value = "", attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "MaskedInput",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      keyboard: keyboard,
      mask: mask,
      on_change: null,
      placeholder: placeholder,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("MaskedInput", fieldVariant, size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `Menu` IR node (type `Menu`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Menu({ key = null, anchor = null, focusOrder = null, focusable = null, items = [], semantics = null, tag = null, attrs = {}, style = null, onSelect = null } = {}) {
  return {
    type: "Menu",
    key,
    props: {
      anchor: anchor,
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      items: items,
      on_select: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
    __handlers: { "select": onSelect },
  };
}

/**
 * Build a `PageView` IR node (type `PageView`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function PageView({ key = null, focusOrder = null, focusable = null, page = 0, semantics = null, tag = null, attrs = {}, style = null, children = [], onPageChange = null } = {}) {
  return {
    type: "PageView",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_page_change: null,
      page: page,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "page_change": onPageChange },
  };
}

/**
 * Build a `PanHandler` IR node (type `PanHandler`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function PanHandler({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onPan = null } = {}) {
  return {
    type: "PanHandler",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_pan: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "pan": onPan },
  };
}

/**
 * Build a `PanHandlerWidget` IR node (type `PanHandler`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function PanHandlerWidget({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onPan = null } = {}) {
  return {
    type: "PanHandler",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_pan: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "pan": onPan },
  };
}

/**
 * Build a `PinInput` IR node (type `PinInput`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function PinInput({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, length = 6, secure = false, semantics = null, size = "md", tag = null, value = "", attrs = {}, style = null, onChange = null, onComplete = null } = {}) {
  return {
    type: "PinInput",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      length: length,
      on_change: null,
      on_complete: null,
      secure: secure,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("PinInput", fieldVariant, size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange, "complete": onComplete },
  };
}

/**
 * Build a `Popover` IR node (type `Popover`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Popover({ key = null, anchor = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onDismiss = null } = {}) {
  return {
    type: "Popover",
    key,
    props: {
      anchor: anchor,
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_dismiss: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "dismiss": onDismiss },
  };
}

/**
 * Build a `ProgressBar` IR node (type `ProgressBar`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ProgressBar({ key = null, colorScheme = "primary", focusOrder = null, focusable = null, indeterminate = false, semantics = null, tag = null, value = 0.0, attrs = {}, style = null } = {}) {
  return {
    type: "ProgressBar",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      indeterminate: indeterminate,
      semantics: semantics,
      style: style,
      tag: tag,
      value: value,
    },
    children: [],
  };
}

/**
 * Build a `QrScanner` IR node (type `QrScanner`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function QrScanner({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, onScan = null } = {}) {
  return {
    type: "QrScanner",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_scan: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
    __handlers: { "scan": onScan },
  };
}

/**
 * Build a `RangeSlider` IR node (type `RangeSlider`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function RangeSlider({ key = null, colorScheme = "primary", focusOrder = null, focusable = null, high = 100.0, low = 0.0, maxValue = 100.0, minValue = 0.0, semantics = null, size = "md", step = 1.0, tag = null, attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "RangeSlider",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      high: high,
      low: low,
      max_value: maxValue,
      min_value: minValue,
      on_change: null,
      semantics: semantics,
      size: size,
      step: step,
      style: resolveWidgetStyle("RangeSlider", "_", size, colorScheme, style),
      tag: tag,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `RefreshControl` IR node (type `RefreshControl`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function RefreshControl({ key = null, focusOrder = null, focusable = null, refreshing = false, semantics = null, tag = null, attrs = {}, style = null, onRefresh = null } = {}) {
  return {
    type: "RefreshControl",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_refresh: null,
      refreshing: refreshing,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
    __handlers: { "refresh": onRefresh },
  };
}

/**
 * Build a `ReorderableList` IR node (type `ReorderableList`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ReorderableList({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onReorder = null } = {}) {
  return {
    type: "ReorderableList",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_reorder: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "reorder": onReorder },
  };
}

/**
 * Build a `Row` IR node (type `Row`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Row({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Row",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `SafeArea` IR node (type `SafeArea`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function SafeArea({ key = null, edges = ["top", "right", "bottom", "left"], focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "SafeArea",
    key,
    props: {
      attrs,
      edges: edges,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `ScaleHandler` IR node (type `ScaleHandler`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ScaleHandler({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onScale = null, onDoubleTap = null } = {}) {
  return {
    type: "ScaleHandler",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_double_tap: null,
      on_scale: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "scale": onScale, "double_tap": onDoubleTap },
  };
}

/**
 * Build a `ScaleHandlerWidget` IR node (type `ScaleHandler`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ScaleHandlerWidget({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [], onScale = null, onDoubleTap = null } = {}) {
  return {
    type: "ScaleHandler",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_double_tap: null,
      on_scale: null,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
    __handlers: { "scale": onScale, "double_tap": onDoubleTap },
  };
}

/**
 * Build a `ScrollView` IR node (type `ScrollView`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function ScrollView({ key = null, focusOrder = null, focusable = null, horizontal = false, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "ScrollView",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      horizontal: horizontal,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `SectionList` IR node (type `SectionList`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function SectionList({ key = null, endReachedThreshold = 0.8, focusOrder = null, focusable = null, sections = [], semantics = null, tag = null, attrs = {}, style = null, onScroll = null, onEndReached = null } = {}) {
  return {
    type: "SectionList",
    key,
    props: {
      attrs,
      end_reached_threshold: endReachedThreshold,
      focus_order: focusOrder,
      focusable: focusable,
      on_end_reached: null,
      on_scroll: null,
      sections: sections,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
    __handlers: { "scroll": onScroll, "end_reached": onEndReached },
  };
}

/**
 * Build a `Skeleton` IR node (type `Skeleton`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Skeleton({ key = null, baseColor = {"r": 224, "g": 224, "b": 224, "a": 1.0}, colorScheme = "neutral", durationMs = 1200, focusOrder = null, focusable = null, height = null, highlightColor = {"r": 245, "g": 245, "b": 245, "a": 1.0}, radius = 4.0, semantics = null, tag = null, width = null, attrs = {}, style = null } = {}) {
  return {
    type: "Skeleton",
    key,
    props: {
      attrs,
      base_color: baseColor,
      color_scheme: colorScheme,
      duration_ms: durationMs,
      focus_order: focusOrder,
      focusable: focusable,
      height: height,
      highlight_color: highlightColor,
      radius: radius,
      semantics: semantics,
      style: style,
      tag: tag,
      width: width,
    },
    children: [],
  };
}

/**
 * Build a `Slider` IR node (type `Slider`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Slider({ key = null, colorScheme = "primary", focusOrder = null, focusable = null, maxValue = 100.0, minValue = 0.0, semantics = null, size = "md", step = 1.0, tag = null, value = 0.0, attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "Slider",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      max_value: maxValue,
      min_value: minValue,
      on_change: null,
      semantics: semantics,
      size: size,
      step: step,
      style: resolveWidgetStyle("Slider", "_", size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `Spacer` IR node (type `Spacer`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Spacer({ key = null, flex = 1.0, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Spacer",
    key,
    props: {
      attrs,
      flex: flex,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: resolveWidgetStyle("Spacer", "_", "_", "_", style),
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `Spinner` IR node (type `Spinner`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Spinner({ key = null, colorScheme = "primary", focusOrder = null, focusable = null, semantics = null, size = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Spinner",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      size: size,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `Stack` IR node (type `Stack`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Stack({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Stack",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `Svg` IR node (type `Svg`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Svg({ src, key = null, fit = "contain", focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Svg",
    key,
    props: {
      attrs,
      fit: fit,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      src: src,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `Switch` IR node (type `Switch`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Switch({ key = null, checked = false, colorScheme = "primary", focusOrder = null, focusable = null, label = "", semantics = null, size = "md", tag = null, attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "Switch",
    key,
    props: {
      attrs,
      checked: checked,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      on_change: null,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("Switch", "_", size, colorScheme, style),
      tag: tag,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `TabBar` IR node (type `TabBar`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function TabBar({ tabs, key = null, active = 0, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "TabBar",
    key,
    props: {
      active: active,
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      on_change: null,
      semantics: semantics,
      style: style,
      tabs: tabs,
      tag: tag,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `Text` IR node (type `Text`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Text({ content, key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Text",
    key,
    props: {
      attrs,
      content: content,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `TextArea` IR node (type `TextArea`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function TextArea({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, maxLength = null, placeholder = "", rows = 3, semantics = null, size = "md", tag = null, value = "", attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "TextArea",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      max_length: maxLength,
      on_change: null,
      placeholder: placeholder,
      rows: rows,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("TextArea", fieldVariant, size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `TimePicker` IR node (type `TimePicker`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function TimePicker({ key = null, colorScheme = "primary", fieldVariant = "outline", focusOrder = null, focusable = null, label = "", semantics = null, size = "md", tag = null, value = "", attrs = {}, style = null, onChange = null } = {}) {
  return {
    type: "TimePicker",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      field_variant: fieldVariant,
      focus_order: focusOrder,
      focusable: focusable,
      label: label,
      on_change: null,
      semantics: semantics,
      size: size,
      style: resolveWidgetStyle("TimePicker", fieldVariant, size, colorScheme, style),
      tag: tag,
      value: value,
    },
    children: [],
    __handlers: { "click": onChange },
  };
}

/**
 * Build a `Toast` IR node (type `Toast`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Toast({ message, key = null, durationS = 2.5, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "Toast",
    key,
    props: {
      attrs,
      duration_s: durationS,
      focus_order: focusOrder,
      focusable: focusable,
      message: message,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `Tooltip` IR node (type `Tooltip`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Tooltip({ message, key = null, colorScheme = "neutral", focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Tooltip",
    key,
    props: {
      attrs,
      color_scheme: colorScheme,
      focus_order: focusOrder,
      focusable: focusable,
      message: message,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

/**
 * Build a `VideoPlayer` IR node (type `VideoPlayer`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function VideoPlayer({ src, key = null, autoplay = false, controls = true, focusOrder = null, focusable = null, loop = false, muted = false, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "VideoPlayer",
    key,
    props: {
      attrs,
      autoplay: autoplay,
      controls: controls,
      focus_order: focusOrder,
      focusable: focusable,
      loop: loop,
      muted: muted,
      semantics: semantics,
      src: src,
      style: style,
      tag: tag,
    },
    children: [],
  };
}

/**
 * Build a `WebView` IR node (type `WebView`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function WebView({ url, key = null, focusOrder = null, focusable = null, javascriptEnabled = true, semantics = null, tag = null, attrs = {}, style = null } = {}) {
  return {
    type: "WebView",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      javascript_enabled: javascriptEnabled,
      semantics: semantics,
      style: style,
      tag: tag,
      url: url,
    },
    children: [],
  };
}

/**
 * Build a `Wrap` IR node (type `Wrap`).
 * @param {Object} [args]  Widget props (handlers stashed off-wire).
 * @returns {import("../transport.js").Node}
 */
export function Wrap({ key = null, focusOrder = null, focusable = null, semantics = null, tag = null, attrs = {}, style = null, children = [] } = {}) {
  return {
    type: "Wrap",
    key,
    props: {
      attrs,
      focus_order: focusOrder,
      focusable: focusable,
      semantics: semantics,
      style: style,
      tag: tag,
    },
    children: children,
  };
}

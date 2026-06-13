// icons/index.js — resolve an icon name to an inline SVG and render it.
//
// The core's `Icon` widget serializes as `{type:"Icon", props:{name, size}}` and
// carries only the NAME over the wire — never the geometry. This module owns the
// name -> SVG resolution on the client, from vendored path data (no font, no
// network, offline/PWA-safe). Icons are tinted via `currentColor`, so an Icon's
// Style `color` sets the icon color and `size` (or Style width/height) its size.
//
// Name grammar (the "set:" prefix picks the source):
//   "mail"            -> Lucide (bare name = default set)
//   "lucide:mail"     -> Lucide, explicitly
//   "material:home"   -> Material Symbols (Outlined)
//   "path:M3 3 ..."   -> a raw SVG path `d` (24x24 stroke grid); lets an app ship
//                        ANY glyph over the wire without a client-side registry
//   <custom>          -> whatever registerIcon() registered, else falls through
//                        to the Lucide set.

import { LUCIDE_PATHS, LUCIDE_VIEWBOX } from "./lucide.js";
import { MATERIAL_PATHS, MATERIAL_VIEWBOX } from "./material.js";

/** The SVG namespace; SVG elements must be created with it, not createElement. */
export const SVG_NS = "http://www.w3.org/2000/svg";

const DATA_NAME = "data-tw-icon";

/**
 * @typedef {Object} IconDef
 * @property {string} d         The SVG path `d` string.
 * @property {string} viewBox   The SVG viewBox the path is drawn on.
 * @property {"stroke"|"fill"} mode  Whether the path is stroked or filled.
 */

/** App-registered icons (full name -> def), consulted before the bare-name set. */
/** @type {Map<string, IconDef>} */
const CUSTOM = new Map();

/**
 * Register a custom icon so `Icon(name=...)` (or an input icon slot) can use it.
 *
 * @param {string} name          The name apps will reference (any prefix or bare).
 * @param {string} d             The SVG path `d` string.
 * @param {Object} [opts]        Options.
 * @param {string} [opts.viewBox="0 0 24 24"]  The path's viewBox.
 * @param {"stroke"|"fill"} [opts.mode="stroke"]  Stroke or fill the path.
 * @returns {void}
 */
export function registerIcon(name, d, opts = {}) {
  CUSTOM.set(name, {
    d,
    viewBox: opts.viewBox ?? LUCIDE_VIEWBOX,
    mode: opts.mode ?? "stroke",
  });
}

/**
 * Resolve an icon name to its geometry, or `null` when unknown.
 *
 * @param {?string} name  The icon name (see the grammar in the module header).
 * @returns {?IconDef}    The resolved geometry, or `null`.
 */
export function resolveIcon(name) {
  if (name == null || name === "") {
    return null;
  }
  if (CUSTOM.has(name)) {
    return CUSTOM.get(name) ?? null;
  }
  if (name.startsWith("path:")) {
    return { d: name.slice(5), viewBox: LUCIDE_VIEWBOX, mode: "stroke" };
  }
  if (name.startsWith("material:")) {
    const d = MATERIAL_PATHS[name.slice(9)];
    return d ? { d, viewBox: MATERIAL_VIEWBOX, mode: "fill" } : null;
  }
  const bare = name.startsWith("lucide:") ? name.slice(7) : name;
  const d = LUCIDE_PATHS[bare];
  return d ? { d, viewBox: LUCIDE_VIEWBOX, mode: "stroke" } : null;
}

/**
 * Create an empty SVG element for an Icon node; {@link renderIcon} fills it.
 *
 * @returns {SVGSVGElement}  A fresh, namespaced `<svg>`.
 */
export function createIconSvg() {
  const svg = /** @type {SVGSVGElement} */ (document.createElementNS(SVG_NS, "svg"));
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  return svg;
}

/**
 * (Re)render an Icon's geometry into its `<svg>` from a (possibly partial) props
 * bag. The name and size are remembered on the element, so an Update patch that
 * changes only one of them keeps the other. An unknown name clears the glyph but
 * leaves the box, so layout does not jump.
 *
 * @param {SVGSVGElement} svg  The Icon's `<svg>` element.
 * @param {Object} props       Props that may include `name` and/or `size`.
 * @returns {void}
 */
export function renderIcon(svg, props) {
  if ("name" in props) {
    svg.setAttribute(DATA_NAME, props.name == null ? "" : String(props.name));
  }
  const name = svg.getAttribute(DATA_NAME);
  const def = resolveIcon(name);

  // Size: an explicit `size` wins; otherwise scale to the surrounding font
  // ("1em"), so an icon inline with text matches its size out of the box.
  if ("size" in props) {
    if (props.size == null) {
      svg.style.removeProperty("width");
      svg.style.removeProperty("height");
    } else {
      svg.style.width = `${props.size}px`;
      svg.style.height = `${props.size}px`;
    }
  } else if (!svg.style.width) {
    svg.style.width = "1em";
    svg.style.height = "1em";
  }

  while (svg.firstChild) {
    svg.removeChild(svg.firstChild);
  }
  if (def == null) {
    return;
  }
  svg.setAttribute("viewBox", def.viewBox);
  if (def.mode === "stroke") {
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
  } else {
    svg.setAttribute("fill", "currentColor");
    svg.removeAttribute("stroke");
  }
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", def.d);
  svg.appendChild(path);
}

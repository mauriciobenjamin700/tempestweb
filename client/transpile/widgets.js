// widgets.js — the Mode C widget builder surface (public import).
//
// The transpiled app module imports its widgets from here
// (`import { Button, Column, … } from "./widgets.js"`). All IR builders are
// GENERATED from tempest_core into widgets.gen.js (one per buildable core
// widget); the Style/Edge helpers live in widget-support.js. This module just
// re-exports both so the app has a single, stable import path regardless of how
// the generated set grows.
//
// Regenerate the builders: python -m tests.conformance._transpile_widgets
// Regenerate the styles:   python -m tests.conformance._transpile_widget_styles
//
// See docs/contract.md (wire format) and docs/modo-c-transpile.md (Mode C).

// widgets.gen.js already re-exports Edge/Style from widget-support.js, so a single
// star re-export gives the app every builder plus the Style/Edge helpers.
export * from "./widgets.gen.js";

// The rest of the core's value surface: enums (TextAlign, FontWeight, …), the
// non-widget wire fragments (Semantics, Border, Shadow, Gradient, …) and the
// design tokens (ACCENT, ON_SURFACE, HOVER_OPACITY, …). Generated the same way
// the builders are: python -m tests.conformance._transpile_values.
export * from "./values.gen.js";

// The ported subset of tempest_core.components: the ergonomic layout aliases plus
// the compositional components whose tree does not depend on the data they are
// handed. Each one is parity-pinned against the real core (see
// tests/fixtures/transpile_component_samples.json).
export {
  AppBar,
  Card,
  Chip,
  Divider,
  HStack,
  RadioGroup,
  Scaffold,
  SegmentedControl,
  VStack,
} from "./components.js";

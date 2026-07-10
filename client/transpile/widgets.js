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

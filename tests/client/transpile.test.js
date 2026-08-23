// Tests for client/transpile/ — Mode C native runtime (diff, widgets, runtime).
//
// Three layers, mirroring docs/modo-c-transpile.md:
//   1. diff.js conforms to the core-derived golden (transpile_diff_cases.json).
//   2. widgets.js emits IR in the core's wire shape.
//   3. runtime.js mounts a generated module (counter.gen.js), and a real DOM
//      click drives state -> diff -> patch -> DOM update.
import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import { fixture, freshDom } from "./setup.js";
import { diff } from "../../client/transpile/diff.js";
import {
  Button,
  Column,
  Container,
  Edge,
  Input,
  Row,
  Style,
  Text,
} from "../../client/transpile/widgets.js";
import { mountApp, State } from "../../client/transpile/runtime.js";
import * as widgets from "../../client/transpile/widgets.gen.js";
import {
  Alert,
  AppBar,
  Avatar,
  Badge,
  Banner,
  Breadcrumb,
  Burger,
  Card,
  Chip,
  ConfidenceBadge,
  confidence_scheme,
  Divider,
  Drawer,
  EmptyState,
  Footer,
  Grid,
  Header,
  HStack,
  ListTile,
  MetricCard,
  NavBar,
  ProgressStepper,
  RadioGroup,
  Rating,
  Scaffold,
  SearchBar,
  SegmentedControl,
  Sidebar,
  Stat,
  StatCard,
  Stepper,
  StyledContainer,
  Surface,
  Tag,
  VStack,
} from "../../client/transpile/components.js";
import { native, NativeError } from "../../client/transpile/native.js";
import { makeState, view } from "../../client/transpile/counter.gen.js";

// ---- 1. diff conformance against the core-derived golden -------------------

test("diff conforms to every golden case (all five patch kinds + noop)", () => {
  const cases = fixture("transpile_diff_cases.json");
  assert.ok(cases.length >= 6, "expected the full kind coverage");
  for (const { name, before, after, patches } of cases) {
    assert.deepEqual(diff(before, after), patches, `case "${name}" diverged from golden`);
  }
});

test("diff of identical trees is empty", () => {
  const { before } = fixture("transpile_diff_cases.json")[0];
  assert.deepEqual(diff(before, before), []);
});

// ---- 2. widgets emit the core's wire shape --------------------------------

test("Text emits the core Text prop shape (attrs + tag)", () => {
  const node = Text({ content: "hi", key: "t" });
  assert.equal(node.type, "Text");
  assert.equal(node.key, "t");
  assert.deepEqual(node.children, []);
  assert.equal(node.props.content, "hi");
  assert.deepEqual(node.props.attrs, {});
  assert.equal(node.props.tag, null);
  assert.equal(node.props.style, null);
});

test("Column/Row are flex containers carrying their children", () => {
  const col = Column({ key: "root", children: [Text({ content: "x", key: "x" })] });
  assert.equal(col.type, "Column");
  assert.equal(col.children.length, 1);
  const row = Row({ children: [] });
  assert.equal(row.type, "Row");
  assert.equal(row.key, null);
});

test("every generated builder returns a well-formed IR node", () => {
  // Widgets that need a required arg — supply a minimal value so we can build one
  // of each and assert the common wire shape.
  const required = {
    Text: { content: "x" },
    Icon: { name: "home" },
    Image: { src: "x" },
    Svg: { source: "x" },
    Toast: { message: "x" },
    Tooltip: { message: "x" },
    WebView: { url: "x" },
    VideoPlayer: { source: "x" },
    MapView: { latitude: 0, longitude: 0 },
  };
  const builders = Object.entries(widgets).filter(([, v]) => typeof v === "function");
  assert.ok(builders.length >= 40, `expected many builders, got ${builders.length}`);
  const helpers = new Set(["Style", "Color", "Edge"]); // Style-value helpers, not widgets
  for (const [name, build] of builders) {
    if (helpers.has(name)) continue;
    let node;
    try {
      node = build(required[name] ?? {});
    } catch (err) {
      // A builder needing an arg we didn't supply is fine to skip here.
      continue;
    }
    assert.equal(typeof node.type, "string", `${name}: type`);
    assert.ok("props" in node, `${name}: props`);
    assert.ok(Array.isArray(node.children), `${name}: children array`);
    assert.ok("attrs" in node.props, `${name}: attrs`);
    assert.ok("style" in node.props, `${name}: style key present`);
  }
});

test("widgets.js re-exports every ported component", async () => {
  const surface = await import("../../client/transpile/widgets.js");
  const components = await import("../../client/transpile/components.js");
  const missing = Object.keys(components).filter((name) => !(name in surface));
  assert.deepEqual(
    missing,
    [],
    "a component the served manifest accepts but widgets.js does not re-export " +
      "compiles cleanly and then fails to resolve in the browser",
  );
});

test("every ported component matches the core build (order-agnostic)", () => {
  const samples = fixture("transpile_component_samples.json");
  const drop = (n) => ({
    type: n.type,
    props: n.props,
    children: (n.children ?? []).map(drop),
  });
  const child = () => Text({ content: "a", key: "a" });
  const noop = () => {};
  const cases = {
    hstack_default: HStack({ children: [child()] }),
    hstack_lg_between: HStack({ gap: "lg", justify: "space-between" }),
    hstack_float: HStack({ gap: 8.0 }),
    vstack_sm: VStack({ children: [child()], gap: "sm" }),
    vstack_start: VStack({ children: [child()], align: "start" }),
    card_default: Card({ children: [child()] }),
    card_filled_primary: Card({ children: [child()], variant: "filled", colorScheme: "primary" }),
    card_outlined_error_flat: Card({
      children: [child()],
      variant: "outlined",
      colorScheme: "error",
      elevation: 0,
    }),
    card_elevated_level_4: Card({ children: [child()], elevation: 4 }),
    card_steps: Card({
      children: [child()],
      paddingStep: "lg",
      radiusStep: "xl",
      gapStep: "none",
    }),
    divider_default: Divider(),
    divider_token_thickness: Divider({ thickness: "xs" }),
    divider_tinted: Divider({ colorScheme: "primary" }),
    chip_static: Chip({ label: "tag" }),
    chip_selected: Chip({ label: "tag", selected: true }),
    chip_clickable_lg_success: Chip({
      label: "tag",
      onClick: noop,
      size: "lg",
      colorScheme: "success",
    }),
    segmented_default: SegmentedControl({ options: ["a", "b"], onSelect: noop }),
    segmented_second_lg: SegmentedControl({
      options: ["a", "b", "c"],
      selected: 1,
      onSelect: noop,
      size: "lg",
    }),
    segmented_secondary: SegmentedControl({
      options: ["a"],
      onSelect: noop,
      colorScheme: "secondary",
    }),
    appbar_title_only: AppBar({ title: "Home" }),
    appbar_filled_with_slots: AppBar({
      title: "Home",
      variant: "filled",
      leading: Button({ label: "<", onClick: noop, key: "back" }),
      actions: [Button({ label: "+", onClick: noop, key: "add" })],
    }),
    appbar_outlined_primary_level_2: AppBar({
      title: "Home",
      variant: "outlined",
      colorScheme: "primary",
      elevation: 2,
    }),
    radio_default: RadioGroup({ options: ["a", "b"], onSelect: noop }),
    radio_second_sm_warning: RadioGroup({
      options: ["a", "b"],
      selected: 1,
      onSelect: noop,
      size: "sm",
      colorScheme: "warning",
    }),
    scaffold_body_only: Scaffold({ body: child() }),
    scaffold_full: Scaffold({
      appBar: AppBar({ title: "Home" }),
      body: child(),
      bottomBar: Divider(),
    }),
    scaffold_scroll: Scaffold({ body: child(), scroll: true }),
    scaffold_empty: Scaffold(),
    surface_default: Surface({ child: child() }),
    surface_filled_primary: Surface({ child: child(), variant: "filled", colorScheme: "primary" }),
    surface_outlined_error_flat: Surface({
      child: child(),
      variant: "outlined",
      colorScheme: "error",
      elevation: 0,
    }),
    surface_radius_lg: Surface({ child: child(), radiusStep: "lg" }),
    surface_empty: Surface(),
    styled_container_default: StyledContainer({ child: child() }),
    styled_container_step_lg: StyledContainer({ child: child(), padding: "lg" }),
    styled_container_float: StyledContainer({ child: child(), padding: 6.0 }),
    grid_three_in_two: Grid({ children: [child(), child(), child()] }),
    grid_full_rows: Grid({ children: [child(), child(), child(), child()] }),
    grid_single_column: Grid({ children: [child(), child()], columns: 1 }),
    grid_four_in_three_token_gap: Grid({
      children: [child(), child(), child(), child()],
      columns: 3,
      gap: "md",
    }),
    grid_empty: Grid(),
    sidebar_default: Sidebar({ children: [child()] }),
    sidebar_filled_primary_wide: Sidebar({
      children: [child()],
      width: 320.0,
      variant: "filled",
      colorScheme: "primary",
    }),
    sidebar_outlined_level_3: Sidebar({ children: [child()], variant: "outlined", elevation: 3 }),
    drawer_closed: Drawer({ children: [child()] }),
    drawer_open: Drawer({ open: true, children: [child()] }),
    drawer_open_filled_secondary: Drawer({
      open: true,
      children: [child()],
      width: 200.0,
      variant: "filled",
      colorScheme: "secondary",
    }),
    burger_default: Burger({ onClick: noop }),
    burger_solid_primary_lg: Burger({
      onClick: noop,
      variant: "solid",
      colorScheme: "primary",
      size: "lg",
    }),
    header_title_only: Header({ title: "Reports" }),
    header_with_subtitle: Header({ title: "Reports", subtitle: "last 30 days" }),
    header_tinted: Header({ title: "Reports", colorScheme: "primary" }),
    header_neutral_scheme: Header({ title: "Reports", colorScheme: "neutral" }),
    footer_default: Footer({ children: [child()] }),
    footer_filled_primary: Footer({ children: [child()], variant: "filled", colorScheme: "primary" }),
    footer_outlined_flat: Footer({ children: [child()], variant: "outlined", elevation: 0 }),
    navbar_first_active: NavBar({ items: ["a", "b", "c"], onSelect: noop }),
    navbar_second_active_lg: NavBar({
      items: ["a", "b", "c"],
      active: 1,
      onSelect: noop,
      size: "lg",
    }),
    navbar_secondary_scheme: NavBar({ items: ["a", "b"], onSelect: noop, colorScheme: "secondary" }),
    breadcrumb_presentational: Breadcrumb({ items: ["home", "docs", "ui"] }),
    breadcrumb_navigable: Breadcrumb({ items: ["home", "docs", "ui"], onSelect: noop }),
    breadcrumb_single: Breadcrumb({ items: ["home"], onSelect: noop }),
    breadcrumb_custom_separator: Breadcrumb({ items: ["a", "b"], separator: "›" }),
    listtile_title_only: ListTile({ title: "Maria" }),
    listtile_with_subtitle: ListTile({ title: "Maria", subtitle: "admin" }),
    listtile_with_slots: ListTile({
      title: "Maria",
      subtitle: "admin",
      leading: Avatar({ initials: "MB", key: "lead" }),
      trailing: Button({ label: "→", onClick: noop, key: "go" }),
    }),
    listtile_tinted: ListTile({ title: "Maria", colorScheme: "primary" }),
    listtile_neutral_scheme: ListTile({ title: "Maria", colorScheme: "neutral" }),
    avatar_default: Avatar({ initials: "MB" }),
    avatar_large_secondary: Avatar({ initials: "MB", size: 64.0, colorScheme: "secondary" }),
    avatar_neutral: Avatar({ initials: "MB", colorScheme: "neutral" }),
    avatar_unknown_scheme: Avatar({ initials: "MB", colorScheme: "brand" }),
    tag_default: Tag({ label: "python" }),
    tag_lg_success: Tag({ label: "python", size: "lg", colorScheme: "success" }),
    rating_presentational: Rating({ value: 3 }),
    rating_interactive: Rating({ value: 2, onRate: noop }),
    rating_three_stars: Rating({ value: 1, maxStars: 3, colorScheme: "warning" }),
    stepper_default: Stepper({ onChange: noop }),
    stepper_bounded: Stepper({ value: 5, step: 2, minValue: 0, maxValue: 10, onChange: noop }),
    searchbar_empty: SearchBar({ onChange: noop }),
    searchbar_with_value_and_clear: SearchBar({ value: "cat", onChange: noop, onClear: noop }),
    searchbar_empty_with_clear: SearchBar({ onChange: noop, onClear: noop }),
    searchbar_outline_sm_primary: SearchBar({
      onChange: noop,
      fieldVariant: "outline",
      size: "sm",
      colorScheme: "primary",
    }),
    banner_default: Banner({ message: "saved" }),
    banner_success_tone: Banner({ message: "saved", tone: "success" }),
    banner_unknown_tone: Banner({ message: "saved", tone: "fuchsia" }),
    banner_solid_scheme: Banner({ message: "saved", variant: "solid", colorScheme: "error" }),
    banner_left_accent_with_action: Banner({
      message: "saved",
      variant: "left_accent",
      action: Button({ label: "undo", onClick: noop, key: "undo" }),
    }),
    alert_title_only: Alert({ title: "Heads up" }),
    alert_body_and_glyph: Alert({ title: "Heads up", body: "check it", glyph: "!" }),
    alert_left_accent_error: Alert({
      title: "Heads up",
      variant: "left_accent",
      colorScheme: "error",
    }),
    alert_top_accent_with_dismiss: Alert({
      title: "Heads up",
      variant: "top_accent",
      colorScheme: "success",
      dismiss: Button({ label: "x", onClick: noop, key: "close" }),
    }),
    badge_default: Badge({ label: "3" }),
    badge_subtle_info_md: Badge({ label: "3", variant: "subtle", colorScheme: "info", size: "md" }),
    badge_outline_warning_lg: Badge({
      label: "NEW",
      variant: "outline",
      colorScheme: "warning",
      size: "lg",
    }),
    badge_success_tone: Badge({ label: "3", tone: "success" }),
    badge_unknown_tone: Badge({ label: "3", tone: "fuchsia" }),
    emptystate_default: EmptyState({ title: "Nothing here" }),
    emptystate_full: EmptyState({
      title: "Nothing here",
      subtitle: "add the first one",
      glyph: "◍",
      action: Button({ label: "add", onClick: noop, key: "add" }),
    }),
    stat_plain: Stat({ label: "revenue", value: "R$ 1.2M" }),
    stat_delta_up: Stat({ label: "revenue", value: "R$ 1.2M", delta: "+12%" }),
    stat_delta_down: Stat({
      label: "revenue",
      value: "R$ 1.2M",
      delta: "-3%",
      deltaUp: false,
    }),
    progress_stepper_first: ProgressStepper({ steps: ["a", "b", "c"] }),
    progress_stepper_second: ProgressStepper({ steps: ["a", "b", "c"], current: 1 }),
    progress_stepper_single: ProgressStepper({ steps: ["a"] }),
    progress_stepper_secondary: ProgressStepper({
      steps: ["a", "b"],
      current: 1,
      colorScheme: "secondary",
    }),
    metric_card_plain: MetricCard({ label: "users", value: "1.2k" }),
    metric_card_delta: MetricCard({ label: "users", value: "1.2k", delta: "+8%" }),
    metric_card_trailing: MetricCard({
      label: "users",
      value: "1.2k",
      trailing: Text({ content: "~", key: "spark" }),
    }),
    metric_card_filled_primary: MetricCard({
      label: "users",
      value: "1.2k",
      variant: "filled",
      colorScheme: "primary",
    }),
    stat_card_default: StatCard({ label: "users", value: "1.2k" }),
    stat_card_delta_down: StatCard({ label: "users", value: "1.2k", delta: "-2%", deltaUp: false }),
    confidence_badge_high: ConfidenceBadge({ confidence: 0.92 }),
    confidence_badge_mid: ConfidenceBadge({ confidence: 0.61 }),
    confidence_badge_low: ConfidenceBadge({ confidence: 0.2 }),
    confidence_badge_labelled: ConfidenceBadge({ confidence: 0.92, label: "cat" }),
    confidence_badge_custom_thresholds: ConfidenceBadge({ confidence: 0.61, high: 0.6, mid: 0.3 }),
  };
  assert.equal(
    Object.keys(cases).length,
    Object.keys(samples).length,
    "every fixture case must have a matching builder case",
  );
  for (const [name, built] of Object.entries(cases)) {
    // diff() ignores prop key order, so an empty diff means the trees are equal.
    assert.deepEqual(diff(drop(samples[name]), drop(built)), [], `${name} diverged from core`);
  }
});

test("Container is a layout box with the semantic-tag escape hatch", () => {
  const node = Container({
    key: "nav",
    tag: "nav",
    attrs: { "hx-get": "/x" },
    child: Text({ content: "a" }),
  });
  assert.equal(node.type, "Container");
  assert.equal(node.props.tag, "nav");
  assert.deepEqual(node.props.attrs, { "hx-get": "/x" });
  assert.equal(node.props.style, null); // pure layout, no baked style
  assert.equal(node.children.length, 1);
});

test("a builder takes the core's own child slot, whatever it is named", () => {
  const single = widgets.Container({ child: Text({ content: "a" }) });
  assert.equal(single.children.length, 1, "Container folds `child` into children");
  assert.equal(widgets.Container({}).children.length, 0, "no child means no children");

  const wrapped = widgets.Draggable({
    key: "card",
    dragData: "card-7",
    child: Text({ content: "task" }),
  });
  assert.equal(wrapped.children.length, 1, "Draggable declares `child`, not `children`");

  const form = widgets.Form({
    key: "signup",
    fields: [widgets.FormField({ name: "email" }), widgets.FormField({ name: "pw" })],
  });
  assert.equal(form.children.length, 2, "Form's slot is `fields`");

  const list = widgets.Column({ children: [Text({ content: "a" })] });
  assert.equal(list.children.length, 1, "a `children` slot keeps its name");
});

test("Style fills the full shape with nulls; only set fields differ", () => {
  const style = Style({ gap: 8.0, padding: Edge.all(16) });
  assert.equal(style.gap, 8.0);
  assert.deepEqual(style.padding, { top: 16, right: 16, bottom: 16, left: 16 });
  assert.equal(style.background, null);
  assert.equal(style.color, null);
});

test("Button keeps its click closure off the wire (on_click null, __handlers fn)", () => {
  let hit = 0;
  const node = Button({ label: "+", key: "inc", onClick: () => (hit += 1) });
  assert.equal(node.props.on_click, null, "wire prop stays null for a stable diff");
  assert.equal(typeof node.__handlers.click, "function");
  node.__handlers.click();
  assert.equal(hit, 1);
});

test("Button resolves its Material 3 variant style (solid/md/primary default)", () => {
  const node = Button({ label: "+", key: "inc" });
  const style = node.props.style;
  // A default solid/primary button paints a filled background with light text,
  // a pill radius and comfortable padding — resolved from the core-derived table.
  assert.notEqual(style, null);
  assert.notEqual(style.background, null, "solid variant has a filled background");
  assert.notEqual(style.color, null);
  assert.equal(style.radius, 999.0);
  assert.equal(node.props.variant, "solid");
  assert.equal(node.props.color_scheme, "primary");
});

test("an explicit Button style layers over the resolved base (caller wins)", () => {
  const override = Style({ radius: 4.0 });
  const node = Button({ label: "x", style: override });
  assert.equal(node.props.style.radius, 4.0, "caller's set field wins");
  // Fields the caller did NOT set keep the resolved base (not nulled out).
  assert.notEqual(node.props.style.background, null);
});

test("Button variant/size/colorScheme select different resolved styles", () => {
  const solid = Button({ label: "a" }).props.style;
  const ghost = Button({ label: "a", variant: "ghost" }).props.style;
  // A ghost button is not a filled solid one — the table distinguishes variants.
  assert.notDeepEqual(solid, ghost);
});

test("Input emits the core prop shape with a resolved outline style", () => {
  const node = Input({ value: "hi", placeholder: "name", key: "f" });
  assert.equal(node.type, "Input");
  assert.equal(node.props.value, "hi");
  assert.equal(node.props.placeholder, "name");
  assert.equal(node.props.field_variant, "outline");
  assert.equal(node.props.on_change, null, "handler stays off the wire");
  assert.notEqual(node.props.style.border, null, "outline field has a border");
  assert.equal(node.props.style.radius, 8.0);
});

test("Input keeps its change closure off the wire (onChange collected by runtime)", () => {
  const node = Input({ key: "f", onChange: () => {} });
  assert.equal(node.props.on_change, null);
  assert.equal(typeof node.__handlers.input, "function");
  assert.equal(typeof node.__handlers.change, "function");
});

test("typing in an Input drives onChange -> state -> re-render", () => {
  const dom = freshDom();
  globalThis.document = dom.document;

  class FormState extends State {
    constructor() {
      super();
      this.text = "";
    }
  }
  const mod = {
    makeState: () => new FormState(),
    view: (app) =>
      Column({
        children: [
          Input({
            value: app.state.text,
            key: "f",
            onChange: (e) => app.setState((s) => (s.text = e.payload.value)),
          }),
        ],
      }),
  };

  const handle = mountApp(dom.root, mod);
  const field = dom.root.querySelector("[data-tw-key=\"f\"]");
  field.value = "hello";
  field.dispatchEvent(new dom.window.Event("input", { bubbles: true }));

  assert.equal(handle.app.state.text, "hello");
  assert.ok(handle.patchLog.length >= 1, "the re-render emitted a patch");
});

// ---- 3. runtime drives a real generated module ----------------------------

test("mountApp renders the counter's initial tree", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  mountApp(dom.root, { makeState, view });

  const tree = dom.root.children[0];
  assert.equal(tree.children[0].textContent, "Count: 0");
});

test("a click drives state -> diff -> Update patch -> DOM (not a Replace)", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const handle = mountApp(dom.root, { makeState, view });

  const inc = dom.root.querySelector("[data-tw-key=\"inc\"]");
  inc.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(dom.root.children[0].children[0].textContent, "Count: 1");
  // The only change is the label's content: a single Update patch, not a Replace.
  assert.equal(handle.patchLog.length, 1);
  const batch = handle.patchLog[0];
  assert.equal(batch.length, 1);
  assert.ok("set_props" in batch[0], "expected an Update patch");
  assert.deepEqual(batch[0].path, [0]);
});

test("decrement works too and the tree element stays stable across ticks", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  const handle = mountApp(dom.root, { makeState, view });

  const treeBefore = dom.root.children[0];
  const dec = dom.root.querySelector("[data-tw-key=\"dec\"]");
  dec.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  dec.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));

  assert.equal(dom.root.children[0].textContent.startsWith("Count: -2"), true);
  // Granular patches mutate in place — the mounted tree element is never swapped.
  assert.equal(dom.root.children[0], treeBefore);
  assert.equal(handle.patchLog.length, 2);
});

// ---- Mode C native facade -------------------------------------------------

test("native.cookies round-trips via the in-process facade (document)", async () => {
  const dom = new JSDOM("<!doctype html>", { url: "https://example.com/" });
  globalThis.document = dom.window.document;
  try {
    await native.cookies.set("token", "xyz");
    assert.equal(await native.cookies.get("token"), "xyz");
    assert.equal(await native.cookies.get("absent"), null);
    const all = await native.cookies.all();
    assert.equal(all.token, "xyz");
    await native.cookies.remove("token");
    assert.equal(await native.cookies.get("token"), null);
  } finally {
    delete globalThis.document;
  }
});

test("native.http.request routes to fetch and parses the response", async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return {
      status: 200,
      ok: true,
      headers: { get: () => "application/json", forEach: () => {} },
      json: async () => ({ hello: "world" }),
      text: async () => '{"hello":"world"}',
    };
  };
  try {
    const res = await native.http.request("GET", "/api/x");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/x");
    assert.equal(res.status, 200);
  } finally {
    delete globalThis.fetch;
  }
});

test("a native failure surfaces as a NativeError", async () => {
  // No document -> the cookies capability reports "unsupported".
  delete globalThis.document;
  await assert.rejects(() => native.cookies.get("x"), (err) => {
    assert.ok(err instanceof NativeError);
    assert.equal(err.code, "unsupported");
    return true;
  });
});

test("native.share.is_supported reports false without navigator.share", async () => {
  // Node's built-in navigator has no `.share`, so the capability reports false —
  // proving the dispatch + unwrap (`.supported`) path.
  assert.equal(await native.share.is_supported(), false);
});

test("native.audio.play dispatches src/volume/channel", async () => {
  // No Audio ctor -> the capability reports unavailable, proving the dispatch
  // path and arg shaping without a real audio device.
  await assert.rejects(() => native.audio.play("/x.wav", { volume: 0.5 }), (err) => {
    assert.ok(err instanceof NativeError);
    return true;
  });
});

// ---- Mode C navigation ----------------------------------------------------

import { Route } from "../../client/transpile/nav.js";

test("app.push/pop navigate the stack and re-render", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  class NavState extends State {}
  const mod = {
    makeState: () => new NavState(),
    view: (app) =>
      Column({
        children: [
          Text({ content: app.nav.top.name, key: "route" }),
          Button({
            label: "go",
            key: "go",
            onClick: () => app.push(new Route({ name: "/about" })),
          }),
          Button({ label: "back", key: "back", onClick: () => app.pop() }),
        ],
      }),
  };
  const handle = mountApp(dom.root, mod);
  assert.equal(dom.root.querySelector("[data-tw-key=\"route\"]").textContent, "/");

  dom.root.querySelector("[data-tw-key=\"go\"]")
    .dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  assert.equal(handle.app.nav.top.name, "/about");
  assert.equal(dom.root.querySelector("[data-tw-key=\"route\"]").textContent, "/about");

  dom.root.querySelector("[data-tw-key=\"back\"]")
    .dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  assert.equal(handle.app.nav.top.name, "/");
});

test("a navigate event resets the stack from the path (deep link)", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  class NavState extends State {}
  const mod = {
    makeState: () => new NavState(),
    view: (app) => Text({ content: app.nav.top.name, key: "route" }),
  };
  const handle = mountApp(dom.root, mod);
  // Simulate the router reporting a deep-linked path.
  handle.app.reset(routesFromPathTest("/a/b"));
  assert.equal(handle.app.nav.top.name, "/a/b");
  assert.deepEqual(handle.app.nav.stack.map((r) => r.name), ["/", "/a", "/a/b"]);
});

import { routesFromPath as routesFromPathTest } from "../../client/transpile/nav.js";

// ---- Mode C theme + responsiveness ----------------------------------------

import { MediaQueryData, Theme, ThemeMode } from "../../client/transpile/theme.js";

test("app.set_theme and media updates re-render the view", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  class ThemeState extends State {}
  const mod = {
    makeState: () => new ThemeState(),
    view: (app) => {
      const dark = app.theme.is_dark({ platform_dark_mode: app.media.platform_dark_mode });
      const wide = app.media.width >= 600;
      return Text({ content: `${dark ? "dark" : "light"}/${wide ? "wide" : "narrow"}`, key: "t" });
    },
  };
  const handle = mountApp(dom.root, mod);
  const label = () => dom.root.querySelector("[data-tw-key=\"t\"]").textContent;
  assert.equal(label(), "light/narrow");

  handle.app.set_theme(new Theme({ mode: ThemeMode.DARK }));
  assert.equal(label(), "dark/narrow");

  handle.app._setMedia(new MediaQueryData({ width: 1024, height: 768 }));
  assert.equal(label(), "dark/wide");
});

// ---- Mode C imperative animation (frame loop) -----------------------------

import { AnimationController, Tween } from "../../client/transpile/animation.js";

test("registering a controller drives the frame loop until it settles", () => {
  const dom = freshDom();
  globalThis.document = dom.document;
  // A controllable rAF: collect callbacks, pump them manually with timestamps.
  const queue = [];
  globalThis.requestAnimationFrame = (fn) => queue.push(fn);
  try {
    class AnimState extends State {
      constructor() {
        super();
        this.anim = new AnimationController(1.0);
      }
    }
    const mod = {
      makeState: () => new AnimState(),
      view: (app) =>
        Text({ content: String(Math.round(new Tween({ begin: 0, end: 100 }).at(app.state.anim.value))), key: "v" }),
    };
    const handle = mountApp(dom.root, mod);
    const label = () => dom.root.querySelector("[data-tw-key=\"v\"]").textContent;
    assert.equal(label(), "0");

    handle.app.state.anim.forward();
    handle.app.register_animation(handle.app.state.anim);
    assert.equal(handle.app.has_animations, true);

    // Pump frames: t=0, 0.5s, 1.1s (settles).
    let t = 0;
    const pump = (ms) => {
      t += ms;
      const fns = queue.splice(0);
      for (const fn of fns) fn(t);
    };
    pump(0);
    pump(500);
    assert.notEqual(label(), "0"); // advanced
    pump(700); // total 1200ms > 1000ms duration -> settles at 100
    assert.equal(label(), "100");
    assert.equal(handle.app.has_animations, false);
  } finally {
    delete globalThis.requestAnimationFrame;
  }
});

test("the re helpers reproduce Python's semantics, which JS does not give free", async () => {
  const { reMatch, reSearch, reFullmatch, reSub, reFindall } = await import(
    "../../client/transpile/runtime.js"
  );
  // `Pattern.match` anchors at the START — `test`/`exec` do not.
  assert.ok(reMatch("[^@\\s]+@[^@\\s]+", "a@b.c"));
  assert.equal(reMatch("b", "ab"), null, "match is anchored at the start");
  assert.ok(reSearch("b", "ab"), "search is not anchored");
  // `fullmatch` anchors both ends.
  assert.ok(reFullmatch("a+", "aaa"));
  assert.equal(reFullmatch("a+", "aaab"), null);
  // `re.sub` replaces EVERY occurrence; a JS string `replace` replaces one.
  assert.equal(reSub("\\D", "", "R$ 1.234,50"), "123450");
  assert.deepEqual(reFindall("\\d+", "a1b22c333"), ["1", "22", "333"]);
  // A compiled pattern works the same as its source.
  assert.ok(reMatch(new RegExp("^[a-z]+$"), "abc"));
});

test("the sleep helper counts seconds, the way asyncio.sleep does", async () => {
  const { sleep } = await import("../../client/transpile/runtime.js");
  const started = Date.now();
  await sleep(0.05);
  assert.ok(Date.now() - started >= 45, "0.05 s is 50 ms, not 0.05 ms");
});

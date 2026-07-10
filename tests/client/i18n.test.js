// Tests for client/transpile/i18n.js — parity with tempest_core.i18n.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import { Locale, t, translate } from "../../client/transpile/i18n.js";

test("translate matches the core for every fixture case", () => {
  const { table, cases } = fixture("transpile_i18n_cases.json");
  for (const { language, key, params, expected } of cases) {
    const got = translate(key, {
      locale: new Locale({ language }),
      translations: table,
      ...params,
    });
    assert.equal(got, expected, `${language}/${key}`);
  }
});

test("t is an alias of translate and interpolates", () => {
  const table = { pt: { hi: "Olá, {name}" } };
  const loc = new Locale({ language: "pt" });
  assert.equal(t("hi", { locale: loc, translations: table, name: "Ana" }), "Olá, Ana");
});

test("a missing key degrades to the key itself", () => {
  const loc = new Locale({ language: "pt" });
  assert.equal(translate("nope", { locale: loc, translations: {} }), "nope");
});

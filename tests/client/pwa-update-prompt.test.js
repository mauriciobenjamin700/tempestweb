// Tests for client/pwa/update-prompt.js — P1 "new version available" banner.
import { test } from "node:test";
import assert from "node:assert/strict";
import { JSDOM } from "jsdom";
import {
  UPDATE_BANNER_ID,
  createUpdateBanner,
  showUpdatePrompt,
} from "../../client/pwa/update-prompt.js";

/** A jsdom document with an empty body. */
function freshDoc() {
  return new JSDOM("<!doctype html><body></body>").window.document;
}

test("createUpdateBanner builds a labelled banner with a button", () => {
  const doc = freshDoc();
  const banner = createUpdateBanner(doc, {
    message: "Nova versão",
    buttonLabel: "Atualizar",
  });
  assert.equal(banner.id, UPDATE_BANNER_ID);
  assert.match(banner.textContent, /Nova versão/);
  const button = banner.querySelector("button");
  assert.ok(button, "has a button");
  assert.equal(button.textContent, "Atualizar");
});

test("createUpdateBanner button click invokes onApply", () => {
  const doc = freshDoc();
  let applied = 0;
  const banner = createUpdateBanner(doc, { onApply: () => (applied += 1) });
  banner.querySelector("button").click();
  assert.equal(applied, 1);
});

test("showUpdatePrompt attaches the banner and wires skipWaiting", () => {
  const doc = freshDoc();
  const calls = [];
  const registration = { waiting: {} };
  const banner = showUpdatePrompt(registration, {
    document: doc,
    skipWaiting: (reg) => calls.push(reg),
    buttonLabel: "Reload",
  });
  assert.ok(banner, "returns the banner");
  assert.equal(doc.getElementById(UPDATE_BANNER_ID), banner, "attached to the DOM");
  banner.querySelector("button").click();
  assert.deepEqual(calls, [registration], "click activates the waiting worker");
});

test("showUpdatePrompt is idempotent (no duplicate banner)", () => {
  const doc = freshDoc();
  const registration = { waiting: {} };
  const first = showUpdatePrompt(registration, { document: doc, skipWaiting() {} });
  const second = showUpdatePrompt(registration, { document: doc, skipWaiting() {} });
  assert.equal(first, second, "returns the existing banner");
  assert.equal(doc.querySelectorAll(`#${UPDATE_BANNER_ID}`).length, 1);
});

test("showUpdatePrompt returns null without a document body", () => {
  assert.equal(showUpdatePrompt({ waiting: {} }, { document: null }), null);
});

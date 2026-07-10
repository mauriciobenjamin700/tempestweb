// Tests for client/transpile/validators.js — parity with tempest_core.validators.
//
// The JS validators are a port of the core's; this asserts they return the exact
// same message (or null) the core does, for a battery of core-derived inputs
// (tests/fixtures/transpile_validator_cases.json).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fixture } from "./setup.js";
import {
  validate_cnpj,
  validate_cpf,
  validate_email,
  validate_phone,
} from "../../client/transpile/validators.js";

const FNS = {
  validate_cpf,
  validate_cnpj,
  validate_email,
  validate_phone,
};

test("JS validators match the core for every fixture case", () => {
  const cases = fixture("transpile_validator_cases.json");
  assert.ok(cases.length >= 15, "expected a battery of cases");
  for (const { validator, input, expected } of cases) {
    const got = FNS[validator](input);
    // JSON null in the fixture maps to JS null.
    assert.equal(got, expected, `${validator}(${JSON.stringify(input)})`);
  }
});

test("a valid CPF and a valid email return null", () => {
  assert.equal(validate_cpf("529.982.247-25"), null);
  assert.equal(validate_email("user@domain.com"), null);
});

test("an invalid CPF reports the PT-BR message", () => {
  assert.equal(validate_cpf("111.111.111-11"), "CPF inválido");
  assert.equal(validate_cpf("123"), "CPF deve ter 11 dígitos");
});

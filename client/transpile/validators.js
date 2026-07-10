// validators.js — Mode C field validators (a faithful port of tempest_core.validators).
//
// Pure, dependency-free BR form validators, mirroring
// tempest_core/validators.py exactly (same algorithms, same PT-BR messages).
// Each returns a PT-BR error string when the value is invalid, or null when
// valid — the `Callable[[Any], str | None]` shape the core uses. The transpiler
// routes `from tempest_core.validators import validate_cpf, …` to this module, so
// a transpiled Mode C form validates client-side with no Python.
//
// Parity is locked by a core-derived fixture (tests/fixtures/
// transpile_validator_cases.json) and a JS test — see docs/native-modo-c.md.

/** A pragmatic email pattern: local part, `@`, dotted domain with a 2+ TLD. */
export const EMAIL_PATTERN = "[^@\\s]+@[^@\\s]+\\.[^@\\s]{2,}";

const _EMAIL_RE = new RegExp(`^${EMAIL_PATTERN}$`);

/**
 * Strip every non-digit character from a value's string form.
 * @param {*} value  The raw value (coerced via String).
 * @returns {string}  The value's digits, in order.
 */
function onlyDigits(value) {
  return String(value).replace(/\D/g, "");
}

/**
 * Report whether every character of `digits` is identical (and non-empty).
 * @param {string} digits
 * @returns {boolean}
 */
function allSame(digits) {
  return digits.length > 0 && digits === digits[0].repeat(digits.length);
}

/**
 * Validate a Brazilian CPF (11 digits, not all-same, two mod-11 check digits).
 * @param {*} value  The raw CPF (masked or bare).
 * @returns {?string}  A PT-BR error message, or null when valid.
 */
export function validate_cpf(value) {
  const digits = onlyDigits(value);
  if (digits.length !== 11) {
    return "CPF deve ter 11 dígitos";
  }
  if (allSame(digits)) {
    return "CPF inválido";
  }
  const numbers = digits.split("").map(Number);
  for (const position of [9, 10]) {
    let weighted = 0;
    for (let index = 0; index < position; index += 1) {
      weighted += numbers[index] * (position + 1 - index);
    }
    const remainder = (weighted * 10) % 11;
    const check = remainder === 10 ? 0 : remainder;
    if (check !== numbers[position]) {
      return "CPF inválido";
    }
  }
  return null;
}

/**
 * Validate a Brazilian CNPJ (14 digits, not all-same, two check digits).
 * @param {*} value  The raw CNPJ (masked or bare).
 * @returns {?string}  A PT-BR error message, or null when valid.
 */
export function validate_cnpj(value) {
  const digits = onlyDigits(value);
  if (digits.length !== 14) {
    return "CNPJ deve ter 14 dígitos";
  }
  if (allSame(digits)) {
    return "CNPJ inválido";
  }
  const numbers = digits.split("").map(Number);
  const firstWeights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const secondWeights = [6, ...firstWeights];
  for (const [weights, position] of [[firstWeights, 12], [secondWeights, 13]]) {
    let weighted = 0;
    for (let index = 0; index < position; index += 1) {
      weighted += numbers[index] * weights[index];
    }
    const remainder = weighted % 11;
    const check = remainder < 2 ? 0 : 11 - remainder;
    if (check !== numbers[position]) {
      return "CNPJ inválido";
    }
  }
  return null;
}

/**
 * Validate an email address with the pragmatic {@link EMAIL_PATTERN}.
 * @param {*} value  The raw email address.
 * @returns {?string}  A PT-BR error message, or null when valid.
 */
export function validate_email(value) {
  const text = String(value).trim();
  return _EMAIL_RE.test(text) ? null : "E-mail inválido";
}

/**
 * Validate a Brazilian phone (10 digits landline, or 11 digits mobile).
 * @param {*} value  The raw phone (masked or bare).
 * @returns {?string}  A PT-BR error message, or null when valid.
 */
export function validate_phone(value) {
  const digits = onlyDigits(value);
  return digits.length === 10 || digits.length === 11 ? null : "Telefone inválido";
}

import test from "node:test";
import assert from "node:assert/strict";

import { getRoleFromClaims } from "./authRoles.js";

test("accepts exactly one supported application role", () => {
  assert.equal(getRoleFromClaims({ roles: ["analista"] }), "analista");
});

test("reports a missing role clearly", () => {
  assert.throws(
    () => getRoleFromClaims({ roles: [] }),
    /no tiene un rol asignado/i,
  );
});

test("rejects multiple roles", () => {
  assert.throws(
    () => getRoleFromClaims({ roles: ["analista", "gerente"] }),
    /más de un rol/i,
  );
});

test("rejects unsupported roles", () => {
  assert.throws(
    () => getRoleFromClaims({ roles: ["administrador"] }),
    /no está autorizado/i,
  );
});

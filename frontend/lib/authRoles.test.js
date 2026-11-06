import test from "node:test";
import assert from "node:assert/strict";

import { isSupportedRole, OPERATIONAL_ROLES } from "./authRoles.js";

test("lists the five operational roles without granting admin through registration", () => {
  assert.deepEqual(OPERATIONAL_ROLES, [
    "directivo",
    "analista",
    "gerente",
    "bodega",
    "ti",
  ]);
});

test("recognizes admin only as a dashboard role, not an operational agent", () => {
  assert.equal(isSupportedRole("admin"), true);
  assert.equal(OPERATIONAL_ROLES.includes("admin"), false);
});

test("rejects unsupported role values", () => {
  assert.equal(isSupportedRole("administrator"), false);
  assert.equal(isSupportedRole(null), false);
});

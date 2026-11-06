import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  BRANCH_OPTIONS,
  formatBranchNames,
  getSelectedBranches,
} from "./branches.js";

test("public registration only allows one of the five named branches", () => {
  assert.deepEqual(
    BRANCH_OPTIONS.map(({ value }) => value),
    ["guadalajara", "zapopan", "leon", "queretaro", "aguascalientes"],
  );
  assert.equal(BRANCH_OPTIONS.some(({ value }) => value === "all"), false);
});

test("admin multi-select returns named branches in canonical order", () => {
  assert.deepEqual(
    getSelectedBranches([
      { value: "leon" },
      { value: "guadalajara" },
      { value: "zapopan" },
    ]),
    ["guadalajara", "zapopan", "leon"],
  );
});

test("chat selection is limited to the assigned branches", () => {
  assert.deepEqual(
    getSelectedBranches(
      [{ value: "leon" }, { value: "zapopan" }],
      ["leon"],
    ),
    ["leon"],
  );
});

test("branch labels keep the selected result set classified", () => {
  assert.equal(formatBranchNames(["leon", "zapopan"]), "León, Zapopan");
});

test("admin interface posts a multi-select branch list", () => {
  const adminComponent = readFileSync(
    new URL("../components/AdminUserManagement.jsx", import.meta.url),
    "utf8",
  );
  assert.match(adminComponent, /import BranchMultiSelect/);
  assert.match(adminComponent, /onChange=\{\(branches\)/);
  assert.match(adminComponent, /branches: selectedBranches\[user\.id\]/);

  const branchSelector = readFileSync(
    new URL("../components/BranchMultiSelect.jsx", import.meta.url),
    "utf8",
  );
  assert.match(branchSelector, /type="checkbox"/);
  assert.match(branchSelector, /onChange=\{\(event\) => toggleBranch/);
});

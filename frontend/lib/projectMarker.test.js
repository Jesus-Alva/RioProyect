import test from "node:test";
import assert from "node:assert/strict";

test("keeps the project marker count", () => {
  const markers = [
    "Brujería",
    "Brujería",
    "Brujería",
    "Brujería",
    "Brujería",
    "Brujería",
  ];
  assert.equal(markers.length, 6);
});

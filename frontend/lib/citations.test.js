import test from "node:test";
import assert from "node:assert/strict";

import { extractCitations } from "./citations.js";

const citation = (reference) =>
  `${String.fromCodePoint(0x3010)}${reference}${String.fromCodePoint(0x3011)}`;

test("extracts citation markers and retains surrounding answer text", () => {
  const source = citation(`4:0${String.fromCodePoint(0x2020)}source`);

  assert.deepEqual(
    extractCitations(`Total de la factura: 120. ${source}`),
    {
      answer: "Total de la factura: 120.",
      citations: [source],
    },
  );
});

test("preserves line breaks when a response contains more than one citation", () => {
  const firstSource = citation(`4:0${String.fromCodePoint(0x2020)}source`);
  const secondSource = citation(`5:1${String.fromCodePoint(0x2020)}source`);

  assert.deepEqual(
    extractCitations(`Resumen\nPrimera fuente ${firstSource}\nSegunda ${secondSource}`),
    {
      answer: "Resumen\nPrimera fuente \nSegunda",
      citations: [firstSource, secondSource],
    },
  );
});

test("returns an uncited answer unchanged except for outer whitespace", () => {
  assert.deepEqual(extractCitations("  Hola\nmundo  "), {
    answer: "Hola\nmundo",
    citations: [],
  });
});

const CITATION_PATTERN = /【[^】]+】/g;

export function extractCitations(text) {
  const citations = [...text.matchAll(CITATION_PATTERN)].map(([citation]) => citation);
  const answer = text.replace(CITATION_PATTERN, "").trim();

  return { answer, citations };
}

/**
 * Parse rubric text, one item per line:
 *   Point | keywords | expected meaning | marks      (or: Point | keywords | marks)
 */
export function parseRubric(text) {
  const lines = text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) throw new Error("Add at least one rubric point.");

  return lines.map((line, index) => {
    const parts = line.split("|").map((part) => part.trim());

    if (parts.length !== 3 && parts.length !== 4) {
      throw new Error(
        `Rubric line ${index + 1} must use: Point | keywords | expected meaning | marks`
      );
    }

    const point = parts[0];
    const keywordsText = parts[1];
    const semanticReference = parts.length === 4 ? parts[2] : "";
    const marks = Number(parts[parts.length - 1]);

    if (!point || !keywordsText || !Number.isFinite(marks) || marks <= 0) {
      throw new Error(`Rubric line ${index + 1} is invalid.`);
    }

    return {
      point,
      keywords: keywordsText.split(",").map((k) => k.trim()).filter(Boolean),
      semantic_reference: semanticReference,
      marks,
    };
  });
}

const RUBRIC_STOP_WORDS = new Set([
  "about", "after", "also", "and", "are", "because", "been", "being", "between",
  "but", "can", "could", "does", "during", "each", "for", "from", "has", "have",
  "into", "its", "may", "more", "most", "not", "of", "on", "one", "onto", "or",
  "our", "should", "some", "such", "than", "that", "the", "their", "them", "then",
  "there", "these", "this", "those", "through", "to", "use", "used", "using", "was",
  "were", "which", "while", "will", "with", "would",
]);

export function generateRubricFromAnswer(answer, totalMarks = 5) {
  const sentences = answer
    .split(/\r?\n+/)
    .flatMap((line) => line.split(/(?<=[.!?])\s+/))
    .map((sentence) => sentence.replace(/^\s*(?:[-*]|\d+[.)])\s*/, "").replace(/\|/g, " ").trim())
    .filter(Boolean)
    .slice(0, 50);

  if (!sentences.length) return "";

  const normalizedTotal = Math.round(Number(totalMarks) * 100) / 100;
  if (!Number.isFinite(normalizedTotal) || normalizedTotal <= 0 || normalizedTotal > 1000) {
    throw new Error("Total marks must be between 0 and 1000.");
  }

  const markPerPoint = Math.floor((normalizedTotal / sentences.length) * 100) / 100;

  return sentences.map((sentence, index) => {
    const keywords = [...new Set(
      (sentence.toLowerCase().match(/[a-z0-9]+(?:['-][a-z0-9]+)*/g) || [])
        .filter((word) => word.length > 2 && !RUBRIC_STOP_WORDS.has(word))
    )].slice(0, 4);
    const fallback = sentence.match(/[a-z0-9]+/i)?.[0] || "answer";
    const point = sentence.slice(0, 300);
    const reference = sentence.slice(0, 1000);
    const marks = index === sentences.length - 1
      ? Number((normalizedTotal - markPerPoint * index).toFixed(2))
      : markPerPoint;

    return `${point} | ${(keywords.length ? keywords : [fallback]).join(", ")} | ${reference} | ${marks}`;
  }).join("\n");
}

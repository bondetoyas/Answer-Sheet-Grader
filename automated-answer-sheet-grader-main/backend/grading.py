"""Pure grading logic (no web framework imports) so it is easy to test."""

import re
from typing import Callable, Optional, Sequence

LOW_CONFIDENCE_THRESHOLD = 60
SEMANTIC_MATCH_THRESHOLD = 0.60

# (student_answer, references) -> list of cosine similarities, or None if unavailable
SimilarityFn = Callable[[str, Sequence[str]], Optional[list]]


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def keyword_in_text(keyword: str, cleaned_text: str) -> bool:
    """Whole-word / whole-phrase match, so 'carbon' does not match 'carbonate'."""
    cleaned_keyword = clean_text(keyword)
    if not cleaned_keyword:
        return False
    return f" {cleaned_keyword} " in f" {cleaned_text} "


def grade(rubric: Sequence[dict], student_answer: str,
          similarity_fn: Optional[SimilarityFn] = None) -> dict:
    """Grade an answer. Each rubric item: point, keywords, semantic_reference, marks."""
    cleaned = clean_text(student_answer)

    semantic_scores = None
    if similarity_fn is not None and student_answer.strip():
        references = [item.get("semantic_reference") or "" for item in rubric]
        if any(r.strip() for r in references):
            semantic_scores = similarity_fn(student_answer, references)

    score = 0.0
    total_marks = 0.0
    breakdown = []

    for index, item in enumerate(rubric):
        marks = float(item["marks"])
        total_marks += marks

        matched_keywords = [
            kw for kw in item.get("keywords", []) if keyword_in_text(kw, cleaned)
        ]
        keyword_matched = bool(matched_keywords)

        similarity = None
        semantic_matched = False
        reference = (item.get("semantic_reference") or "").strip()
        if semantic_scores is not None and reference:
            similarity = float(semantic_scores[index])
            semantic_matched = similarity >= SEMANTIC_MATCH_THRESHOLD

        matched = keyword_matched or semantic_matched
        awarded = marks if matched else 0.0
        score += awarded

        if keyword_matched and semantic_matched:
            method = "Keyword and semantic match"
        elif keyword_matched:
            method = "Keyword match"
        elif semantic_matched:
            method = "Semantic match"
        else:
            method = "No match"

        breakdown.append({
            "point": item["point"],
            "marks": marks,
            "awarded_marks": awarded,
            "matched": matched,
            "matched_keywords": matched_keywords,
            "semantic_similarity": None if similarity is None else round(similarity * 100, 1),
            "match_method": method,
        })

    coverage = round(score / total_marks * 100, 1) if total_marks else 0.0
    needs_review = coverage < LOW_CONFIDENCE_THRESHOLD

    return {
        "score": round(score, 1),
        "max_marks": round(total_marks, 1),
        "confidence": coverage,
        "needs_review": needs_review,
        "review_reason": (
            "Low rubric coverage. Teacher review is required."
            if needs_review else "Rubric coverage is acceptable."
        ),
        "semantic_available": semantic_scores is not None,
        "rubric_breakdown": breakdown,
    }


_MARKER = re.compile(
    r"^[ \t]*(?:(?:question|ques|qn|q|answer|ans)[ \t]*\.?[ \t]*(\d{1,3})[ \t]*[.):\-]?"
    r"|(\d{1,3})[ \t]*[.)])[ \t]*",
    re.IGNORECASE | re.MULTILINE,
)


def split_sections(text: str) -> list:
    """Split OCR text into per-question answers using markers like 'Q1.', 'Ans 2:', '3)'.

    Returns [] unless at least two markers are found, so single answers stay untouched.
    """
    matches = list(_MARKER.finditer(text))
    if len(matches) < 2:
        return []

    sections = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end].strip()
        number = match.group(1) or match.group(2)
        if body:
            sections.append({"label": f"Q{int(number)}", "text": body})
    return sections if len(sections) >= 2 else []

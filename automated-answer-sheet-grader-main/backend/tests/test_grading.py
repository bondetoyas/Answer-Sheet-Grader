import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grading import grade, keyword_in_text, clean_text  # noqa: E402

RUBRIC = [
    {"point": "Uses sunlight", "keywords": ["sunlight"], "semantic_reference": "Plants use sunlight", "marks": 1},
    {"point": "Uses water", "keywords": ["water"], "semantic_reference": "Plants need water", "marks": 1},
    {"point": "Uses CO2", "keywords": ["carbon dioxide", "carbon"], "semantic_reference": "", "marks": 1},
    {"point": "Makes glucose", "keywords": ["glucose", "food"], "semantic_reference": "", "marks": 1},
    {"point": "Releases oxygen", "keywords": ["oxygen"], "semantic_reference": "", "marks": 1},
]


class GradingTests(unittest.TestCase):
    def test_all_rubric_items_are_scored(self):
        # Regression: the old loop only scored the last rubric item.
        r = grade(RUBRIC, "Plants use sunlight and water and carbon dioxide to make glucose and release oxygen.")
        self.assertEqual(r["score"], 5)
        self.assertEqual(r["max_marks"], 5)
        self.assertEqual(len(r["rubric_breakdown"]), 5)
        self.assertFalse(r["needs_review"])

    def test_partial_score(self):
        r = grade(RUBRIC, "It needs water and sunlight.")
        self.assertEqual(r["score"], 2)
        self.assertEqual(r["confidence"], 40.0)
        self.assertTrue(r["needs_review"])

    def test_empty_answer_scores_zero(self):
        r = grade(RUBRIC, "")
        self.assertEqual(r["score"], 0)
        self.assertEqual(r["max_marks"], 5)

    def test_whole_word_matching(self):
        self.assertFalse(keyword_in_text("carbon", clean_text("calcium carbonate")))
        self.assertTrue(keyword_in_text("carbon dioxide", clean_text("Carbon-Dioxide!")))

    def test_without_semantic_is_keyword_only(self):
        r = grade(RUBRIC, "sunlight", similarity_fn=lambda a, refs: None)
        self.assertFalse(r["semantic_available"])
        self.assertIsNone(r["rubric_breakdown"][0]["semantic_similarity"])
        self.assertEqual(r["rubric_breakdown"][0]["match_method"], "Keyword match")

    def test_semantic_match_awards_marks(self):
        sims = lambda a, refs: [0.9, 0.1, 0.0, 0.0, 0.0]  # noqa: E731
        r = grade(RUBRIC, "the sun's light powers it", similarity_fn=sims)
        first = r["rubric_breakdown"][0]
        self.assertEqual(first["match_method"], "Semantic match")
        self.assertEqual(first["awarded_marks"], 1)
        self.assertEqual(first["semantic_similarity"], 90.0)
        self.assertEqual(r["score"], 1)

    def test_both_methods(self):
        sims = lambda a, refs: [0.8] + [0.0] * 4  # noqa: E731
        r = grade(RUBRIC, "sunlight", similarity_fn=sims)
        self.assertEqual(r["rubric_breakdown"][0]["match_method"], "Keyword and semantic match")


if __name__ == "__main__":
    unittest.main()


class SplitTests(unittest.TestCase):
    def test_splits_numbered_answers(self):
        from grading import split_sections
        text = "Q1. Plants use sunlight.\nthey also need water\nQ2) Oxygen is released.\nAns 3: Glucose is made."
        s = split_sections(text)
        self.assertEqual([x["label"] for x in s], ["Q1", "Q2", "Q3"])
        self.assertEqual(s[0]["text"], "Plants use sunlight.\nthey also need water")
        self.assertEqual(s[2]["text"], "Glucose is made.")

    def test_plain_number_markers(self):
        from grading import split_sections
        self.assertEqual(len(split_sections("1. first answer\n2. second answer")), 2)

    def test_single_answer_not_split(self):
        from grading import split_sections
        self.assertEqual(split_sections("Q1. only one answer here"), [])
        self.assertEqual(split_sections("Plants make 2 things. 3 apples"), [])
        self.assertEqual(split_sections(""), [])

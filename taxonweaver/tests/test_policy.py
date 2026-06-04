"""Unit checks for centralized resolver status policy."""

from __future__ import annotations

import unittest

from taxonomy_resolver.policy import (
    ResolutionStatus,
    WarningCode,
    allows_auto_accept,
    apply_level_conflict_policy,
    classify_fuzzy_status,
    requires_review,
)


class PolicyTests(unittest.TestCase):
    """Verify the explicit status and warning policy helpers."""

    def test_level_conflict_promotes_status_and_warning(self) -> None:
        status, warnings = apply_level_conflict_policy(
            ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC,
            [],
            provided_level="genus",
            matched_rank="species",
        )

        self.assertEqual(status, ResolutionStatus.LEVEL_CONFLICT)
        self.assertIn(WarningCode.PROVIDED_LEVEL_CONFLICT, warnings)

    def test_matching_levels_leave_status_unchanged(self) -> None:
        status, warnings = apply_level_conflict_policy(
            ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC,
            [],
            provided_level="species",
            matched_rank="species",
        )

        self.assertEqual(status, ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC)
        self.assertEqual(warnings, [])

    def test_fuzzy_status_classification(self) -> None:
        self.assertEqual(
            classify_fuzzy_status(1),
            (ResolutionStatus.SUGGESTED_FUZZY_UNIQUE, []),
        )
        self.assertEqual(
            classify_fuzzy_status(2),
            (
                ResolutionStatus.AMBIGUOUS_FUZZY_MULTIPLE,
                [WarningCode.MULTIPLE_FUZZY_CANDIDATES],
            ),
        )
        self.assertEqual(
            classify_fuzzy_status(0),
            (ResolutionStatus.UNRESOLVED_NO_MATCH, []),
        )

    def test_review_and_auto_accept_policy_sets(self) -> None:
        self.assertTrue(requires_review(ResolutionStatus.LEVEL_CONFLICT))
        self.assertTrue(requires_review(ResolutionStatus.UNRESOLVED_NO_MATCH))
        self.assertFalse(requires_review(ResolutionStatus.RESOLVED_EXACT_SCIENTIFIC))
        self.assertTrue(allows_auto_accept(ResolutionStatus.RESOLVED_EXACT_SYNONYM))
        self.assertFalse(allows_auto_accept(ResolutionStatus.AMBIGUOUS_FUZZY_MULTIPLE))


if __name__ == "__main__":
    unittest.main()

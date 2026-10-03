"""
Automated tests for Independent Quantitative Auditor.
"""

import unittest
from idx.audit import run_comprehensive_audit


class TestIndependentAudit(unittest.TestCase):
    def test_run_comprehensive_audit(self):
        report = run_comprehensive_audit()
        self.assertIn("status", report)
        self.assertIn("invariants", report)
        self.assertIn("summary", report)
        
        # Verify invariants exist
        invariants = report["invariants"]
        self.assertIn("balance_sheet_identity", invariants)
        self.assertIn("der_consistency", invariants)
        self.assertIn("shareholder_ownership", invariants)
        self.assertIn("dividend_yield", invariants)
        self.assertIn("anti_trap_protection", invariants)
        
        # Invariants must pass with 0 defects
        self.assertEqual(invariants["balance_sheet_identity"]["status"], "PASSED")
        self.assertEqual(invariants["shareholder_ownership"]["status"], "PASSED")
        self.assertEqual(invariants["dividend_yield"]["status"], "PASSED")
        self.assertEqual(invariants["anti_trap_protection"]["status"], "PASSED")
        self.assertEqual(report["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()

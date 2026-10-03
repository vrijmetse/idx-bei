"""
Tests for Sharia compliance engine.
"""

import unittest
from idx.core.sharia import get_sharia_status_map, get_non_sharia_tickers


class TestShariaCompliance(unittest.TestCase):
    def test_conventional_banks_excluded(self):
        non_sharia = get_non_sharia_tickers()
        # Conventional banks must NEVER be in Sharia
        self.assertIn("BBCA", non_sharia)
        self.assertIn("BMRI", non_sharia)
        self.assertIn("BBRI", non_sharia)
        self.assertIn("BBNI", non_sharia)
        self.assertIn("BDMN", non_sharia)
        
        # Alcohol must NEVER be in Sharia
        self.assertIn("MLBI", non_sharia)
        self.assertIn("DLTA", non_sharia)

    def test_sharia_banks_and_compounders_included(self):
        sharia_map = get_sharia_status_map()
        # Sharia bank BRIS must be Sharia
        self.assertTrue(sharia_map.get("BRIS", False))
        # Non-financial compounders must be Sharia
        self.assertTrue(sharia_map.get("TLKM", False))
        self.assertTrue(sharia_map.get("ASII", False))
        self.assertTrue(sharia_map.get("UNVR", False))
        self.assertTrue(sharia_map.get("ICBP", False))

        # Conventional bank BBCA must NOT be Sharia
        self.assertFalse(sharia_map.get("BBCA", True))


if __name__ == "__main__":
    unittest.main()

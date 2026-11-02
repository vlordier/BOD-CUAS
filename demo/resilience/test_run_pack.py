import unittest

from run_pack import run


class ResiliencePackTests(unittest.TestCase):
    def test_all_five_scenarios_execute_with_expected_invariants(self):
        report = run()
        self.assertEqual(len(report["scenarios"]), 5)
        self.assertTrue(all(item["authority_records_created"] == 0 for item in report["scenarios"]))


if __name__ == "__main__":
    unittest.main()

import importlib.util
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts" / "validate.py"
spec = importlib.util.spec_from_file_location("validator", FILE)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class StructureTests(unittest.TestCase):
    def test_offline_validation(self):
        self.assertEqual(validator.validate(), [])


if __name__ == "__main__":
    unittest.main()

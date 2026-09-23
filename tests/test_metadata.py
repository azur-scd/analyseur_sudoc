import unittest

import analyseur_sudoc


class MetadataTests(unittest.TestCase):
    def test_package_docstring_uses_visible_application_name(self):
        self.assertEqual(analyseur_sudoc.__doc__, "Analyseur Sudoc")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

import duckdb

from analyseur_sudoc.database import save_libraries
from analyseur_sudoc.libraries import parse_listrcr
from test_libraries import STAMP, TSV


class DatabaseTests(unittest.TestCase):
    def test_load_join_and_repeat(self):
        rows = parse_listrcr(TSV.encode(), STAMP)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.duckdb"
            save_libraries(rows, path)
            save_libraries(rows, path)
            with duckdb.connect(str(path)) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM LIBRARY").fetchone()[0], 2)
                result = conn.execute("SELECT l.library_ppn FROM (VALUES ('040702201')) AS h(rcr) JOIN LIBRARY l USING (rcr)").fetchone()
                self.assertEqual(result[0], "068875975")

    def test_failed_replacement_rolls_back(self):
        rows = parse_listrcr(TSV.encode(), STAMP)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.duckdb"
            save_libraries(rows, path)
            with self.assertRaises(duckdb.ConstraintException):
                save_libraries([rows[0], rows[0]], path)
            with duckdb.connect(str(path)) as conn:
                self.assertEqual(conn.execute("SELECT count(*) FROM LIBRARY").fetchone()[0], 2)


if __name__ == "__main__":
    unittest.main()

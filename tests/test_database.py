from unittest import TestCase

from sqlalchemy import inspect

case = TestCase()
case.maxDiff = None


def test_tables_exist(test_db):
    inspector = inspect(test_db.get_bind())
    case.assertIn("user_id", inspector.get_table_names())

import os
import logging
import unittest

from paths import namespace
from querymgr import query_manager as QM


class TestQueryMgr(unittest.TestCase):

    def test_find_sql(self):
        count = 0
        for _, _, files in os.walk(os.path.join(namespace.PROJECT_DIR, 'sql.d')):
            for file in files:
                if file.endswith('.sql'):
                    count += 1

        assert count == len(QM._QueryManager__find_sql())

    def test_init_manager(self):
        QM.init_manager(logging)

        assert 'SELECT DISTINCT name' in QM.find_pkgset_get_package_names
        assert '' == QM.nonexistent_attribute


if __name__ == '__main__':
    unittest.main()

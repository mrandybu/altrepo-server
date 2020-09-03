import unittest
from unittest.mock import MagicMock, patch

from logic_server import Connection, server


class TestLogicServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """true database parameters
        can set it in `paths` or override here"""
        # namespace.DATABASE_HOST = '8.8.8.8'
        # namespace.DATABASE_NAME = 'google'

        cls.m = MagicMock()

    def test_db_connection(self):
        conn = Connection()

        assert False is conn.db_connection.connection_status
        conn.db_connection.make_connection()
        assert True is conn.db_connection.connection_status
        conn.drop_connection()
        assert False is conn.db_connection.connection_status

    def test_send_request(self):
        conn = Connection()

        conn.request_line = 'SELECT name FROM Package LIMIT 10'
        status, response = conn.send_request()

        assert True is status
        assert 10 == len(response)

    def test_get_one_value(self):
        self.m.args = {
            'arg1': 'value1',
            'arg2': 123,
            'arg3': 'true',
            'arg4': '\'[^A-Za-z0-9_]\''
        }

        with patch('logic_server.request', self.m):
            assert 'value1' == server.get_one_value('arg1', type_='s')
            assert 123 == server.get_one_value('arg2', type_='i')
            assert 1 is server.get_one_value('arg3', type_='b')
            assert '[^A-Za-z0-9_]' == server.get_one_value('arg4', type_='r')

    def test_get_dict_values(self):
        self.m.args = {
            'pkg_ls': 'glibc,perl',
            'branch': 'sisyphus',
            'arch': 'x86_64,noarch',
        }

        with patch('logic_server.request', self.m):
            struct = server.get_dict_values([
                ('pkg_ls', 's', 'pkg_name'), ('task', 'i'),
                ('branch', 's', 'repo_name'), ('arch', 'i'),
            ])

            assert 'glibc,perl' == struct.get('pkg_ls')
            assert None is struct.get('task')
            assert 'Sisyphus' is struct.get('branch')
            assert False is struct.get('arch')

    def test_check_input_params(self):
        self.m.connection = Connection()
        # correct parameters
        self.m.args = {
            'name': 'python-module-flask',
            'arch': 'noarch,x86_64',
            'branch': 'p9',
        }

        with patch('logic_server.g', self.m):
            with patch('logic_server.request', self.m):
                assert True is server.check_input_params()

            # incorrect branch name
            self.m.args = {'branch': 'p99'}
            with patch('logic_server.request', self.m):
                assert 'Unknown branch' in server.check_input_params()

            # incorrect package name
            self.m.args = {'name': 'non-existent name'}
            with patch('logic_server.request', self.m):
                assert 'Package(s) with input parameters is not in the ' \
                       'repository' in server.check_input_params()

    def test_get_values_by_params(self):
        self.m.args = {
            'sha1': '53ddac04bd35f566a818e020d59b1bcb2e58bbe9',
            'name': 'fwbuilder-ipt',
            'buildtime': '100000'
        }

        struct = {
            'sha1': {
                'rname': 'pkgcs',
                'type': 's',
                'action': None,
                'notenpty': False,
            },
            'name': {
                'rname': 'name',
                'type': 's',
                'action': None,
                'notempty': False,
                'is_': 'pkg_name',
            },

            'buildtime': {
                'rname': 'buildtime',
                'type': 'i',
                'action': "{} = {}",
                'notempty': False,
            },
        }

        correct_response = [
            "pkgcs = '137905963604748147'",
            "AND name = 'fwbuilder-ipt'",
            'AND buildtime = 100000'
        ]

        with patch('logic_server.request', self.m):
            assert correct_response == server.get_values_by_params(struct)


if __name__ == '__main__':
    unittest.main()

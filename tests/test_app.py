import unittest
import datetime
from app import LogicServer
import json


class TestApp(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self) -> None:
        pass

    def get_server_with_test_config(self):
        logic_server = LogicServer()

        return logic_server

    @staticmethod
    def convert_response(response):
        return json.loads(response.data.decode('utf-8'))

    def test_last_version(self):
        server = self.get_server_with_test_config()

        _, last_version = server.get_last_version('libtcplay', 'Sisyphus')

        assert last_version == '2.0'

    def test_last_date(self):
        server = self.get_server_with_test_config()

        repodate = server.get_last_date()

        assert datetime.datetime.strptime(
            '2019-06-05', '%Y-%m-%d').date() == repodate

    def test_request_status(self):
        server = self.get_server_with_test_config()

        # good query
        server.request_line = "SELECT name FROM Package LIMIT 1"
        true_status, _ = server.send_request()

        # bad query
        server.request_line = "SELECT _name_ FROM Package LIMIT 1"
        false_status, _ = server.send_request()

        assert true_status is True
        assert false_status is False

    def test_package_files(self):
        files = [
            '/usr/include/tclxslt',
            '/usr/include/tclxslt/tclxslt.h',
        ]

        response = self.convert_response(
            self.test.get("/package_files?sha1="
                          "8934dda8b2c4548217b23f5178d6dd0558c99073")
        )['files']

        assert set(response) == set(files)

    def test_package_info(self):
        test_struct = {
            'arch': 'noarch',
            'branch': 'p8',
            'version': '5.5.1',
            'name': 'puppet',
            'packager': 'cas',
        }

        response = self.convert_response(
            self.test.get("/package_info?name=puppet&branch=p8"))['0']

        assert response['arch'] == test_struct['arch']
        assert response['branch'] == test_struct['branch']
        assert response['version'] == test_struct['version']
        assert response['name'] == test_struct['name']
        assert response['packager'] == test_struct['packager']

    def test_package_by_file(self):
        # by file
        response_by_file = self.convert_response(
            self.test.get("/package_by_file?file=/usr/bin/syslinux")
        )

        # by mask
        response_by_mask = self.convert_response(
            self.test.get("package_by_file?mask='/etc/bacula/pool.d/%.conf'")
        )

        # by md5
        response_by_md5 = self.convert_response(
            self.test.get("package_by_file?md5=c5ab3e09e155543ed2bf0a03a3baa4e3")
        )
        md5_package = tuple(
            set(response_by_md5[res]['name'] for res in response_by_md5)
        )

        assert response_by_file['0']['name'] == 'syslinux1'
        assert response_by_mask['0']['name'] == 'bacula9-director-common'
        assert ''.join(md5_package) == 'pekwm'

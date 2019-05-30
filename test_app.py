import unittest
import psycopg2
import datetime
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from subprocess import Popen, PIPE
from app import LogicServer


class TestApp(unittest.TestCase):

    def setUp(self):
        self.conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            password='',
            host='localhost',
        )

        self.TEST_DB_NAME = 'altrepo_test'
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        self.cursor = self.conn.cursor()

        restore_cmd = '/usr/bin/pg_restore -U postgres -d {db} {db}.dump' \
                      ''.format(db=self.TEST_DB_NAME).split()

        try:
            self.cursor.execute("CREATE DATABASE {}".format(self.TEST_DB_NAME))
            Popen(restore_cmd, stdout=PIPE, stderr=PIPE).wait()
        except psycopg2.DatabaseError as err:
            if err.pgcode != '42P04':
                return 'db err'

    def tearDown(self) -> None:
        self.cursor.execute("DROP DATABASE {}".format(self.TEST_DB_NAME))

        self.cursor.close()
        self.conn.close()

    def get_server_with_test_config(self):
        logic_server = LogicServer()

        logic_server.db_connection = {
            'dbname': self.TEST_DB_NAME,
            'user': 'postgres',
            'password': '',
            'host': 'localhost',
        }

        return logic_server

    def test_last_version(self):
        server = self.get_server_with_test_config()

        _, last_version = server.get_last_version('kde5-korganizer', 'Sisyphus')

        assert last_version == '19.04.0'

    def test_last_date(self):
        server = self.get_server_with_test_config()

        date_of_repo = server._get_last_date_record()

        assert datetime.datetime(2019, 5, 29) == date_of_repo

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

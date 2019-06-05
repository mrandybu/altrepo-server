import unittest
from db_connection import DBConnection


class TestDataBase(unittest.TestCase):
    default_connection = {
        'dbname': 'postgres',
        'user': 'postgres',
        'password': '',
        'host': '10.88.13.7',
    }

    def test_db_connection(self):
        database = DBConnection(dbconn_struct=self.default_connection)
        database.db_query = "SELECT current_database()"
        response = database.send_request()

        assert response[0] is True
        assert response[1][0] == ('postgres',)

    def test_db_cursor(self):
        database = DBConnection(dbconn_struct=self.default_connection)

        with database.get_db_cursor() as (connection, error):
            assert error is None

    def test_pool(self):
        database = DBConnection(dbconn_struct=self.default_connection)

        with database.get_db_connection() as (connection, error):
            assert error is None

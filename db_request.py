import psycopg2
import logging


class DBRequest:
    def __init__(self):
        pass

    @staticmethod
    def get_connection(conn_struct):
        try:
            conn = psycopg2.connect(dbname=conn_struct.get('dbname'),
                                    user=conn_struct.get('user'),
                                    password=conn_struct.get('passwd'),
                                    host=conn_struct.get('host'))
        except Exception as err:
            logging.error("Connection error: {}".format(err))
            return False

        return conn

    @staticmethod
    def send_request(connection, request_line):
        cursor = connection.cursor()
        result = False

        try:
            cursor.execute(request_line)
            result = cursor.fetchall()
        except Exception as err:
            logging.error("Request error: {}".format(err))

        return result

    @staticmethod
    def close_connection(connection):
        connection.close()

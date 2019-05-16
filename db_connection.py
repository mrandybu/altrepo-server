import logging
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool

logging.basicConfig(filename='altrepo_server.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)


class DBConnection(object):
    def __init__(self, maxsize=20, dbconn_struct=None, request_line=None):
        self.dbconn_struct = dbconn_struct
        self.maxsize = maxsize
        self.request_line = request_line

    @contextmanager
    def get_db_connection(self):
        try:
            pool = ThreadedConnectionPool(
                1, self.maxsize, dbname=self.dbconn_struct.get('dbname'),
                user=self.dbconn_struct.get('user'),
                password=self.dbconn_struct.get('passwd'),
                host=self.dbconn_struct.get('host'),
            )
        except Exception as error:
            logger.error(error)
            yield None, "Unable to database connect!\n"
        else:
            try:
                connection = pool.getconn()
                yield connection, None
            finally:
                pool.putconn(connection)

    @contextmanager
    def get_db_cursor(self):
        with self.get_db_connection() as (connection, error):
            if connection:
                try:
                    cursor = connection.cursor()
                    yield cursor, None
                finally:
                    cursor.close()
            else:
                yield None, error

    def send_request(self):
        response_status = False

        with self.get_db_cursor() as (cursor, error):
            if cursor:
                try:
                    cursor.execute(self.request_line)
                    response = cursor.fetchall()
                    response_status = True
                except Exception as error:
                    logger.error(error)
                    response = 'SQL request error!\n'

                return response_status, response
            else:
                return response_status, error

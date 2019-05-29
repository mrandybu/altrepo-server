from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool
from utils import get_logger, exception_to_logger, json_str_error

logger = get_logger(__name__)


class DBConnection(object):
    def __init__(self, maxsize=20, dbconn_struct=None, db_query=None):
        self.dbconn_struct = dbconn_struct
        self.maxsize = maxsize
        self.db_query = db_query

    @contextmanager
    def _get_db_connection(self):
        try:
            pool = ThreadedConnectionPool(
                1, self.maxsize, dbname=self.dbconn_struct.get('dbname'),
                user=self.dbconn_struct.get('user'),
                password=self.dbconn_struct.get('passwd'),
                host=self.dbconn_struct.get('host'),
            )
        except Exception as error:
            logger.error(exception_to_logger(error))
            yield None, json_str_error("Unable to database connect!")
        else:
            try:
                connection = pool.getconn()
                yield connection, None
            finally:
                pool.putconn(connection)

    @contextmanager
    def _get_db_cursor(self):
        with self._get_db_connection() as (connection, error):
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

        with self._get_db_cursor() as (cursor, error):
            if cursor:
                try:
                    cursor.execute(self.db_query)
                    response = cursor.fetchall()
                    response_status = True
                except Exception as error:
                    logger.error(exception_to_logger(error))
                    response = json_str_error("Error in sql query!")

                return response_status, response
            else:
                return response_status, error

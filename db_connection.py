from clickhouse_driver import Client
from utils import get_logger, exception_to_logger, json_str_error

logger = get_logger(__name__)


class DBConnection:
    def __init__(self, clickhouse_host=None, db_query=None):

        self.db_query = db_query
        self.clickhouse_client = Client(clickhouse_host)

    def send_request(self):
        response_status = False

        try:
            response = self.clickhouse_client.execute(self.db_query)
            response_status = True
        except Exception as error:
            logger.error(exception_to_logger(error))
            response = json_str_error("Error in sql query!")

        return response_status, response

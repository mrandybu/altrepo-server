from clickhouse_driver import Client
from utils import get_logger, exception_to_logger, json_str_error, print_statusbar

logger = get_logger(__name__)


class DBConnection:
    def __init__(self, clickhouse_host=None, clickhouse_name=None,
                 db_query=None):

        self.db_query = db_query
        self.clickhouse_name = clickhouse_name
        self.clickhouse_client = Client(clickhouse_host)

        if clickhouse_name:
            try:
                self.clickhouse_client.execute("USE {}".format(clickhouse_name))
            except Exception as err:
                logger.error(exception_to_logger(err))

    def send_request(self, trace=False):
        response_status = False

        try:
            if isinstance(self.db_query, tuple):
                response = self.clickhouse_client.execute(
                    self.db_query[0], self.db_query[1]
                )
            else:
                response = self.clickhouse_client.execute(self.db_query)
            response_status = True
        except Exception as error:
            logger.error(exception_to_logger(error))
            response = json_str_error("Error in sql query!")
            if trace:
                print_statusbar([(error, 'd',)])

        return response_status, response

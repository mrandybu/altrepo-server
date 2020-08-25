import os


class QueryManager:

    def __init__(self):
        self.logger = None

    def __getattr__(self, item):
        if item in dir(self):
            return self.__getattr__(item)

        self.logger.error(
            "QueryManager does not have attribute `{}`".format(item)
        )

        return ''

    @staticmethod
    def __find_sql():
        sql_struct = {}
        for root, _, files in os.walk('sql.d'):
            for file in files:
                if file.endswith('.sql'):
                    attr_name = root.split('/')[-1] + '_' + file[:-4]
                    path_to_sql = os.path.join(root, file)
                    sql_struct[attr_name] = path_to_sql

        return sql_struct

    def init_manager(self, logger):
        self.logger = logger
        for k, v in self.__find_sql().items():
            with open(v, 'r') as fd:
                setattr(self, k, fd.read())


query_manager = QueryManager()

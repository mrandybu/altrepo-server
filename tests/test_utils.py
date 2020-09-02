import os
import json
import time
import logging
import unittest
import tempfile
from io import StringIO

import utils
from utils import func_time

log_stream = StringIO()
logging.basicConfig(stream=log_stream, level=logging.INFO)


class TestUtils(unittest.TestCase):
    def test_get_logger(self):
        logger = utils.get_logger(__name__)
        message = "logging from {}".format(__name__)
        logger.info(message)

        assert message in log_stream.getvalue()

    def test_exception_to_logger(self):
        try:
            1 / 0
        except Exception as err:
            assert 'division by zero' == utils.exception_to_logger(err)

    def test_read_config(self):
        contain = """
                [TestConfig]
                Field1 = value1
                Field2 = value2
                Field3 = value3
                """

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(contain.encode())
        tmp.close()

        path = os.path.join(os.path.dirname(tmp.name), tmp.name)
        config = utils.read_config(path)

        os.remove(path)

        assert 'value1' == config.get('TestConfig', 'Field1')
        assert 'value2' == config.get('TestConfig', 'Field2')
        assert 'value3' == config.get('TestConfig', 'Field3')

    def test_join_tuples(self):
        tuples = (('elem1', 'elem2', 'elem3'),
                  ('elem1.1', 'elem2.1', 'elem3.1'),
                  ('elem1.2', 'elem2.2', 'elem3.2'),)

        join_tuple = utils.join_tuples(tuples)

        assert ('elem1', 'elem1.1', 'elem1.2') == join_tuple

    def test_convert_to_json(self):
        values = [('elem1', 'elem2', 'elem3'),
                  ('elem1.1', 'elem2.1', 'elem3.1'),
                  ('elem1.2', 'elem2.2', 'elem3.2'), ]
        js = json.loads(
            utils.convert_to_json(['key1', 'key2', 'key3'], values)
        )

        assert 'elem1' == js['0']['key1']
        assert 'elem2.1' == js['1']['key2']
        assert 'elem3.2' == js['2']['key3']

    def test_func_time(self):
        logger = logging.getLogger()

        @func_time(logger)
        def sleep_func():
            time.sleep(2)

        sleep_func()

        assert 'Time sleep_func is 2.' in log_stream.getvalue()

    def test_tuplelist_to_dict(self):
        assert {1: [2], 2: [3, 4], 7: [8, 9]} == utils.tuplelist_to_dict(
            ((1, 2), (2, 3, 4, 6), (7, 8, 9)), 2
        )
        assert {1: [2, 3, 4, 5], 6: [7, 8], 9: [0, 1, 2]} == utils.tuplelist_to_dict(
            ((1, 2, 3, 4, 5), (6, 7, 8), (9, 0, 1, 2)), 4
        )
        assert {1: [2, 3, 4], 3: []} == utils.tuplelist_to_dict(
            ((1,), (1, 2, 3, 4), (3,)), 6
        )

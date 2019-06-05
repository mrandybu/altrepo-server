import unittest
import json
import time
import utils
from utils import func_time
from paths import paths


class TestUtils(unittest.TestCase):
    def test_logger(self):
        logger = utils.get_logger(__name__)
        message = "logging from {}".format(__name__)
        logger.info(message)

        with open(paths.LOG_FILE) as log:
            assert message in log.read()

    def test_exception_logger(self):
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
        file = "/tmp/{}".format(__name__)
        with open(file, "w") as f:
            f.write(contain)

        config = utils.read_config(file)

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
        logger = utils.get_logger(__name__)

        @func_time(logger)
        def sleep_fuc():
            time.sleep(2)

        sleep_fuc()

        with open(paths.LOG_FILE) as f:
            assert 'Time sleep_fuc is 2.' in f.read()

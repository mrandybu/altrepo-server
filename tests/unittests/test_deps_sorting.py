import json
import unittest

from libs.deps_sorting import SortList


class TestDepsSorting(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        with open('deps_sorting_data/input_struct', 'r') as fd:
            cls.test_struct = json.loads(fd.read())

    def test_sort_list(self):
        sort = SortList(self.test_struct, 'a')
        circle, sorted_ = sort.sort_list()

        with open('deps_sorting_data/result_circle', 'r') as fd_c, \
                open('deps_sorting_data/result_sorted') as fd_s:
            res_circle = json.loads(fd_c.read())
            res_sorted = fd_s.read().split('\n')

        assert res_circle == circle
        assert res_sorted == sorted_

    def test_numbered_list(self):
        name_num, num_name = SortList._numbered_list([
            'curl', 'strongswan', 'SimGear', 'osgEarth', 'adp'
        ])

        assert {'curl': 0, 'strongswan': 1, 'SimGear': 2,
                'osgEarth': 3, 'adp': 4} == name_num
        assert {0: 'curl', 1: 'strongswan', 2: 'SimGear',
                3: 'osgEarth', 4: 'adp'} == num_name

    def test_search_circle_deps(self):
        sort = SortList(None, None)
        sort.package_reqs = self.test_struct

        with open('deps_sorting_data/result_circle') as fd:
            res_circle = json.loads(fd.read())

        assert res_circle == sort._search_circle_deps()


if __name__ == '__main__':
    unittest.main()

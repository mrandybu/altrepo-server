import unittest

from libs.deps_sorting import SortList


class TestDepsSorting(unittest.TestCase):
    def test_sort_list(self):
        test_struct = {
            'a': [],
            'b': ['c', 'a'],
            'c': ['d', 'b', 'a'],
            'd': ['e', 'a'],
            'e': ['a'],
            'f': ['b', 'c', 'e', 'a'],
        }

        sort = SortList(test_struct, 'a')
        circle, sorted_ = sort.sort_list()

        assert {0: 'a', 1: 'e', 2: 'd', 3: 'c', 4: 'b', 5: 'f'} == \
               {sorted_.index(i): i for i in sorted_}
        assert {'b': {'c': 3}, 'c': {'b': 2}} == circle


if __name__ == '__main__':
    unittest.main()

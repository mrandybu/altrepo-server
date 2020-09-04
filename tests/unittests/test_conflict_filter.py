import unittest

from libs.conflict_filter import ConflictFilter


class TestConflictFilter(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cf = ConflictFilter(None, None)

    def test_get_conflicts(self):
        dA = {
            'conflict': [
                ('syslinux', '', 0),
                ('syslinux4-extlinux', '', 0)
            ],
            'provide': [
                ('exlinux', '6.04.pre3-alt2:sisyphus+240957.100.1.1', 8),
                ('syslinux4-exlinux', '6.04.pre3-alt2', 8)
            ],
        }
        dB = {
            'conflict': [],
            'provide': [
                ('syslinux', '2:4.04-alt16:sisyphus+242564.100.1.1', 8)
            ],
        }

        hshA, hshB = 17830059475705751619, 8505303502925891219

        hsh_evrd = {
            8505303502925891219: [
                0,
                '6.04.pre3',
                'alt2',
                'sisyphus+240957.100.1.1'
            ],
            17830059475705751619: [
                2,
                '4.04',
                'alt16',
                'sisyphus+242564.100.1.1'
            ],
        }

        assert [(17830059475705751619, 8505303502925891219)] == \
               self.cf._get_conflicts(dA, dB, hshA, hshB, hsh_evrd)

    def test_split_version(self):
        assert (0, '6.04.pre3', 'alt2', 'sisyphus+240957.100.1.1') == \
               (self.cf._split_version('6.04.pre3-alt2:sisyphus+240957.100.1.1'))
        assert ('1', '1.0.1', 'alt0', None) == \
               self.cf._split_version('1:1.0.1-alt0')

    def test_compare_version(self):
        assert 0 == self.cf._compare_version(
            (0, '6.04.pre3', 'alt2', None), (0, '6.04.pre3', 'alt2', None)
        )
        assert -1 == self.cf._compare_version(
            (0, '5.04.pre3', 'alt2', None), (0, '6.04.pre3', 'alt2', None)
        )
        assert 1 == self.cf._compare_version(
            (0, '6.04.pre3', 'alt2', None), (0, '6.04.pre3', 'alt1', None)
        )
        assert 1 == self.cf._compare_version(
            (1, '6.04.pre3', 'alt2', None), (0, '6.04.pre3', 'alt2', None)
        )


if __name__ == '__main__':
    unittest.main()

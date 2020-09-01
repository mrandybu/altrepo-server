import rpm
from flask import g
from collections import defaultdict

import utils


class ConflictFilter:
    """
    Class for conflicts filter.

    Class contains method which finds conflicts and obsoletes between two
    packages and its auxiliary methods.

    :param pbranch: name of package repository
    :param parch: packages archs
    """

    def __init__(self, pbranch, parch):
        self.pbranch = pbranch
        self.parch = parch

    def _get_dict_conflict_provide(self, hshs):

        # get conflicts and provides by hash
        g.connection.request_line = (
            "SELECT DISTINCT pkghash, dptype, dpname, dpversion, flag FROM "
            "Depends WHERE pkghash IN %(hshs)s AND dptype IN "
            "('conflict', 'provide', 'obsolete')", {
                'hshs': tuple(hshs), 'branch': self.pbranch, 'arch': self.parch
            }
        )

        status, response = g.connection.send_request()
        if status is False:
            return response

        hsh_dpt_dict = defaultdict(lambda: defaultdict(list))
        for hsh, *args in response:
            dptype = 'conflict' if args[0] == 'obsolete' else args[0]
            hsh_dpt_dict[hsh][dptype] += [tuple(args[1:])]

        g.connection.request_line = (
            "SELECT pkghash, epoch, version, release, disttag FROM "
            "Package WHERE pkghash IN %(hshs)s", {'hshs': tuple(hshs)}
        )

        status, response = g.connection.send_request()
        if status is False:
            return response

        return hsh_dpt_dict, utils.tuplelist_to_dict(response, 4)

    def _get_conflicts(self, dA, dB, hshA, hshB, hsh_evrd):
        """
        Finds conflicts between two packages.

        Method of find conflicts between two packages uses conflicts of one
        and provides of the second package.

        :param dA: dict conflicts/provides package A
        :param dB: dict conflicts/provides package B
        :param hshA: hash package A
        :param hshB: hash package B
        :return: `list` of `tuple` (package hash, conflict hash) for package A
        """
        conflicts = []
        for confl in dA['conflict']:
            for provd in dB['provide']:
                if confl[0] == provd[0]:
                    # add conflict in list if conflict without version
                    if confl[1] == '' or confl[2] == 0:
                        conflicts.append((hshA, hshB))
                    else:
                        # version of provide
                        vv1 = tuple(hsh_evrd[hshB])
                        # version of conflict
                        vv2 = self._split_version(confl[1])

                        # make compare versions
                        eq = self._compare_version(vv1, vv2)

                        flag = confl[2]

                        # check conflict version flag (>, <, =, >=, <=)
                        if (eq == -1 and flag & 1 << 1 != 0) or \
                                (eq == 0 and flag & 1 << 3 != 0) or \
                                (eq == 1 and flag & 1 << 2 != 0):
                            conflicts.append((hshA, hshB))

        return conflicts

    def detect_conflict(self, confl_list):
        """
        Main public class method.

        List of package tuples that conflict with the given package. Return
        join list for package A and package B.

        :param confl_list: list of tuples with package hashes
        :return: `list` of `tuple` (package hash, conflict hash) for
        input list
        """

        # get unique package hashes
        uniq_hshs = list({hsh for confl in confl_list for hsh in confl})

        # get conflicts and provides for every unique package
        # also (epoch, version, release, disttag)
        hsh_dpt_dict, hsh_evrd = self._get_dict_conflict_provide(uniq_hshs)

        conflicts = []
        for hshA, hshB in confl_list:
            # A - conflicts; B - provides
            conflA = self._get_conflicts(
                hsh_dpt_dict[hshA], hsh_dpt_dict[hshB], hshA, hshB, hsh_evrd
            )
            # A - provides; B - conflicts
            conflB = self._get_conflicts(
                hsh_dpt_dict[hshB], hsh_dpt_dict[hshA], hshB, hshA, hsh_evrd
            )

            conflicts += utils.remove_duplicate(conflA + conflB)

        return conflicts

    @staticmethod
    def _split_version(vers):
        """
        Split version of package.

        Version of packages may be contains also epoch, release, dist tag.
        It method split the version and returns each item separately.

        :param vers: version of package (dpversion in datatbase)
        :return: `int`: epoch, `str`: version, `str`: release, `str`: disttag
        """
        # split for `-alt` and get epoch, version
        epoch_vers = vers.split('-alt')[0]
        vers = vers.replace(epoch_vers, '')
        epoch_vers = epoch_vers.split(':')
        # get release, disttag
        rel_dist = vers.split(':')
        rel_dist[0] = rel_dist[0].replace('-', '')

        # release check, if not, release is 0
        if len(epoch_vers) < 2:
            epoch = 0
            vers = epoch_vers[0]
        else:
            epoch = epoch_vers[0]
            vers = epoch_vers[1]

        # disttag check, if not (disttag = ''), disttag is None
        dist = None
        if len(rel_dist) < 2:
            if rel_dist[0] != '':
                rel = rel_dist[0]
            else:
                rel = None
        else:
            rel = rel_dist[0]
            dist = rel_dist[1]

        return epoch, vers, rel, dist

    @staticmethod
    def _compare_version(vv1, vv2):
        """
        Compare versions of packages.

        The method compares versions (epoch, version, release, disttag) using
        the rpm module.

        :param vv1: version of first package
        :param vv2: version of second package
        :return: `0` if versions are identical
                 `1` if the first version is larger
                 `-1` if the first version is less
        """
        v1 = rpm.hdr()
        v2 = rpm.hdr()

        v1[rpm.RPMTAG_EPOCH] = vv1[0]
        v2[rpm.RPMTAG_EPOCH] = vv2[0]

        v1[rpm.RPMTAG_VERSION] = vv1[1]
        v2[rpm.RPMTAG_VERSION] = vv2[1]
        if vv1[2]:
            v1[rpm.RPMTAG_RELEASE] = vv1[2]
        if vv2[2]:
            v2[rpm.RPMTAG_RELEASE] = vv2[2]

        # check disttag, if true, add it
        if vv1[3] != '' and vv2[3]:
            v1[rpm.RPMTAG_DISTTAG] = vv1[3]
            v2[rpm.RPMTAG_DISTTAG] = vv2[3]

        eq = rpm.versionCompare(v1, v2)

        return eq

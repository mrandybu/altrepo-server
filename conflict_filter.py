import rpm
import utils
from logic_server import server


class ConflictFilter:
    """
    Class for conflicts filter.

    Class contains method which finds conflicts between two packages and
    its auxiliary methods.

    :param pbranch: name of package repository
    :param parch: packages archs
    """

    def __init__(self, pbranch, parch):
        self.pbranch = pbranch
        self.parch = parch

    def _get_dict_conflict_provide(self, hsh):

        # get conflicts and provides by hash
        server.request_line = (
            "SELECT DISTINCT dptype, dpname, dpversion, flag FROM Depends WHERE "
            "pkghash = %(hsh)d AND dptype IN ('conflict', 'provide')",
            {'hsh': hsh, 'branch': self.pbranch, 'arch': self.parch}
        )

        status, response = server.send_request()
        if status is False:
            return response

        # form dict `conflict` - `list of conflicts`, `provide` - `list of provides`
        dict_ = {'conflict': [], 'provide': []}
        for pkg in response:
            pkg_tpl = (pkg[1], pkg[2])
            if pkg[0] == 'conflict':
                pkg_tpl += (pkg[3],)
            dict_[pkg[0]].append(pkg_tpl)

        return dict_

    def _get_conflicts(self, dA, dB, hshA, hshB):
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
                        # get epoch, version, release, disttag for package B (provides)
                        # for compare versions with conflict
                        server.request_line = (
                            "SELECT epoch, version, release, disttag FROM "
                            "Package WHERE pkghash = %(hsh)s", {'hsh': hshB}
                        )

                        status, response = server.send_request()
                        if status is False:
                            return response

                        # version of provide
                        vv1 = response[0]
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

    def detect_conflict(self, hshA, hshB):
        """
        Main public class method.

        List of package tuples that conflict with the given package. Return
        join list for package A and package B.

        :param hshA: hash of first package
        :param hshB: hash of second package
        :return: `list` of `tuple` (package hash, conflict hash) for
        package A and package B
        """
        # get dict for A and B packages (conflicts, provides)
        dictA = self._get_dict_conflict_provide(hshA)
        dictB = self._get_dict_conflict_provide(hshB)

        # get conflicts by matching conflicts first package and provides
        # second package
        conflA = self._get_conflicts(dictA, dictB, hshA, hshB)
        conflB = self._get_conflicts(dictB, dictA, hshB, hshA)

        confls = utils.remove_duplicate(conflA + conflB)

        return confls

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

        v1[rpm.RPMTAG_RELEASE] = vv1[2]
        v2[rpm.RPMTAG_RELEASE] = vv2[2]

        # check disttag, if true, add it
        if vv1[3] != '' and vv2[3]:
            v1[rpm.RPMTAG_DISTTAG] = vv1[3]
            v2[rpm.RPMTAG_DISTTAG] = vv2[3]

        eq = rpm.versionCompare(v1, v2)

        return eq

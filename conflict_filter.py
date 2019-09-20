import rpm
import utils
from clickhouse_driver import Client

client = Client('')
client.execute("")


class ConflictFilter:
    def __init__(self, pbranch, parch):
        self.pbranch = pbranch
        self.parch = parch

    def _get_dict_conflict_provide(self, hsh):

        response = client.execute(
            "SELECT DISTINCT dptype, dpname, dpversion FROM Depends WHERE "
            "pkghash = %(hsh)d AND dptype IN ('conflict', 'provide')",
            {'hsh': hsh, 'branch': self.pbranch, 'arch': self.parch}
        )

        dict_ = {'conflict': [], 'provide': []}
        for pkg in response:
            dict_[pkg[0]].append((pkg[1], pkg[2]))

        return dict_

    def _get_conflicts(self, dA, dB, hshA, hshB):
        conflicts = []
        for confl in dA['conflict']:
            for provd in dB['provide']:
                if confl[0] == provd[0]:
                    if confl[1] == '':
                        conflicts.append((hshA, hshB))
                    else:
                        # provides
                        response = client.execute(
                            "SELECT epoch, version, release, disttag FROM "
                            "Package WHERE pkghash = %(hsh)s", {'hsh': hshB}
                        )

                        # provd
                        vv1 = response[0]
                        # confl
                        vv2 = self._split_version(confl[1])

                        eq = self._compare_version(vv1, vv2)

                        if eq == 0:
                            conflicts.append((hshA, hshB))

        return conflicts

    def detect_conflict(self, hshA, hshB):
        dictA = self._get_dict_conflict_provide(hshA)
        dictB = self._get_dict_conflict_provide(hshB)

        conflA = self._get_conflicts(dictA, dictB, hshA, hshB)
        conflB = self._get_conflicts(dictB, dictA, hshB, hshA)

        confls = utils.remove_duplicate(conflA + conflB)

        return confls

    @staticmethod
    def _split_version(vers):
        epoch_vers = vers.split('-alt')[0]
        vers = vers.replace(epoch_vers, '')
        epoch_vers = epoch_vers.split(':')
        rel_dist = vers.split(':')
        rel_dist[0] = rel_dist[0].replace('-', '')

        if len(epoch_vers) < 2:
            epoch = 0
            vers = epoch_vers[0]
        else:
            epoch = epoch_vers[0]
            vers = epoch_vers[1]

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
        v1 = rpm.hdr()
        v2 = rpm.hdr()

        v1[rpm.RPMTAG_EPOCH] = vv1[0]
        v2[rpm.RPMTAG_EPOCH] = vv2[0]

        v1[rpm.RPMTAG_VERSION] = vv1[1]
        v2[rpm.RPMTAG_VERSION] = vv2[1]

        v1[rpm.RPMTAG_RELEASE] = vv1[2]
        v2[rpm.RPMTAG_RELEASE] = vv2[2]

        if vv1[3] != '' and vv2[3]:
            v1[rpm.RPMTAG_DISTTAG] = vv1[3]
            v2[rpm.RPMTAG_DISTTAG] = vv2[3]

        eq = rpm.versionCompare(v1, v2)

        return eq

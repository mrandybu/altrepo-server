from logic_server import server
import utils


class PackageDependencies:
    def __init__(self, pbranch):
        self.pbranch = pbranch
        self.static_archs = ['x86_64', 'noarch']
        self.dep_dict = {}

    def get_package_dep_set(self, pkgs=None, first=False):

        server.request_line = \
            "SELECT srchsh, groupUniqArray(pkghash) FROM (SELECT " \
            "pkghash AS srchsh, dpname FROM Depends WHERE pkghash IN " \
            "({pkgs}) AND dptype = 'require') INNER JOIN (SELECT pkghash, " \
            "dpname FROM last_depends WHERE dptype = 'provide' AND " \
            "assigment_name = '{branch}' AND sourcepackage = 0 AND arch IN " \
            "({archs})) USING dpname GROUP BY srchsh".format(
                pkgs=pkgs, branch=self.pbranch, archs=tuple(self.static_archs)
            )

        status, response = server.send_request()
        if status is False:
            return response

        tmp_list = []
        for key, val in response:
            if first:
                self.dep_dict[key] = val
                tmp_list += [hsh for hsh in val if hsh not in tmp_list]
            else:
                for pkg, hshs in self.dep_dict.items():
                    if key in hshs:
                        uniq_hshs = [l for l in val if l not in self.dep_dict[pkg]]
                        self.dep_dict[pkg] += tuple(uniq_hshs)
                        tmp_list += uniq_hshs

        if not tmp_list:
            return self.dep_dict

        return self.get_package_dep_set(pkgs=tuple(tmp_list))

    @staticmethod
    def make_result_dict(hsh_list, hsh_dict):
        fields = ['name', 'version', 'release', 'epoch', 'archs']

        server.request_line = \
            "SELECT pkghash, name, version, release, epoch, " \
            "groupUniqArray(arch) FROM Package WHERE pkghash IN ({}) " \
            "GROUP BY (pkghash, name, version, release, epoch)" \
            "".format(tuple(hsh_list))

        status, response = server.send_request()
        if status is False:
            return response

        dict_info = utils.tuplelist_to_dict(response, 5)

        result_dict = {}
        for pkg, hshs in hsh_dict.items():

            counter = 0
            control_list, pkg_req_dict = [], {}
            for hsh in hshs:
                first = dict_info[hsh]

                archs = ()
                for hh in hshs:
                    second = dict_info[hh]

                    if first[:3] == second[:3]:
                        archs += second[4]

                dict_info[hsh][4] = tuple(set(archs))

                if dict_info[hsh] not in control_list:
                    control_list.append(dict_info[hsh])

                    pkg_info_dict = {}
                    for i in range(len(fields)):
                        pkg_info_dict[fields[i]] = dict_info[hsh][i]

                    pkg_req_dict[counter] = pkg_info_dict
                    counter += 1

            result_dict[dict_info[pkg][0]] = pkg_req_dict

        return result_dict

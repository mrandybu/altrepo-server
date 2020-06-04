from logic_server import server


class PackageDependencies:
    def __init__(self, pbranch):
        self.pbranch = pbranch
        self.static_archs = ['x86_64', 'noarch']
        self.dep_list = []

    def get_package_dep_set(self, pkgs=None):
        server.request_line = (
            "SELECT pkg.pkghash FROM last_packages WHERE pkg.pkghash IN ("
            "SELECT pkghash FROM Depends WHERE dpname IN (SELECT dpname FROM "
            "Depends WHERE pkghash IN ({pkgs}) AND dptype = 'require') AND "
            "dptype = 'provide') AND assigment_name = '{branch}' AND "
            "sourcepackage = 0 AND arch IN {archs}".format(
                pkgs=pkgs, branch=self.pbranch, archs=tuple(self.static_archs)
            )
        )

        status, response = server.send_request()
        if status is False:
            return response

        tmp_list = [dep[0] for dep in response if dep[0] not in self.dep_list]
        if not tmp_list:
            return self.dep_list

        self.dep_list += tmp_list

        return self.get_package_dep_set(pkgs=tuple(tmp_list))

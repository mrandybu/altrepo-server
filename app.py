from flask import Flask, request, json
from db_connection import DBConnection

app = Flask(__name__)


class LogicServer:
    _db_connection = {
        'dbname': 'alter_altrepo',
        'user': 'underwit',
        'password': '1',
        'host': '10.88.13.7',
    }

    def __init__(self, request_line=None):
        self.package_params = [
            'sha1header', 'subtask', 'name', 'arch', 'version', 'release',
            'epoch', 'serial_', 'summary', 'description', 'changelog',
            'buildtime', 'buildhost', 'size', 'distribution', 'vendor', 'gif',
            'xpm', 'license', 'group_', 'source', 'patch', 'url', 'os',
            'prein', 'postin', 'preun', 'postun', 'icon', 'archivesize',
            'rpmversion', 'preinprog', 'postinprog', 'preunprog', 'postunprog',
            'buildarchs', 'verifyscript', 'verifyscriptprog', 'cookie',
            'prefixes', 'instprefixes', 'sourcepackage', 'optflags', 'disturl',
            'payloadformat', 'payloadcompressor', 'payloadflags', 'platform',
            'disttag', 'sourcerpm', 'filename',
        ]
        self.request_line = request_line

    def send_request(self):
        db = DBConnection(dbconn_struct=self._db_connection)
        db.request_line = self.request_line

        return db.send_request()

    @staticmethod
    def convert_to_json(keys, values):
        js = {}

        for i in range(len(values)):
            js[i] = dict([(keys[j], values[i][j])
                          for j in range(len(values[i]))])

        return json.dumps(js)

    def get_last_date_record(self):
        request_line_tmp = self.request_line
        self.request_line = "SELECT datetime_release FROM AssigmentName " \
                            "ORDER BY id DESC LIMIT 1"

        status, result = self.send_request()
        if status is False:
            return result

        self.request_line = request_line_tmp

        if result is not False:
            return result[0][0]

    def add_extra_package_params(self, extra_package_params):
        self.package_params += extra_package_params

    @staticmethod
    def get_one_value(param):
        value = request.args.get(param)
        return value

    def check_input_params(self):
        # check arch
        parch = self.get_one_value('arch')
        if parch and parch not in ['aarch64', 'armh', 'i586',
                                   'noarch', 'x86_64', 'x86_64-i586']:
            return 'Unknown arch of package!\n'

        # check branch
        pbranch = self.get_one_value('branch')
        if pbranch and pbranch not in ['p7', 'p8', 'Sisyphus']:
            return 'Unknown branch!\n'

        # check package params
        pname = self.get_one_value('name')
        if pname:
            default_req = "SELECT p.name FROM Package p"
            args = "p.name = '{}'".format(pname)

            pversion = self.get_one_value('version')
            if pversion:
                args = "{} AND p.version = '{}'".format(args, pversion)

            if pbranch:
                extra_params = \
                    "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
                    "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id"

                default_req = "{} {}".format(default_req, extra_params)
                args = "{} AND an.name = '{}'".format(args, pbranch)

            self.request_line = "{} WHERE {}".format(default_req, args)

            status, result = self.send_request()
            if status is False:
                return result

            if len(result) == 0:
                return "Package with params not exists!\n"

        return True

    def get_values_by_params(self, input_params):
        params_list = []

        for param in input_params:
            value = self.get_one_value(param)

            notempty = input_params[param].get('notempty')
            if not value and notempty is True:
                return False

            action = input_params[param].get('action')

            if value or action:
                arg = "{} = '{}'"
                rname = input_params[param].get('rname')
                type_ = input_params[param].get('type')

                if action:
                    arg = action
                else:
                    if type_ == 'i':
                        if type(value) is not int:
                            return False
                        arg = "{} {}"
                    if type_ == 'b':
                        if value.lower() == 'true':
                            arg = "{} IS NULL"
                        elif value.lower() == 'false':
                            arg = "{} IS NOT NULL"
                        else:
                            return False
                    if type_ == 't':
                        arg = "{} = {}"

                if arg:
                    arg = arg.format(rname, value)
                    if len(params_list) > 0:
                        arg = "AND {}".format(arg)

                    params_list.append(arg)

        if len(params_list) == 0:
            return False

        return params_list

    @staticmethod
    def join_tuples(tuple_list):
        return tuple([tuple_[0] for tuple_ in tuple_list])


@app.route('/package_info')
def package_info():
    server = LogicServer()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime')
    if buildtime_value:
        if buildtime_value not in ['>', '<', '=']:
            buildtime_action = "{} = {}"

    date_value = server.get_one_value('date')
    if date_value is None:
        date_value = "{} IN (SELECT datetime_release FROM AssigmentName " \
                     "ORDER BY datetime_release DESC LIMIT 1)"
    else:
        date_value = None

    intput_params = {
        'name': {
            'rname': 'p.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'version': {
            'rname': 'p.version',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'release': {
            'rname': 'p.release',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'arch': {
            'rname': 'p.arch',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'disttag': {
            'rname': 'p.disttag',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'buildtime': {
            'rname': 'p.buildtime',
            'type': 'i',
            'action': buildtime_action,
            'notempty': False,
        },
        'sourcerpm': {
            'rname': 'p.sourcerpm',
            'type': 'b',
            'action': None,
            'notempty': False,
        },
        'branch': {
            'rname': 'an.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'date': {
            'rname': 'an.datetime_release',
            'type': 's',
            'action': date_value,
            'notempty': False,
        },
        'packager': {
            'rname': 'pr.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(intput_params)
    if params_values is False:
        return 'Request params error..(\n'

    server.request_line = \
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id WHERE " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    status, response = server.send_request()
    if status is False:
        return response

    server.add_extra_package_params(['packager', 'branch', 'date', 'files',
                                     'requires', 'conflicts', 'obsoletes',
                                     'provides'])

    json_retval = json.loads(
        server.convert_to_json(server.package_params, response)
    )

    for elem in json_retval:
        package_sha1 = json_retval[elem]['sha1header']

        # files
        server.request_line = \
            "SELECT filename FROM File WHERE package_sha1 = '{}'" \
            "".format(package_sha1)

        status, files = server.send_request()
        if status is False:
            return files

        json_retval[elem]['files'] = server.join_tuples(files)

        p_list = [('Require', 'requires'), ('Conflict', 'conflicts'),
                  ('Obsolete', 'obsoletes'), ('Provide', 'provides')]

        for pl in p_list:
            server.request_line = "SELECT name, version FROM {table} " \
                                  "WHERE package_sha1 = '{sha1}'" \
                                  "".format(table=pl[0], sha1=package_sha1)

            status, response = server.send_request()
            if status is False:
                return response

            json_retval[elem][pl[1]] = server.join_tuples(response)

    return json.dumps(json_retval)


@app.route('/misconflict_packages')
def conflict_packages():
    server = LogicServer()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name')
    pbranch = server.get_one_value('branch')

    if not pname or not pbranch:
        return 'Package name and branch not be empty!\n'

    # version
    pversion = server.get_one_value('version')
    if not pversion:
        server.request_line = \
            "SELECT MAX(p.version) FROM Package p " \
            "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}'" \
            "".format(name=pname, branch=pbranch)

        status, pversion = server.send_request()
        if status is False:
            return pversion

        pversion = pversion[0][0]

    # files
    pfiles = server.get_one_value('files')
    if not pfiles:
        server.request_line = \
            "SELECT DISTINCT f.filename, p.arch FROM Package p " \
            "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
            "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE p.name = '{name}' AND an.name = '{branch}' " \
            "AND p.version = '{version}'" \
            "".format(name=pname, branch=pbranch, version=pversion)

        status, pfiles = server.send_request()
        if status is False:
            return pfiles

    pfiles = tuple([(file[0], file[1]) for file in pfiles])

    # packages with ident files
    server.request_line = \
        "SELECT DISTINCT p.name, p.version, p.release, p.arch, p.sha1header " \
        "FROM Package p INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE (f.filename, p.arch) IN {files} " \
        "AND CAST(f.filemode AS VARCHAR) NOT LIKE '1%' " \
        "AND p.name != '{name}' AND p.sourcerpm IS NOT NULL " \
        "AND an.name = '{branch}' AND an.datetime_release IN " \
        "(SELECT datetime_release FROM AssigmentName " \
        "ORDER BY datetime_release DESC LIMIT 1)" \
        "".format(files=pfiles, name=pname, branch=pbranch)

    status, packages_with_ident_files = server.send_request()
    if status is False:
        return packages_with_ident_files

    packages_with_ident_files = [(el[0], "{}-{}".format(el[1], el[2]), el[3])
                                 for el in packages_with_ident_files]

    # conflicts input package
    server.request_line = \
        "SELECT DISTINCT c.name, c.version, p.arch FROM Package p " \
        "INNER JOIN Conflict c ON c.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE p.name = '{name}' AND p.version = '{version}' " \
        "AND an.name = '{branch}'" \
        "".format(name=pname, version=pversion, branch=pbranch)

    status, conflicts = server.send_request()
    if status is False:
        return conflicts

    packages_without_conflict = []

    for package in packages_with_ident_files:
        if package[2] == 'noarch':
            for conflict in conflicts:
                conflict = (conflict[0], conflict[1])

                if (package[0], package[1]) != conflict and \
                        (package[0], '') != conflict:
                    packages_without_conflict.append(package)
        else:
            if package not in conflicts and \
                    (package[0], '', package[2]) not in conflicts:
                packages_without_conflict.append(package)

    result_packages = []

    for package in packages_without_conflict:
        package = (package[0], package[1].split("-")[0],
                   package[1].split("-")[1], package[2])

        # conflicts found packages
        server.request_line = \
            "SELECT DISTINCT c.name, c.version, p.arch FROM Package p " \
            "INNER JOIN Conflict c ON c.package_sha1 = p.sha1header " \
            "INNER JOIN Assigment a ON a.package_sha1 = sha1header " \
            "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
            "WHERE (p.name, p.version, p.release, p.arch) = {nvr} " \
            "AND an.name = '{branch}'" \
            "".format(nvr=package, branch=pbranch)

        status, conflicts = server.send_request()
        if status is False:
            return conflicts

        ind = False
        for conflict in conflicts:
            if (pname, pversion) == (conflict[0], conflict[1]) or \
                    (pname, '') == (conflict[0], conflict[1]):
                ind = True
                break

        # conflict files
        if ind is False:
            server.request_line = \
                "SELECT DISTINCT f.filename FROM Package p " \
                "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
                "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
                "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
                "WHERE (p.name, p.version, p.release, p.arch) = {nvr} " \
                "AND an.name = '{branch}' AND (f.filename, p.arch) IN {files}" \
                "".format(nvr=package, branch=pbranch, files=pfiles)

            status, files = server.send_request()
            if status is False:
                return files

            files = server.join_tuples(files)

            result_packages.append((package[0],
                                    "{}-{}".format(package[1], package[2]),
                                    package[3], files))

    return server.convert_to_json(['name', 'version', 'arch', 'files'],
                                  result_packages)


@app.route('/package_by_file')
def package_by_file():
    server = LogicServer()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    input_params = {
        'file': {
            'rname': 'f.filename',
            'type': 's',
            'action': None,
            'notempty': True,
        },
        'branch': {
            'rname': 'an.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        return 'Request params error..(\n'

    server.request_line = \
        "SELECT DISTINCT p.name, p.version, an.name FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "WHERE {args}".format(args=" ".join(params_values))

    status, response = server.send_request()
    if status is False:
        return response

    return server.convert_to_json(['name', 'version', 'branch'], response)


@app.route('/package_files')
def package_files():
    server = LogicServer()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1')

    server.request_line = \
        "SELECT DISTINCT f.filename FROM Package p " \
        "INNER JOIN File f ON f.package_sha1 = p.sha1header " \
        "WHERE p.sourcerpm IS NOT NULL " \
        "AND p.sha1header = '{sha1}'".format(sha1=sha1)

    status, response = server.send_request()
    if status is False:
        return response

    tp = server.join_tuples(response)

    js = {
        'sha1': sha1,
        'files': tp
    }

    return json.dumps(js)


@app.route('/dependent_packages')
def dependent_packages():
    server = LogicServer()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    input_params = {
        'name': {
            'rname': 'r.name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'version': {
            'rname': 'r.version',
            'type': 's',
            'action': "{} LIKE '{}%'",
            'notempty': False,
        },
        'branch': {
            'rname': 'an.name',
            'type': 's',
            'action': None,
            'notempty': False,

        },
        'date': {
            'rname': 'an.datetime_release',
            'type': 's',
            'action': None,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        return 'Request params error..(\n'

    server.request_line = \
        "SELECT p.{}, pr.name, an.name, an.datetime_release FROM Package p " \
        "INNER JOIN Assigment a ON a.package_sha1 = p.sha1header " \
        "INNER JOIN Packager pr ON pr.id = p.packager_id " \
        "INNER JOIN AssigmentName an ON an.id = a.assigmentname_id " \
        "INNER JOIN Require r ON r.package_sha1 = p.sha1header " \
        "WHERE sourcerpm IS NULL AND " \
        "".format(", p.".join(server.package_params)) + " ".join(params_values)

    status, response = server.send_request()
    if status is False:
        return response

    server.add_extra_package_params(['packager', 'branch', 'date'])

    return server.convert_to_json(server.package_params, response)


@app.errorhandler(404)
def page_404(e):
    return "Page not found\n"


if __name__ == '__main__':
    app.run()

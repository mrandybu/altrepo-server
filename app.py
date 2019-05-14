from flask import Flask, request, json
from db_request import DBRequest

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
        db = DBRequest()

        conn = db.get_connection(self._db_connection)
        if conn is False:
            return False

        result = db.send_request(conn, self.request_line)
        if result is False:
            return False

        db.close_connection(conn)

        return result

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

        result = self.send_request()

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
            return 'Unknown arch of package!'

        # check branch
        pbranch = self.get_one_value('branch')
        if pbranch and pbranch not in ['p7', 'p8', 'Sisyphus']:
            return 'Unknown branch!'

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

            if not self.request_line:
                return "Package with params not exists!"

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


if __name__ == '__main__':
    app.run()

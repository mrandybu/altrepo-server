from flask import Flask, request, json
from collections import defaultdict
from logic_server import server
import utils
from utils import func_time, get_helper
from deps_sorting import SortList
from conflict_filter import ConflictFilter

app = Flask(__name__)
logger = utils.get_logger(__name__)


@app.route('/package_info')
@func_time(logger)
def package_info():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    buildtime_action = None

    buildtime_value = server.get_one_value('buildtime', 'i')
    if buildtime_value and buildtime_value not in ['>', '<', '=']:
        buildtime_action = "{} = {}"

    pbranch = server.get_one_value('branch', 's')

    input_params = {
        'sha1': {
            'rname': 'pkgcs',
            'type': 's',
            'action': None,
            'notenpty': False,
        },
        'name': {
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'version': {
            'rname': 'version',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'release': {
            'rname': 'release',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'arch': {
            'rname': 'arch',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'disttag': {
            'rname': 'disttag',
            'type': 's',
            'action': None,
            'notempty': False,
        },
        'buildtime': {
            'rname': 'buildtime',
            'type': 'i',
            'action': buildtime_action,
            'notempty': False,
        },
        'source': {
            'rname': 'sourcepackage',
            'type': 'b',
            'action': None,
            'notempty': False,
        },
        'packager': {
            'rname': 'name',
            'type': 's',
            'action': None,
            'notempty': False,
        },
    }

    params_values = server.get_values_by_params(input_params)
    if params_values is False:
        return get_helper(server.helper(request.path))

    full = bool(server.get_one_value('full', 'b'))

    output_params = [
        'pkgcs', 'packager', 'packager_email', 'name',
        'arch', 'version', 'release', 'epoch', 'buildtime',
        'sourcepackage', 'sourcerpm', 'filename',
    ]
    if full:
        output_params = server.package_params

    server.request_line = \
        "SELECT pkg.pkghash, {p_params} FROM last_packages WHERE " \
        "{p_values} {branch}".format(
            p_params=", ".join(output_params),
            p_values=" ".join(params_values),
            branch='{}'
        )

    if pbranch:
        server.request_line = server.request_line.format(
            "AND assigment_name = %(branch)s"
        )
    else:
        server.request_line = server.request_line.format('')

    server.request_line = (server.request_line, {'branch': pbranch})

    status, response = server.send_request()
    if status is False:
        return response

    json_retval = json.loads(
        utils.convert_to_json(['pkghash'] + output_params, response)
    )

    if full:

        pkghashs = utils.join_tuples(response)

        # files
        server.request_line = (
            "SELECT pkghash, filename FROM File WHERE pkghash IN %(pkghshs)s",
            {'pkghshs': pkghashs}
        )

        status, response = server.send_request()
        if status is False:
            return response

        files_dict = utils.tuplelist_to_dict(response, 1)

        # depends
        server.request_line = (
            "SELECT pkghash, dptype, dpname, dpversion FROM last_depends "
            "WHERE pkghash IN %(pkghshs)s", {'pkghshs': pkghashs}
        )

        status, response = server.send_request()
        if status is False:
            return response

        depends_dict = utils.tuplelist_to_dict(response, 3)

        for elem in json_retval:
            pkghash = json_retval[elem]['pkghash']

            json_retval[elem]['files'] = files_dict[pkghash]

            prop_dict_values = utils.tuplelist_to_dict(depends_dict[pkghash], 2)

            for prop in ['require', 'conflict', 'obsolete', 'provide']:
                if prop in prop_dict_values.keys():
                    json_retval[elem][prop + 's'] = [
                        nv[0] + " " + nv[1] for nv in prop_dict_values[prop]
                    ]

    # remove pkghash from result
    for value in json_retval.values():
        value.pop('pkghash', None)

    return json.dumps(json_retval, sort_keys=False)


@app.route('/misconflict_packages')
@func_time(logger)
def conflict_packages():
    """
    The function of searching for conflicting files in packages that do not have
    a conflict.

    Input GET params:
        pkg_ls * - package or list of packages
        task ** - task id
        branch (* - for pkg_ls only) - name of repository
        arch - package architectures

    Output structure:
        input package
        conflict package
        version
        release
        epoch
        architectures
        files with conflict
    """
    server.url_logging()

    check_params = server.check_input_params(source=0)
    if check_params is not True:
        return check_params

    values = server.get_dict_values(
        [('pkg_ls', 's'), ('task', 'i'), ('branch', 's'), ('arch', 's')]
    )

    if values['pkg_ls'] and values['task']:
        return utils.json_str_error("One parameter only. ('name'/'task')")

    if not values['pkg_ls'] and not values['task']:
        return utils.json_str_error("'pkg_ls' or 'task' is require parameters.")

    if values['pkg_ls'] and not values['branch']:
        return get_helper(server.helper(request.path))

    if values['arch']:
        allowed_archs = values['arch'].split(',')
        if 'noarch' not in allowed_archs:
            allowed_archs.append('noarch')
    else:
        allowed_archs = server.default_archs

    allowed_archs = tuple(allowed_archs)

    # prepare packages list from Task
    if values['task']:
        # get branch of task
        server.request_line = (
            "SELECT DISTINCT branch FROM Tasks WHERE task_id = %(task)d",
            {'task': values['task']}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error(
                "Task {task} not found!".format(task=values['task'])
            )

        pbranch = response[0][0]

        # get packages of task (hashes)
        server.request_line = (
            "SELECT pkgs FROM Tasks WHERE task_id = %(task)d",
            {'task': values['task']}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error(
                "Error: Packages in task {task} not found!"
                "".format(task=values['task'])
            )

        # joining tuples from response list
        input_pkg_hshs = []
        for block in response:
            for hsh in block[0]:
                input_pkg_hshs.append(hsh)

    # package list without task
    else:
        pkg_ls = tuple(values['pkg_ls'].split(','))
        pbranch = values['branch']

        # get hash for package names
        server.request_line = (
            "SELECT pkghash, name FROM last_packages WHERE name IN %(pkgs)s "
            "AND assigment_name = %(branch)s AND sourcepackage = 0 AND arch "
            "IN %(arch)s", {
                'pkgs': tuple(pkg_ls), 'branch': pbranch, 'arch': allowed_archs
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error(
                "Error: Packages {pkgs} not found in pkgset {branch}!".format(
                    pkgs=pkg_ls, branch=pbranch
                )
            )

        # check the existence of a package by comparing the number of input
        # and selected from database
        if len(set([pkg[1] for pkg in response])) != len(pkg_ls):
            return utils.json_str_error("Error of input data.")

        # form a list of package hashes
        input_pkg_hshs = [pkg[0] for pkg in response]

    # get list of (input package | conflict package | conflict files)
    server.request_line = (
        "SELECT InPkg.pkghash, pkghash, groupUniqArray(filename) FROM (SELECT "
        "pkghash, filename, hashname FROM File WHERE hashname IN (SELECT "
        "hashname FROM File WHERE pkghash IN %(hshs)s AND fileclass != "
        "'directory') AND pkghash IN (SELECT pkghash FROM last_packages WHERE "
        "assigment_name = %(branch)s AND sourcepackage = 0 AND arch IN "
        "%(arch)s AND pkghash NOT IN %(hshs)s )) LEFT JOIN (SELECT pkghash, "
        "hashname FROM File WHERE pkghash IN %(hshs)s) AS InPkg USING "
        "hashname GROUP BY (InPkg.pkghash, pkghash)", {
            'hshs': tuple(input_pkg_hshs), 'branch': pbranch,
            'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    hshs_files = response

    # list of conflicting package pairs
    in_confl_hshs = [(hsh[0], hsh[1]) for hsh in hshs_files]

    # filter conflicts by provides/conflicts
    c_filter = ConflictFilter(pbranch, allowed_archs)

    # check for the presence of the specified conflict each pair
    # if the conflict between the packages in the pair is specified,
    # then add the pair to the list
    filter_ls = []
    for tp_hsh in in_confl_hshs:
        confl_ls = c_filter.detect_conflict(tp_hsh[0], tp_hsh[1])
        for confl in confl_ls:
            if confl not in filter_ls:
                filter_ls.append(confl)

    # get a list of hashes of packages to form a dict of hash-name
    pkg_hshs = utils.remove_duplicate(
        [hsh[0] for hsh in hshs_files] + [hsh[1] for hsh in hshs_files]
    )

    # get package names by hashes
    server.request_line = (
        "SELECT pkghash, name FROM last_packages WHERE pkghash IN %(pkgs)s "
        "AND assigment_name = %(branch)s AND sourcepackage = 0 AND arch IN "
        "%(arch)s", {
            'pkgs': tuple(pkg_hshs), 'branch': pbranch, 'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    hsh_name_dict = utils.tuplelist_to_dict(response, 1)

    # get names of input packages
    input_packages = []
    for hsh, name in hsh_name_dict.items():
        if hsh in input_pkg_hshs:
            input_packages.append(name)

    input_packages = utils.remove_duplicate(utils.join_tuples(input_packages))

    # convert the hashes into names, put in the first place in the pair
    # the name of the input package, if it is not
    filter_ls_names = []
    for hsh in filter_ls:
        inp_pkg = hsh_name_dict[hsh[1]][0]
        if inp_pkg not in input_packages:
            inp_pkg = hsh_name_dict[hsh[0]][0]
            filter_ls_names.append((inp_pkg, hsh_name_dict[hsh[1]][0]))
        else:
            filter_ls_names.append((inp_pkg, hsh_name_dict[hsh[0]][0]))

    # form the list of tuples (input package | conflict package | conflict files)
    result_list = []
    for pkg in hshs_files:
        pkg = (hsh_name_dict[pkg[0]][0], hsh_name_dict[pkg[1]][0], pkg[2])
        if pkg not in result_list:
            result_list.append(pkg)

    # look for duplicate pairs of packages in the list with different files
    # and join them
    result_list_cleanup = []
    for pkg in result_list:
        files = list(pkg[2])
        for pkg_next in result_list:
            if (pkg[0], pkg[1]) == (pkg_next[0], pkg_next[1]):
                for file in pkg_next[2]:
                    files.append(file)

        files = sorted(utils.remove_duplicate(files))

        pkg = (pkg[0], pkg[1], files)
        if pkg not in result_list_cleanup:
            result_list_cleanup.append(pkg)

    confl_pkgs = utils.remove_duplicate([pkg[1] for pkg in result_list_cleanup])

    # get main information of packages by package hashes
    server.request_line = (
        "SELECT name, version, release, epoch, groupUniqArray(arch) FROM "
        "last_packages WHERE name IN %(pkgs)s AND assigment_name = %(branch)s "
        "AND sourcepackage = 0 AND arch IN %(arch)s GROUP BY (name, version, "
        "release, epoch)", {
            'pkgs': tuple(confl_pkgs), 'branch': pbranch, 'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    # form dict name - package info
    name_info_dict = {}
    for pkg in response:
        name_info_dict[pkg[0]] = pkg[1:]

    # form list of tuples (input pkg | conflict pkg | pkg info | conflict files)
    # and filter it
    result_list_info = []
    for pkg in result_list_cleanup:
        if (pkg[0], pkg[1]) not in filter_ls_names:
            pkg = (pkg[0], pkg[1]) + name_info_dict[pkg[1]] + (pkg[2],)
            result_list_info.append(pkg)

    return utils.convert_to_json(
        ['input_package', 'conflict_package', 'version', 'release', 'epoch',
         'archs', 'files_with_conflict'], result_list_info
    )


@app.route('/package_by_file')
@func_time(logger)
def package_by_file():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    file = server.get_one_value('file', 'r')
    md5 = server.get_one_value('md5', 's')

    if len([param for param in [file, md5] if param]) != 1:
        return get_helper(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        return utils.json_str_error('Branch require parameter!')

    arch = server.get_one_value('arch', 's')
    if arch:
        arch = (arch, 'noarch')
    else:
        arch = server.known_archs

    pkghash = \
        "SELECT pkg.pkghash FROM last_packages WHERE " \
        "assigment_name = %(branch)s AND arch IN %(arch)s"

    base_query = \
        "SELECT pkghash{in_} FROM File WHERE pkghash IN ({pkghash}) AND " \
        "{param}".format(in_='{}', pkghash=pkghash, param='{}')

    if file:
        elem, query = file, "filename LIKE %(elem)s"
    else:
        elem, query = md5, "filemd5 = %(elem)s"

    server.request_line = (
        base_query.format(', filename', query),
        {'branch': pbranch, 'arch': tuple(arch), 'elem': elem}
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    ids_filename_dict = utils.tuplelist_to_dict(response, 1)

    pkghashs = tuple([key for key in ids_filename_dict.keys()])

    server.request_line = (
        "SELECT pkghash, pkgcs, name, version, release, disttag, arch, "
        "assigment_name FROM last_packages WHERE sourcepackage = 0 AND "
        "pkghash IN %(hashs)s AND assigment_name = %(branch)s",
        {'hashs': pkghashs, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    output_values = []
    for package in response:
        package += (ids_filename_dict[package[0]],)
        output_values.append(package[1:])

    output_params = ['pkgcs', 'name', 'version', 'release',
                     'disttag', 'arch', 'branch', 'files']

    return utils.convert_to_json(output_params, tuple(output_values))


@app.route('/package_files')
@func_time(logger)
def package_files():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    sha1 = server.get_one_value('sha1', 's')
    if not sha1:
        return get_helper(server.helper(request.path))

    server.request_line = (
        "SELECT filename FROM File WHERE pkghash = murmurHash3_64(%(sha1)s)",
        {'sha1': sha1}
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return utils.json_str_error(
            "Files not found by sha1 '{}'".format(sha1)
        )

    js = {
        'sha1': sha1,
        'files': [file[0] for file in response],
    }

    return json.dumps(js, sort_keys=False)


@app.route('/dependent_packages')
@func_time(logger)
def dependent_packages():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    if not pname:
        return get_helper(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        message = 'Branch is required parameter.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = (
        "SELECT DISTINCT name, version, release, epoch, serial_, filename "
        "AS sourcerpm, assigment_name, groupUniqArray(binary_arch) FROM "
        "last_packages INNER JOIN (SELECT sourcerpm, arch AS binary_arch FROM "
        "last_packages WHERE name IN (SELECT DISTINCT pkgname FROM last_depends "
        "WHERE dpname IN (SELECT dpname FROM last_depends WHERE pkgname = "
        "%(name)s AND dptype = 'provide' AND assigment_name = %(branch)s AND "
        "sourcepackage = 0) AND assigment_name = %(branch)s AND sourcepackage "
        "= 0) AND assigment_name = %(branch)s AND sourcepackage = 0) USING "
        "sourcerpm WHERE assigment_name = %(branch)s AND sourcepackage = 1 "
        "GROUP BY (name, version, release, epoch, serial_, filename AS "
        "sourcerpm, assigment_name)", {'name': pname, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    js_keys = ['name', 'version', 'release', 'epoch', 'serial', 'sourcerpm',
               'branch', 'archs']

    return utils.convert_to_json(js_keys, response)


@app.route('/what_depends_src')
@func_time(logger)
def what_depends_build():
    """
    The function of searching build dependencies.

    The function search build dependencies of package, list packages or
    packages from task. Also function can also use such parameters like as
    leaf, searching depth.

    Input GET params:
        name * - package or list of packages
        task ** - task id
        branch (* - for pkg_ls only) - name of repository
        arch - package architectures
        leaf - assembly dependency chain
        deep - sorting depth
        dptype - type of package (source, binary, both)

    Output structure:
        name
        version
        release
        epoch
        serial
        source package
        branch
        architectures
        cycle dependencies
    """
    server.url_logging()

    check_params = server.check_input_params(source=1)
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    task_id = server.get_one_value('task', 'i')

    depends_type_to_sql = {
        'source': (1,),
        'binary': (0,),
        'both': (1, 0)
    }

    depends_type = server.get_one_value('dptype', 's')
    if depends_type not in depends_type_to_sql:
        depends_type = 'both'

    sourcef = depends_type_to_sql[depends_type]

    message = None
    if pname and task_id:
        message = "Only one parameter package 'name' or build 'task'."
    elif not pname and not task_id:
        message = "Source package 'name' or build 'task' " \
                  "is require parameters."

    if message:
        logger.debug(message)
        return utils.json_str_error(message)

    pbranch = server.get_one_value('branch', 's')
    if pname and not pbranch:
        return get_helper(server.helper(request.path))

    arch = server.get_one_value('arch', 's')
    if arch:
        arch = [arch]
        if 'noarch' not in arch:
            arch.append('noarch')
    else:
        arch = ['x86_64', 'noarch']

    # tree leaf - show only build path between 'name' and 'leaf'
    leaf = server.get_one_value('leaf', 's')
    if leaf and task_id:
        return utils.json_str_error("'leaf' may be using with 'name' only.")

    # process this query for task
    if task_id:
        # get the branch name from task
        server.request_line = (
            "SELECT DISTINCT branch FROM Tasks WHERE task_id = %(id)s",
            {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error('Unknown task id.')

        # branch from task
        pbranch = response[0][0]

        # get the packages hashes from Task
        server.request_line = (
            "SELECT pkgs FROM Tasks WHERE task_id = %(id)s", {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        # join list of tuples of tuples
        pkgs_hsh = ()
        for tp_package in response:
            for package in tp_package[0]:
                pkgs_hsh += (package,)

        # src packages from task
        server.request_line = (
            "SELECT DISTINCT name FROM Package WHERE filename IN (SELECT "
            "DISTINCT sourcerpm FROM Package WHERE pkghash IN %(pkghshs)s)"
            "", {'pkghshs': pkgs_hsh}
        )

        status, response = server.send_request()
        if status is False:
            return response

        input_pkgs = utils.join_tuples(response)

    # without task - get the packages name from URL
    else:
        input_pkgs = (pname,)

    # deep level for recursive requires search
    deep_level = server.get_one_value('deep', 'i')
    if not deep_level:
        deep_level = 1

    tmp_table_name = 'tmp_pkg_ls'

    # create tmp table with list of packages
    server.request_line = "CREATE TEMPORARY TABLE {tmp_table} (pkgname String)" \
                          "".format(tmp_table=tmp_table_name)

    status, response = server.send_request()
    if status is False:
        return response

    # base query - first iteration, build requires depth 1
    server.request_line = (
        "INSERT INTO {tmp_table} SELECT DISTINCT name FROM Package WHERE "
        "(filename IN (SELECT DISTINCT if(sourcepackage = 1, filename, sourcerpm) "
        "AS sourcerpm from Package WHERE pkghash IN (SELECT DISTINCT pkghash FROM "
        "last_depends WHERE dpname IN (SELECT dpname FROM Depends WHERE pkghash "
        "IN (SELECT pkghash FROM last_packages_with_source WHERE sourcepkgname "
        "IN %(pkgs)s AND assigment_name = %(branch)s AND arch IN ('x86_64', "
        "'noarch') AND name NOT LIKE '%%-debuginfo') AND dptype='provide') AND "
        "assigment_name = %(branch)s AND sourcepackage IN %(sfilter)s AND "
        "dptype = 'require' AND pkgname NOT LIKE '%%-debuginfo'))) AND "
        "sourcepackage = 1 UNION ALL SELECT arrayJoin(%(union)s)"
        "".format(tmp_table=tmp_table_name), {
            'sfilter': sourcef, 'pkgs': input_pkgs, 'branch': pbranch,
            'union': list(input_pkgs)
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    if deep_level > 1:
        if deep_level > 4:
            return utils.json_str_error("Requires Depth cannot exceed 4")

        # sql wrapper for increase depth
        deep_wrapper = \
            "SELECT pkghash FROM last_depends WHERE dpname IN (SELECT dpname " \
            "FROM Depends WHERE pkghash IN (SELECT pkghash FROM " \
            "last_packages_with_source WHERE sourcepkgname IN (SELECT * FROM " \
            "{tmp_table}) AND assigment_name = %(branch)s AND arch IN ('x86_64', " \
            "'noarch') AND name NOT LIKE '%%-debuginfo') AND dptype='provide') " \
            "AND assigment_name = %(branch)s AND dptype = 'require' AND " \
            "sourcepackage IN %(sfilter)s".format(tmp_table=tmp_table_name)

        # process depth for every level and add results to pkg_ls
        for i in range(deep_level - 1):
            server.request_line = (
                "INSERT INTO {tmp_table} (pkgname) SELECT DISTINCT * FROM ("
                "SELECT name FROM Package WHERE (filename IN (SELECT DISTINCT "
                "if(sourcepackage = 1, filename, sourcerpm) AS sourcerpm from "
                "Package WHERE pkghash IN ({wrapper}))) AND sourcepackage = 1 "
                "UNION ALL (SELECT * FROM {tmp_table}))".format(
                    wrapper=deep_wrapper, tmp_table=tmp_table_name
                ), {'sfilter': sourcef, 'branch': pbranch}
            )

            status, response = server.send_request()
            if status is False:
                return response

    pkgs_to_sort_dict = None

    # get source dependencies
    if depends_type in ['source', 'both']:
        # get requires tree for found packages
        server.request_line = (
            "SELECT DISTINCT BinDeps.pkgname, arrayFilter(x -> (x != BinDeps.pkgname "
            "AND notEmpty(x)), groupUniqArray(sourcepkgname)) AS srcarray FROM ("
            "SELECT DISTINCT BinDeps.pkgname, name AS pkgname, sourcepkgname FROM "
            "last_packages_with_source INNER JOIN (SELECT DISTINCT BinDeps.pkgname, "
            "pkgname FROM (SELECT DISTINCT BinDeps.pkgname, pkgname, dpname FROM "
            "last_depends INNER JOIN (SELECT DISTINCT pkgname, dpname FROM "
            "last_depends WHERE pkgname IN (SELECT '' UNION ALL SELECT * FROM "
            "{tmp_table}) AND assigment_name = %(branch)s AND dptype = 'require' "
            "AND sourcepackage = 1) AS BinDeps USING dpname WHERE assigment_name = "
            "%(branch)s AND dptype = 'provide' AND sourcepackage = 0 AND arch IN "
            "('x86_64', 'noarch'))) USING pkgname WHERE assigment_name = %(branch)s "
            "ORDER BY sourcepkgname ASC UNION ALL SELECT arrayJoin(%(union)s), '', '') "
            "WHERE sourcepkgname IN (SELECT '' UNION ALL SELECT * FROM {tmp_table}) "
            "GROUP BY BinDeps.pkgname ORDER BY length(srcarray)".format(
                tmp_table=tmp_table_name
            ), {'union': list(input_pkgs), 'branch': pbranch}
        )

        status, response = server.send_request()
        if status is False:
            return response

        # form dict input package name - dependencies
        name_reqs_dict = {}
        for elem in response:
            name_reqs_dict[elem[0]] = [req for req in elem[1] if req != '']

        # cleanup source dependencies
        pkgs_to_sort_dict = utils.remove_values_not_in_keys(name_reqs_dict)

    # get binary dependencies
    if depends_type in ['binary', 'both']:
        # get binary package dependencies
        server.request_line = (
            "SELECT sourcepkgname, groupUniqArray(Bin.sourcepkgname) FROM (SELECT "
            "sourcepkgname, name AS pkgname, Bin.sourcepkgname FROM "
            "last_packages_with_source INNER JOIN (SELECT pkgname, sourcepkgname "
            "FROM (SELECT DISTINCT pkgname, Prv.pkgname AS dpname, "
            "Src.sourcepkgname FROM (SELECT pkgname, dpname, Prv.pkgname FROM ("
            "SELECT DISTINCT pkgname, dpname FROM last_depends WHERE pkgname IN ("
            "SELECT DISTINCT name FROM last_packages_with_source WHERE "
            "sourcepkgname IN (SELECT * FROM {tmp_table}) AND assigment_name = "
            "%(branch)s AND arch IN %(archs)s AND name NOT LIKE '%%-debuginfo') AND "
            "dptype = 'require' AND assigment_name = %(branch)s AND arch IN %(archs)s "
            "AND sourcepackage = 0) INNER JOIN (SELECT dpname, pkgname FROM "
            "last_depends WHERE dptype = 'provide' AND assigment_name = %(branch)s "
            "AND sourcepackage = 0 AND arch IN %(archs)s) AS Prv USING dpname) "
            "INNER JOIN (SELECT name as dpname, sourcepkgname FROM "
            "last_packages_with_source WHERE assigment_name = %(branch)s AND arch "
            "IN %(archs)s) Src USING dpname)) AS Bin USING pkgname WHERE "
            "assigment_name = %(branch)s AND arch IN %(archs)s) GROUP BY ("
            "sourcepkgname)".format(tmp_table=tmp_table_name), {
                'branch': pbranch, 'archs': tuple(arch)
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

        name_reqs_dict_binary = utils.tuplelist_to_dict(response, 1)

        # cleanup binary dependencies
        name_reqs_dict_binary = utils.remove_values_not_in_keys(
            name_reqs_dict_binary
        )

        # if source and binary dependencies - join it
        if pkgs_to_sort_dict:
            pkgs_to_sort_dict = utils.join_dicts(
                name_reqs_dict_binary, pkgs_to_sort_dict
            )
        else:
            pkgs_to_sort_dict = name_reqs_dict_binary

    if not pkgs_to_sort_dict:
        return json.dumps({})

    # check leaf, if true, get dependencies of leaf package
    if leaf:
        if leaf not in pkgs_to_sort_dict.keys():
            return utils.json_str_error(
                "Package '{}' not in dependencies list.".format(leaf)
            )
        else:
            leaf_deps = pkgs_to_sort_dict[leaf]

    # sort list of dependencies by their dependencies
    sort = SortList(pkgs_to_sort_dict, pname)
    circle_deps, sorted_list = sort.sort_list()

    # form dict package - its circle dependencies
    circle_deps_dict = {}
    for c_dep in circle_deps:
        if c_dep[0] not in circle_deps_dict.keys():
            circle_deps_dict[c_dep[0]] = []
        circle_deps_dict[c_dep[0]].append(c_dep[1])

    # remove the name of the dependent package from the list of its
    # circle dependencies
    for name, deps in circle_deps_dict.items():
        if name in deps:
            deps.remove(name)
        # if sorted list instead of the package name add tuple
        # (pkg name, list of circle dependencies)
        for pac in sorted_list:
            if pac == name:
                sorted_list[sorted_list.index(pac)] = (pac, deps)

    # form dict pkg name - circle dependencies
    result_dict = {}
    for package in sorted_list:
        if isinstance(package, tuple):
            result_dict[package[0]] = package[1]
        else:
            result_dict[package] = []

    # if leaf, then select packages from the result list and their cyclic
    # dependencies on which the leaf package and create a dictionary
    if leaf:
        result_dict_leaf = defaultdict(list)
        result_dict_leaf[pname] = []

        for package, c_deps in result_dict.items():
            if package in leaf_deps:
                if c_deps:
                    for dep in c_deps:
                        if dep in leaf_deps:
                            result_dict_leaf[package].append(dep)
                else:
                    result_dict_leaf[package] = []

        result_dict_leaf[leaf] = []

        result_dict = result_dict_leaf

    # list of result package names
    sorted_pkgs = tuple(result_dict.keys())

    # get output data for sorted package list
    server.request_line = (
        "SELECT DISTINCT SrcPkg.name, SrcPkg.version, SrcPkg.release, "
        "SrcPkg.epoch, SrcPkg.serial_, sourcerpm AS filename, assigment_name, "
        "groupUniqArray(arch), CAST(toDateTime(any(SrcPkg.buildtime)), 'String') "
        "AS buildtime_str FROM last_packages INNER JOIN (SELECT name, version, "
        "release, epoch, serial_, filename, assigment_name, buildtime FROM "
        "last_packages WHERE name IN (SELECT * FROM {tmp_table}) AND "
        "assigment_name = %(branch)s AND sourcepackage = 1) AS SrcPkg USING "
        "filename WHERE assigment_name = %(branch)s AND sourcepackage = 0 "
        "GROUP BY (SrcPkg.name, SrcPkg.version, SrcPkg.release, SrcPkg.epoch, "
        "SrcPkg.serial_, filename, assigment_name)"
        "".format(tmp_table=tmp_table_name), {'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    # add circle requires in package info
    pkg_info_list = []
    for info in response:
        for pkg, c_deps in result_dict.items():
            if info[0] == pkg:
                pkg_info_list.append(info + (c_deps,))

    reqfilter = server.get_one_value('reqfilter', 's')

    filter_pkgs = None
    if reqfilter:
        server.request_line = (
            "SELECT sourcepkgname FROM last_packages_with_source WHERE name IN "
            "(SELECT DISTINCT * FROM (SELECT pkgname FROM last_depends WHERE "
            "dpname IN (SELECT dpname FROM last_depends WHERE pkgname = "
            "%(filter)s AND dptype = 'provide' AND assigment_name = %(branch)s "
            "AND sourcepackage = 0 AND arch IN %(archs)s) AND dptype = 'require' "
            "AND assigment_name = %(branch)s AND sourcepackage IN (0, 1) AND "
            "pkgname IN (SELECT DISTINCT name FROM (SELECT name FROM "
            "last_packages_with_source WHERE sourcepkgname IN (SELECT * FROM "
            "{tmp_table}) AND assigment_name = %(branch)s AND sourcepackage = 0 "
            "AND arch IN %(archs)s AND name NOT LIKE '%%-debuginfo' UNION ALL "
            "SELECT name FROM Package WHERE name IN (SELECT * FROM {tmp_table}"
            "))))) AND assigment_name = %(branch)s AND arch IN %(archs)s"
            "".format(tmp_table=tmp_table_name), {
                'filter': reqfilter, 'branch': pbranch, 'archs': tuple(arch)
            }
        )

        status, response = server.send_request()
        if status is False:
            return response

        filter_pkgs = utils.join_tuples(response)

    # sort pkg info list
    sorted_dict = {}
    for pkg in pkg_info_list:
        if (reqfilter and pkg[0] in filter_pkgs) or not reqfilter:
            if task_id:
                if pkg[0] not in input_pkgs:
                    sorted_dict[sorted_pkgs.index(pkg[0])] = pkg
            else:
                sorted_dict[sorted_pkgs.index(pkg[0])] = pkg

    sorted_dict = list(dict(sorted(sorted_dict.items())).values())

    js_keys = ['name', 'version', 'release', 'epoch', 'serial_', 'sourcerpm',
               'branch', 'archs', 'buildtime', 'cycle']

    return utils.convert_to_json(js_keys, sorted_dict)


@app.route('/unpackaged_dirs')
@func_time(logger)
def unpackaged_dirs():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    values = server.get_dict_values(
        [('pkgr', 's'), ('pkgset', 's'), ('arch', 's')]
    )

    if not values['pkgr'] or not values['pkgset']:
        return get_helper(server.helper(request.path))

    parch = server.default_archs
    if values['arch']:
        parch = values['arch'].split(',')
        if 'noarch' not in parch:
            parch.append('noarch')

    server.request_line = (
        "SELECT DISTINCT Pkg.pkgname, extract(filename, '^(.+)/([^/]+)$') AS "
        "dir, Pkg.version, Pkg.release, Pkg.epoch, Pkg.packager, "
        "Pkg.packager_email, groupUniqArray(Pkg.arch) FROM File LEFT JOIN ("
        "SELECT pkghash, name as pkgname, version, release, epoch, disttag, "
        "packager_email, packager, arch FROM Package) AS Pkg USING pkghash "
        "WHERE empty(fileclass) AND (pkghash IN (SELECT pkghash FROM "
        "last_packages WHERE (assigment_name = %(branch)s) AND packager_email "
        "LIKE %(email)s AND (sourcepackage = 0) AND (arch IN %(archs)s))) AND "
        "(hashdir NOT IN (SELECT hashname FROM File WHERE (fileclass = "
        "'directory') AND (pkghash IN (SELECT pkghash FROM last_packages WHERE "
        "(assigment_name = %(branch)s) AND (sourcepackage = 0) AND (arch IN "
        "%(archs)s))))) GROUP BY (Pkg.pkgname, dir, Pkg.version, Pkg.release, "
        "Pkg.epoch, Pkg.packager, Pkg.packager_email) ORDER BY packager_email",
        {
            'branch': values['pkgset'], 'email': '{}@%'.format(values['pkgr']),
            'archs': tuple(parch)
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    js_keys = ['package', 'directory', 'version', 'release', 'epoch',
               'packager', 'email', 'arch']

    return utils.convert_to_json(js_keys, response)


@app.route('/repo_compare')
@func_time(logger)
def repo_compare():
    server.url_logging()

    check_params = server.check_input_params()
    if check_params is not True:
        return check_params

    values = server.get_dict_values([('pkgset1', 's'), ('pkgset2', 's')])

    if not values['pkgset1'] or not values['pkgset2']:
        return get_helper(server.helper(request.path))

    server.request_line = (
        "SELECT name, version, release, Df.name, Df.version, Df.release FROM "
        "(SELECT name, version, release FROM last_packages WHERE "
        "assigment_name = %(pkgset1)s AND sourcepackage = 1 AND (name, "
        "version, release) NOT IN (SELECT name, version, release FROM "
        "last_packages WHERE assigment_name = %(pkgset2)s AND "
        "sourcepackage = 1) AND name IN (SELECT name FROM last_packages WHERE "
        "assigment_name = %(pkgset2)s AND sourcepackage = 1)) INNER JOIN "
        "(SELECT name, version, release FROM last_packages WHERE "
        "assigment_name = %(pkgset2)s AND sourcepackage = 1) AS Df USING name "
        "UNION ALL SELECT name, version, release, '', '', '' FROM last_packages "
        "WHERE assigment_name = %(pkgset1)s AND sourcepackage = 1 AND name "
        "NOT IN (SELECT name FROM last_packages WHERE assigment_name = "
        "%(pkgset2)s AND sourcepackage = 1)", {
            'pkgset1': values['pkgset1'], 'pkgset2': values['pkgset2']
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    result_dict = {}
    for i in range(len(response)):
        iter_elem = response[i]
        result_dict[i] = {
            values['pkgset1']: {
                'name': iter_elem[0], 'version': iter_elem[1],
                'release': iter_elem[2]
            },
            values['pkgset2']: {
                'name': iter_elem[3], 'version': iter_elem[4],
                'release': iter_elem[5]
            }
        }

    if not response:
        return json.dumps({})

    return json.dumps(result_dict, sort_keys=False)


@app.teardown_request
def drop_connection(connection):
    server.drop_connection()


@app.errorhandler(404)
def page_404(error):
    helper = {
        'Error': error.description,
        'Valid queries': {
            '/package_info': 'information about given package',
            '/misconflict_packages': 'binary packages with intersecting '
                                     'files and no conflict with a given package',
            '/package_by_file': 'binary packages that contain the specified file',
            '/package_files': 'files by current sha1 of package',
            '/dependent_packages': 'source packages whose binary packages '
                                   'depend on the given package',
            '/what_depends_src': 'source packages with build dependency on a '
                                 'given package',
            '/unpackaged_dirs': 'list of unpacked directories',
            '/repo_compare': 'list of differences in the package base of '
                             'specified repositories',
        }
    }
    return json.dumps(helper, sort_keys=False)


if __name__ == '__main__':
    app.run()

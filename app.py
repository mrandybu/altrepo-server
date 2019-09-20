from flask import Flask, request, json
from collections import defaultdict
from logic_server import server
import utils
from utils import func_time
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

    intput_params = {
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

    params_values = server.get_values_by_params(intput_params)
    if params_values is False:
        return json.dumps(server.helper(request.path))

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
        return json.dumps(server.helper(request.path))

    if values['arch']:
        allowed_archs = values['arch'].split(',')
        if 'noarch' not in allowed_archs:
            allowed_archs.append('noarch')
    else:
        allowed_archs = server.default_archs

    allowed_archs = tuple(allowed_archs)

    # prepare packages list from Task
    if values['task']:
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

        pkg_hshs = []
        for block in response:
            for hsh in block[0]:
                pkg_hshs.append(hsh)

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

        if len(set([pkg[1] for pkg in response])) != len(pkg_ls):
            return utils.json_str_error("Error of input data.")

        pkg_hshs = [pkg[0] for pkg in response]

    server.request_line = (
        "SELECT InPkg.pkghash, pkghash, groupUniqArray(filename) FROM (SELECT "
        "pkghash, filename, hashname FROM File WHERE hashname IN (SELECT "
        "hashname FROM File WHERE pkghash IN %(hshs)s AND fileclass != "
        "'directory') AND pkghash IN (SELECT pkghash FROM last_packages WHERE "
        "assigment_name = %(branch)s AND sourcepackage = 0 AND arch IN "
        "%(arch)s AND pkghash NOT IN %(hshs)s )) LEFT JOIN (SELECT pkghash, "
        "hashname FROM File WHERE pkghash IN %(hshs)s) AS InPkg USING "
        "hashname GROUP BY (InPkg.pkghash, pkghash)", {
            'hshs': tuple(pkg_hshs), 'branch': pbranch, 'arch': allowed_archs
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    if not response:
        return json.dumps({})

    hshs_files = response

    in_confl_hshs = [(hsh[0], hsh[1]) for hsh in hshs_files]

    c_filter = ConflictFilter(pbranch, allowed_archs)

    filter_ls = []
    for tp_hsh in in_confl_hshs:
        confl_ls = c_filter.detect_conflict(tp_hsh[0], tp_hsh[1])
        for confl in confl_ls:
            if confl not in filter_ls:
                filter_ls.append(confl)

    pkg_hshs = utils.remove_duplicate(
        [hsh[0] for hsh in hshs_files] + [hsh[1] for hsh in hshs_files]
    )

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

    hsh_name_dict = utils.tuple_to_dict(response)

    filter_ls_names = []
    for hsh in filter_ls:
        filter_ls_names.append(
            (hsh_name_dict[hsh[1]][0], hsh_name_dict[hsh[0]][0])
        )

    result_list = []
    for pkg in hshs_files:
        pkg = (hsh_name_dict[pkg[0]][0], hsh_name_dict[pkg[1]][0], pkg[2])
        if pkg not in result_list:
            result_list.append(pkg)

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

    name_info_dict = {}
    for pkg in response:
        name_info_dict[pkg[0]] = pkg[1:]

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
        return json.dumps(server.helper(request.path))

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

    ids_filename_dict = utils.tuple_to_dict(response)

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
        return json.dumps(server.helper(request.path))

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
        return json.dumps(server.helper(request.path))

    pbranch = server.get_one_value('branch', 's')
    if not pbranch:
        message = 'Branch is required parameter.'
        logger.debug(message)
        return utils.json_str_error(message)

    server.request_line = (
        "SELECT DISTINCT name, version, release, epoch, serial_, filename "
        "AS sourcerpm, assigment_name, groupUniqArray(binary_arch) FROM "
        "last_packages INNER JOIN (SELECT sourcerpm, arch AS binary_arch "
        "FROM last_packages WHERE name IN (SELECT DISTINCT pkgname FROM "
        "last_depends WHERE dpname IN (SELECT dpname FROM last_depends "
        "WHERE pkgname = %(name)s AND dptype = 'provide' AND "
        "assigment_name = %(branch)s AND sourcepackage = 0) AND "
        "assigment_name = %(branch)s AND sourcepackage = 0) AND "
        "assigment_name = %(branch)s AND sourcepackage = 0) USING sourcerpm "
        "WHERE assigment_name = %(branch)s AND sourcepackage = 1 GROUP BY "
        "(name, version, release, epoch, serial_, filename AS sourcerpm, "
        "assigment_name)", {'name': pname, 'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    js_keys = ['name', 'version', 'release', 'epoch', 'serial', 'sourcerpm',
               'branch', 'archs']

    return utils.convert_to_json(js_keys, response)


@app.route('/what_depends_src')
@func_time(logger)
def broken_build():
    server.url_logging()

    check_params = server.check_input_params(source=1)
    if check_params is not True:
        return check_params

    pname = server.get_one_value('name', 's')
    task_id = server.get_one_value('task', 'i')

    message = None
    if pname and task_id:
        message = "Only one parameter 'name' or 'task'."
    elif not pname and not task_id:
        message = "'name' or 'task' is require parameters."

    if message:
        logger.debug(message)
        return utils.json_str_error(message)

    pbranch = server.get_one_value('branch', 's')
    if pname and not pbranch:
        return json.dumps(server.helper(request.path))

    arch = server.get_one_value('arch', 's')
    if arch:
        arch = [arch]
        if 'noarch' not in arch:
            arch.append('noarch')

    leaf = server.get_one_value('leaf', 's')
    if leaf and task_id:
        return utils.json_str_error("'leaf' may be using with 'name' only.")

    if task_id:
        # branch name
        server.request_line = (
            "SELECT DISTINCT branch FROM Tasks WHERE task_id = %(id)s",
            {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

        if not response:
            return utils.json_str_error('Unknown task id.')

        pbranch = response[0][0]

        server.request_line = (
            "SELECT pkgs FROM Tasks WHERE task_id = %(id)s", {'id': task_id}
        )

        status, response = server.send_request()
        if status is False:
            return response

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

    else:
        input_pkgs = (pname,)

    deep_level = server.get_one_value('deep', 'i')
    if not deep_level:
        deep_level = 1

    # base query
    server.request_line = (
        "SELECT DISTINCT pkgname FROM last_depends WHERE dpname IN "
        "(SELECT name FROM last_packages_with_source WHERE "
        "sourcepkgname IN %(pkgs)s AND assigment_name = %(branch)s AND "
        "arch IN ('x86_64', 'noarch') AND name NOT LIKE '%%-debuginfo') "
        "AND assigment_name = %(branch)s AND sourcepackage = 1 AND "
        "dptype = 'require' AND pkgname NOT LIKE '%%-debuginfo' UNION ALL "
        "SELECT arrayJoin(%(union)s)", {
            'pkgs': input_pkgs, 'branch': pbranch, 'union': list(input_pkgs)
        }
    )

    status, response = server.send_request()
    if status is False:
        return response

    pkg_ls = utils.join_tuples(response)

    deep_wrapper = \
        "SELECT DISTINCT pkgname FROM last_depends WHERE dpname IN " \
        "(SELECT DISTINCT name FROM last_packages_with_source WHERE " \
        "sourcepkgname IN %(pkgs)s AND assigment_name = %(branch)s AND " \
        "arch IN ('x86_64', 'noarch') AND name NOT LIKE '%%-debuginfo') " \
        "AND assigment_name = %(branch)s AND dptype = 'require' AND " \
        "sourcepackage = 1"

    if deep_level == 1:
        result_pkg_ls = pkg_ls
    else:

        if deep_level > 3:
            return utils.json_str_error("Deep cannot exceed 3")

        for i in range(deep_level):
            server.request_line = (
                "SELECT DISTINCT pkgname FROM ({} UNION ALL SELECT %(pkgs)s)"
                "".format(deep_wrapper), {
                    'pkgs': tuple(pkg_ls), 'branch': pbranch
                }
            )

            status, response = server.send_request(trace=True)
            if status is False:
                return response

            pkg_ls = utils.join_tuples(response)

    server.request_line = (
        "SELECT DISTINCT BinDeps.pkgname, arrayFilter(x -> (x != "
        "BinDeps.pkgname AND notEmpty(x)), groupUniqArray(sourcepkgname)) "
        "AS srcarray FROM (SELECT DISTINCT BinDeps.pkgname, name AS "
        "pkgname, sourcepkgname FROM last_packages_with_source INNER JOIN "
        "(SELECT DISTINCT BinDeps.pkgname, pkgname FROM (SELECT DISTINCT "
        "BinDeps.pkgname, pkgname, dpname FROM last_depends INNER JOIN "
        "(SELECT DISTINCT pkgname, dpname FROM last_depends WHERE pkgname "
        "IN %(pkgs)s AND assigment_name = %(branch)s AND dptype = 'require' "
        "AND sourcepackage = 1) AS BinDeps USING dpname WHERE "
        "assigment_name = %(branch)s AND dptype = 'provide' AND "
        "sourcepackage = 0 AND arch IN ('x86_64', 'noarch'))) USING "
        "pkgname WHERE assigment_name = %(branch)s ORDER BY sourcepkgname "
        "ASC UNION ALL SELECT arrayJoin(%(union)s), '', '') WHERE "
        "sourcepkgname IN %(pkgs)s GROUP BY BinDeps.pkgname ORDER BY "
        "length(srcarray)",
        {'union': list(input_pkgs), 'pkgs': ('',)+pkg_ls,
         'branch': pbranch}
    )

    status, response = server.send_request()
    if status is False:
        return response

    name_reqs_dict = {}
    for elem in response:
        reqs = [req for req in elem[1] if req != '']
        name_reqs_dict[elem[0]] = reqs

    name_reqs_dict_cleanup = name_reqs_dict

    if leaf:
        if leaf not in name_reqs_dict_cleanup.keys():
            return utils.json_str_error(
                "Package '{}' not in dependencies list.".format(leaf)
            )
        else:
            leaf_deps = name_reqs_dict_cleanup[leaf]

    sort = SortList(name_reqs_dict_cleanup, pname)
    circle_deps, sorted_list = sort.sort_list()

    cleanup_circle_deps = []
    for dp in circle_deps:
        if dp[1] != pname:
            cleanup_circle_deps.append(dp)

    circle_deps = cleanup_circle_deps

    circle_deps_dict = {}
    for c_dep in circle_deps:
        if c_dep[0] not in circle_deps_dict.keys():
            circle_deps_dict[c_dep[0]] = []
        circle_deps_dict[c_dep[0]].append(c_dep[1])

    for name, deps in circle_deps_dict.items():
        if name in deps:
            deps.remove(name)
        for pac in sorted_list:
            if pac == name:
                sorted_list[sorted_list.index(pac)] = (pac, deps)

    result_dict = {}
    for package in sorted_list:
        if isinstance(package, tuple):
            result_dict[package[0]] = package[1]
        else:
            result_dict[package] = []

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

    sorted_pkgs = tuple(result_dict.keys())

    server.request_line = (
        "SELECT DISTINCT SrcPkg.name, SrcPkg.version, SrcPkg.release, "
        "SrcPkg.epoch, SrcPkg.serial_, sourcerpm AS filename, "
        "assigment_name, groupUniqArray(arch) FROM last_packages "
        "INNER JOIN (SELECT name, version, release, epoch, serial_, "
        "filename, assigment_name FROM last_packages WHERE name IN "
        "%(pkgs)s AND assigment_name = %(branch)s AND sourcepackage = 1) "
        "AS SrcPkg USING filename WHERE assigment_name = %(branch)s AND "
        "sourcepackage = 0 GROUP BY (SrcPkg.name, SrcPkg.version, "
        "SrcPkg.release, SrcPkg.epoch, SrcPkg.serial_, filename, "
        "assigment_name)",
        {'pkgs': sorted_pkgs, 'branch': pbranch}
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

    # sort pkg info list
    sorted_dict = {}
    for pkg in pkg_info_list:
        if task_id:
            if pkg[0] not in input_pkgs:
                sorted_dict[sorted_pkgs.index(pkg[0])] = pkg
        else:
            sorted_dict[sorted_pkgs.index(pkg[0])] = pkg

    sorted_dict = list(dict(sorted(sorted_dict.items())).values())

    js_keys = ['name', 'version', 'release', 'epoch', 'serial_', 'sourcerpm',
               'branch', 'archs', 'cycle']

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
        return json.dumps(server.helper(request.path))

    parch = server.default_archs
    if values['arch']:
        parch = values['arch'].split(',')
        if 'noarch' not in parch:
            parch.append('noarch')

    server.request_line = (
        "SELECT DISTINCT Pkg.pkgname, extract(filename, '^(.+)/([^/]+)$'), "
        "Pkg.version, Pkg.release, Pkg.epoch, Pkg.packager, Pkg.packager_email, "
        "Pkg.arch FROM File LEFT JOIN (SELECT pkghash, name AS pkgname, "
        "version, release, epoch, packager, packager_email, arch FROM Package) "
        "AS Pkg USING pkghash WHERE empty(fileclass) AND pkghash IN (SELECT "
        "pkghash FROM last_packages WHERE assigment_name = %(branch)s AND "
        "packager_email LIKE %(email)s AND sourcepackage = 0 AND arch IN "
        "%(arch)s) AND hashdir NOT IN (SELECT hashname FROM File WHERE "
        "fileclass = 'directory' AND pkghash IN (SELECT pkghash FROM "
        "last_packages WHERE assigment_name = %(branch)s AND packager_email "
        "LIKE %(email)s AND sourcepackage = 0 AND arch IN %(arch)s)) ORDER BY "
        "packager_email", {
            'branch': values['pkgset'], 'email': '{}@%'.format(values['pkgr']),
            'arch': tuple(parch)
        }
    )

    status, response = server.send_request(trace=True)
    if status is False:
        return response


@app.errorhandler(404)
def page_404(e):
    helper = {
        'Valid queries': {
            '/package_info': 'information about given package',
            '/misconflict_packages': 'binary packages with intersecting '
                                     'files and no conflict with a given package',
            '/package_by_file': 'binary packages that contain the specified file',
            '/package_files': 'files by current sha1 of package',
            '/dependent_packages': 'source packages whose binary packages '
                                   'depend on the given package',
            '/what_depends_src': 'binary packages with build dependency on a '
                                 'given package',
        }
    }
    return json.dumps(helper)


if __name__ == '__main__':
    app.run()

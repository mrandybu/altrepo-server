from collections import defaultdict
from utils import remove_values_not_in_keys


class Graph:
    """
    Class for build tree of dependencies.

    Class contains methods for build tree of dependencies, make topological
    sort and auxiliary methods.

    :param vertices: number of tree tops
    """

    def __init__(self, vertices):
        self.graph = defaultdict(list)
        self.V = vertices

    def add_edge(self, u, v):
        self.graph[u].append(v)

    def _topological_sort_util(self, v, visited, stack):
        visited[v] = True

        for i in self.graph[v]:
            if visited[i] is False:
                self._topological_sort_util(i, visited, stack)

        stack.insert(0, v)

    def topological_sort(self):
        visited = [False] * self.V
        stack = []

        for i in range(self.V):
            if visited[i] is False:
                self._topological_sort_util(i, visited, stack)

        return stack


class SortList:
    """
    Class for sorting packages.

    Class contains method which sort packages by their dependencies and
    its auxiliary methods.

    :param package_reqs: dict package name - dependency list
    :param pkgname: name of input package
    """

    def __init__(self, package_reqs, pkgname):
        self.package_reqs = package_reqs
        self.pkgname = pkgname

    @staticmethod
    def _numbered_list(list_):
        """
        Convert names to numbers.

        Form two dict, name - number, number - name. Use for data processing
        before sort.

        :param list_: list of package names
        :return: `dict` num - name,
                 `dict` name - num.
        """
        num_to_name, name_to_num = {}, {}
        for num in range(len(list_)):
            num_to_name[list_[num]] = num
            name_to_num[num] = list_[num]
        return num_to_name, name_to_num

    def _search_circle_deps(self):
        """
        Method search if packages from the list have dependencies on each other.

        :return: `list` of circle dependencies
        """
        circle_deps = []
        for package, reqs in self.package_reqs.items():
            for dep in reqs:
                if package in self.package_reqs[dep] and package != dep:
                    circle_deps.append((package, dep))

        return circle_deps

    def _fill_empty_deps(self):
        """
        If package no dependencies add None.
        """
        for package, reqs in self.package_reqs.items():
            if not reqs:
                self.package_reqs[package].append(None)

    def sort_list(self):
        """"
        Main public class method.

        Sort packages by dependencies add find circle dependencies.

        :return: `list` of circle dependencies, `list` of sorted packages
        """
        # list of packages to sort
        packages_ls = list(self.package_reqs.keys())

        # reverse (packages <-> dependencies) in dict
        normalize_req_list = defaultdict(list)
        for key, val in self.package_reqs.items():
            for req in val:
                normalize_req_list[req].append(key)

        self.package_reqs = remove_values_not_in_keys(normalize_req_list)

        # get circle dependencies
        circle_deps = self._search_circle_deps()
        for dep in circle_deps:
            self.package_reqs[dep[0]].remove(dep[1])

        # number of tree tops
        num_non_req = len(packages_ls)

        # make two dict for convert package names in numbers and back
        num_to_name, name_to_num = self._numbered_list(packages_ls)
        # add abstract empty top for packages without dependencies
        num_to_name[None] = num_non_req

        # add None if package no dependencies
        self._fill_empty_deps()

        # convert package names in name - deps dict in numbers
        num_name_reqs = {}
        for package, reqs in self.package_reqs.items():
            num_reqs = []
            for req in reqs:
                num_reqs.append(num_to_name[req])

            num_name_reqs[num_to_name[package]] = num_reqs

        g = Graph(num_non_req + 1)

        # add pair pkg name - dependencies in tree tops
        for key, val in num_name_reqs.items():
            for vertex in val:
                g.add_edge(key, vertex)

        # make back convert numbers to names in sorted list
        sorted_list = []
        for num in g.topological_sort():
            if num != num_non_req:
                sorted_list.append(name_to_num[num])

        return circle_deps, sorted_list

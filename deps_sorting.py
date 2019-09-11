from collections import defaultdict


class Graph:
    def __init__(self, vertices):
        self.graph = defaultdict(list)
        self.V = vertices

    def addEdge(self, u, v):
        self.graph[u].append(v)

    def _topologicalSortUtil(self, v, visited, stack):
        visited[v] = True

        for i in self.graph[v]:
            if visited[i] is False:
                self._topologicalSortUtil(i, visited, stack)

        stack.insert(0, v)

    def topologicalSort(self):
        visited = [False] * self.V
        stack = []

        for i in range(self.V):
            if visited[i] is False:
                self._topologicalSortUtil(i, visited, stack)

        return stack


class SortList:
    def __init__(self, package_reqs, pkgname):
        self.package_reqs = package_reqs
        self.pkgname = pkgname

    @staticmethod
    def _numbered_list(list_):
        num_to_name, name_to_num = {}, {}
        for num in range(len(list_)):
            num_to_name[list_[num]] = num
            name_to_num[num] = list_[num]
        return num_to_name, name_to_num

    def _remove_reqs_out_of_list(self, packages_ls):
        cleanup_pkgs_reqs = {}
        for package, reqs in self.package_reqs.items():
            cleanup_reqs = []
            for req in reqs:
                if req in packages_ls:
                    cleanup_reqs.append(req)

            cleanup_pkgs_reqs[package] = cleanup_reqs

        self.package_reqs = cleanup_pkgs_reqs

    def _search_circle_deps(self):
        circle_deps = []
        for package, reqs in self.package_reqs.items():
            for p_pac, r_reqs in self.package_reqs.items():
                if package in r_reqs and p_pac in reqs:
                    if (package, p_pac) not in circle_deps and \
                            (p_pac, package) not in circle_deps:
                        circle_deps.append((package, p_pac))

        return circle_deps

    def _fill_empty_deps(self):
        for package, reqs in self.package_reqs.items():
            if not reqs:
                self.package_reqs[package].append(None)

    def sort_list(self):
        packages_ls = list(self.package_reqs.keys())

        # reverse (packages -> dependencies)
        normalize_req_list = defaultdict(list)
        for key, val in self.package_reqs.items():
            for req in val:
                normalize_req_list[req].append(key)

        self.package_reqs = normalize_req_list

        circle_deps = self._search_circle_deps()
        for dep in circle_deps:
            self.package_reqs[dep[0]].remove(dep[1])

        num_non_req = len(packages_ls)

        num_to_name, name_to_num = self._numbered_list(packages_ls)
        num_to_name[None] = num_non_req

        self._fill_empty_deps()

        num_name_reqs = {}
        for package, reqs in self.package_reqs.items():
            num_reqs = []
            for req in reqs:
                num_reqs.append(num_to_name[req])

            num_name_reqs[num_to_name[package]] = num_reqs

        g = Graph(num_non_req + 1)

        for key, val in num_name_reqs.items():
            for vertex in val:
                g.addEdge(key, vertex)

        sorted_list = []
        for num in g.topologicalSort():
            if num != num_non_req:
                sorted_list.append(name_to_num[num])

        return circle_deps, sorted_list

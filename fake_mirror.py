import os
import numpy as np
from subprocess import Popen, PIPE

# parameters of make fake mirror
SISYPHUS = '/ALT/Sisyphus/files/{}/RPMS/'
P8 = '/ALT/p8/branch/files/{}/RPMS/'
P7 = '/ALT/p7/branch/files/{}/RPMS/'
PACKAGENUM = 500


def make_fake_mirror():
    repo_struct = {
        'Sisyphus': {
            'archs': ['aarch64', 'armh', 'noarch', 'SRPMS',
                      'i586', 'x86_64', 'x86_64-i586'],
            'paths': (SISYPHUS, 'fake_mirror/Sisyphus/{}/'),
        },
        'p8': {
            'archs': ['aarch64', 'armh', 'noarch', 'SRPMS',
                      'i586', 'x86_64', 'x86_64-i586'],
            'paths': (P8, 'fake_mirror/p8/{}/'),
        },
        'p7': {
            'archs': ['arm', 'armh', 'noarch', 'SRPMS',
                      'i586', 'x86_64', 'x86_64-i586'],
            'paths': (P7, 'fake_mirror/p7/{}/'),
        },
    }

    for branch in repo_struct:
        for arch in repo_struct[branch]['archs']:
            orig_path, fake_path = [
                p.format(arch) for p in repo_struct[branch]['paths']
            ]

            if arch == 'SRPMS':
                orig_path = orig_path.replace('/RPMS/', '/')

            ls = Popen(
                ['ls', orig_path.format(arch)], stdout=PIPE
            ).stdout.read().decode('utf-8').split("\n")

            random_nums = np.random.choice(
                len(ls) - 1, PACKAGENUM, replace=False
            )
            for num in random_nums:
                cp = os.path.join(orig_path, ls[num])
                Popen(['cp', '-f', cp, fake_path], stdout=PIPE)
                print(cp, fake_path)


if __name__ == '__main__':
    make_fake_mirror()

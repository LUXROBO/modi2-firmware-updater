import os

from shutil import rmtree
from platform import system
from argparse import ArgumentParser


def make_clean():
    cwd = os.path.dirname(__file__)
    dirnames = ['__pycache__', 'build', 'dist']
    for d in dirnames:
        dirpath = os.path.join(cwd, d)
        if os.path.isdir(dirpath):
            rmtree(dirpath)

def make_executable(is_multi):
    make_clean()
    if is_multi:
        os.system(f'pyinstaller modi_multi_uploader.spec')
    else:
        os.system(f'pyinstaller modi_single_uploader.spec')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument(
        '--multi', type=str, default="True",
        choices=["False", "True"],
        help='multi uploader'
    )
    args = parser.parse_args()
    multi = (args.multi == 'True')
    make_executable(multi)

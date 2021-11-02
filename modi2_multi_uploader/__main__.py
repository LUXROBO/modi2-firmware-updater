import os
import sys

from textwrap import dedent

from getopt import getopt, GetoptError


def check_option(*options):
    for o, a in opts:
        if o in options:
            return a if a else True
    return False


if __name__ == '__main__':
    usage = dedent(
        """
        Usage: python -m modi -<options>
        Options:
        -t, --tutorial: Interactive Tutorial
        -d, --debug: Auto initialization debugging mode
        -h, --help: Print out help page
        """.rstrip()
    )

    try:
        # All commands should be defined here in advance
        opts, args = getopt(
            sys.argv[1:], 'nbm',
            [
                'update_network', 'update_network_base', 'update_modules',
            ]
        )
    # Exit program if an invalid option has been entered
    except GetoptError as err:
        print(str(err))
        print(usage)
        os._exit(2)

    # Ensure that there is an option but argument
    if len(sys.argv) == 1 or len(args) > 0:
        print(usage)
        os._exit(2)
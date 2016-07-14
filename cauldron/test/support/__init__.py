import re
import readline
from unittest.mock import patch

from cauldron import environ
from cauldron.cli import commander
from cauldron.cli.shell import CauldronShell
from cauldron.test.support import scaffolds
from cauldron.test.support.messages import Message


def run_command(command: str) -> 'environ.Response':
    """

    :param command:
    :return:
    """

    cs = CauldronShell()
    cs.default(command)
    return cs.last_response


def create_project(
        tester: scaffolds.ResultsTest,
        name: str,
        path: str = None,
        **kwargs
) -> 'environ.Response':
    """

    :param tester:
    :param name:
    :param path:
    :param kwargs:
    :return:
    """

    if path is None:
        path = tester.get_temp_path('projects')

    r = environ.Response()

    args = [name, path]
    for key, value in kwargs.items():
        args.append('--{}="{}"'.format(key, value))
    args = ' '.join([a for a in args if a and len(a) > 0])

    commander.execute('create', args, r)

    return r


def open_project(
        tester: scaffolds.ResultsTest,
        path: str
) -> 'environ.Response':
    """

    :param tester:
    :param path:
    :return:
    """

    r = environ.Response()
    commander.execute('open', path, r)
    return r


def autocomplete(command: str):
    """

    :param command:
    :return:
    """

    with patch('readline.get_line_buffer', return_value=command):
        cs = CauldronShell()
        line = command.lstrip()

        splits = re.split('[{}]{{1}}'.format(
            re.escape(readline.get_completer_delims())),
            line
        )

        return cs.completedefault(
            text=splits[-1],
            line=line,
            begin_index=len(line) - len(splits[-1]),
            end_index=len(line) - 1
        )

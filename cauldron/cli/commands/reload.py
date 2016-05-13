import os
from argparse import ArgumentParser

import cauldron
from cauldron import environ
from cauldron import runner
from cauldron import reporting

DESCRIPTION = """
    Discards all shared data and reloads the currently open project to its
    initial state
    """


def populate(parser: ArgumentParser):
    """

    :param parser:
    :return:
    """
    pass


def execute(parser: ArgumentParser):

    recent_paths = environ.configs.fetch('recent_paths', [])

    if not recent_paths:
        return

    path = recent_paths[0]
    path = environ.paths.clean(path)
    if not os.path.exists(path):
        environ.log(
            """
            The specified path does not exist:

            "{path}"
            """.format(path=path)
        )
        return

    try:
        runner.initialize(path)
    except FileNotFoundError:
        environ.log('Error: Project not found')
        return

    environ.log('Reloaded: {}'.format(path))

    project = cauldron.project.internal_project

    if project.results_path:
        reporting.initialize_results_path(project.results_path)

    path = project.output_path
    if not path or not os.path.exists(path):
        project.write()

    url = project.url

    environ.log(
        """
        Project URL:
          * {url}
        """.format(url=url)
    )

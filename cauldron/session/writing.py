import glob
import json
import os
import shutil
import typing

from cauldron import cli
from cauldron import environ
from cauldron import templating
from cauldron.session import projects


def create_step_data(step: 'projects.ProjectStep') -> dict:
    """
    Creates the data object that stores the step information in the notebook
    results JavaScript file.

    :param step:
        Project step for which to create the data
    :return:
        Dictionary containing scaffold data structure for the step output.
        The dictionary must then be populated with data from the step to
        correctly reflect the current state of the step.

        This is essentially a "blank" step dictionary, which is what the step
        would look like if it had not yet run
    """

    return dict(
        name=step.definition.name,
        status=step.status(),
        has_error=False,
        body=None,
        data=dict(),
        includes=[],
        cauldron_version=list(environ.version_info)
    )


def get_cached_step_data(
        step: 'projects.ProjectStep'
) -> typing.Union[None, dict]:
    """

    :param step:
    :return:
    """

    cache_path = step.report.results_cache_path
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r+') as f:
            return json.load(f)
    except Exception:
        return None


def get_step_dom(step: 'projects.ProjectStep') -> str:
    """

    :param step:
    :return:
    """

    if step.dom is None or step.is_running:
        return step.dumps()

    return step.dom


def write_step_cache(step: 'projects.ProjectStep', data: dict) -> bool:
    """

    :param step:
    :param data:
    :return:
    """

    cache_path = step.report.results_cache_path
    if not cache_path:
        return False

    directory = os.path.dirname(cache_path)
    if not os.path.exists(directory):
        os.makedirs(directory)

    with open(cache_path, 'w+') as f:
        json.dump(data, f)

    return True


def populate_step_data(
        step: 'projects.ProjectStep',
        source: dict = None
) -> dict:
    """

    :param step:
    :param source:
    :return:
    """

    out = create_step_data(step) if source is None else source.copy()

    report = step.report

    out['has_error'] = step.error
    out['body'] = get_step_dom(step)
    out['data'].update(report.data.fetch(None))
    out['includes'] += (
        add_web_includes(step.web_includes, step.project) +
        add_components(step)
    )

    return out


def write_step(step: 'projects.ProjectStep') -> dict:
    """

    :param step:
    :return:
    """

    def disable_caching():
        return step.last_modified or step.error

    cached = None if disable_caching() else get_cached_step_data(step)
    if cached:
        return cached

    if step.is_muted:
        return create_step_data(step)

    out = populate_step_data(step)
    write_files(step.report.files.fetch(None), step.project)
    write_step_cache(step, out)

    return out


def write_baked_html_file(
        project: 'projects.Project',
        template_path: str,
        destination_directory: str = None,
        destination_filename: str = None
):
    """

    """

    with open(template_path, 'r+') as f:
        dom = f.read()

    dom = dom.replace(
        '<!-- CAULDRON:EXPORT -->',
        cli.reformat(
            """
            <script>
                window.RESULTS_FILENAME = 'reports/{uuid}/latest/results.js';
                window.PROJECT_ID = '{uuid}';
                window.CAULDRON_VERSION = '{version}';
            </script>
            """.format(
                uuid=project.uuid,
                version=environ.version
            )
        )
    )

    if not destination_directory:
        destination_directory = os.path.dirname(template_path)

    if not destination_filename:
        destination_filename = '{}.html'.format(project.uuid)

    html_out_path = os.path.join(
        destination_directory,
        destination_filename
    )

    with open(html_out_path, 'w+') as f:
        f.write(dom)


def write_project(project: 'projects.Project'):
    """

    :param project:
    :return:
    """

    environ.systems.remove(project.output_directory)
    os.makedirs(project.output_directory)

    web_includes = add_web_includes(
        project.settings.fetch('web_includes', []),
        project
    )

    steps = []
    for step in project.steps:
        steps.append(write_step(step))

    with open(project.output_path, 'w+') as f:
        # Write the results file
        f.write(templating.render_template(
            'report.js.template',
            DATA=json.dumps({
                'steps': steps,
                'includes': web_includes,
                'settings': project.settings.fetch(None),
                'cauldron_version': list(environ.version_info)
            })
        ))

    copy_assets(project)

    write_baked_html_file(
        project,
        os.path.join(project.results_path, 'project.html'),
        destination_filename='display.html'
    )


def copy_files(file_copies: dict, project: 'projects.Project'):
    """

    :param file_copies:
    :param project:
    :return:
    """

    if not file_copies:
        return

    for filename, source_path in file_copies.items():
        file_path = os.path.join(project.output_directory, filename)
        output_directory = os.path.dirname(file_path)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        shutil.copy2(source_path, file_path)


def write_files(file_writes: dict, project: 'projects.Project'):
    """

    :param file_writes:
    :param project:
    :return:
    """

    if not file_writes:
        return

    for filename, contents in file_writes.items():
        file_path = os.path.join(project.output_directory, filename)
        output_directory = os.path.dirname(file_path)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        with open(file_path, 'w+') as f:
            f.write(contents)


def add_web_includes(
        include_paths: list,
        project: 'projects.Project'
) -> typing.List[dict]:
    """

    :param include_paths:
    :param project:
    :return:
    """

    web_includes = []

    for item in include_paths:
        # Copy "included" files and folders that were specified in the
        # project file to the output directory

        source_path = environ.paths.clean(
            os.path.join(project.source_directory, item)
        )
        if not os.path.exists(source_path):
            continue

        item_path = os.path.join(project.output_directory, item)
        output_directory = os.path.dirname(item_path)
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        if os.path.isdir(source_path):
            shutil.copytree(source_path, item_path)
            glob_path = os.path.join(item_path, '**', '*')
            for entry in glob.iglob(glob_path, recursive=True):
                web_includes.append(
                    '{}'.format(
                        entry[len(project.output_directory):]
                            .replace('\\', '/'))
                )
        else:
            shutil.copy2(source_path, item_path)
            web_includes.append('/{}'.format(item.replace('\\', '/')))

    return [
        {'src': url, 'name': ':project:{}'.format(url)}
        for url in web_includes
    ]


def copy_assets(project: 'projects.Project'):
    """

    :param project:
    :return:
    """

    directory = os.path.join(project.source_directory, 'assets')
    if not os.path.exists(directory):
        return False

    output_directory = os.path.join(project.output_directory, 'assets')
    shutil.copytree(directory, output_directory)
    return True


def add_components(step: 'projects.ProjectStep') -> typing.List[dict]:
    """

    :param step:
    :return:
    """

    web_includes = []

    for lib_name in set(step.report.library_includes):
        if lib_name == 'bokeh':
            web_includes += add_bokeh(step)
        elif lib_name == 'plotly':
            web_includes += add_plotly(step)
        else:
            web_includes += add_global_component(lib_name, step)

    return web_includes


def add_global_component(name, step):
    """

    :param name:
    :param step:
    :return:
    """

    component_directory = environ.paths.resources(
        'web',
        'components',
        name
    )

    out = []
    if not os.path.exists(component_directory):
        return out

    glob_path = os.path.join(component_directory, '**', '*')
    for path in glob.iglob(glob_path, recursive=True):
        if not os.path.isfile(path):
            continue

        if not path.endswith('.css') and not path.endswith('.js'):
            continue

        slug = path[len(component_directory):]

        # web includes that start with a : are relative to the root
        # results folder, not the project itself. They are for shared
        # resource files
        out.append({
            'name': 'components-{}-{}'.format(
                name,
                slug.strip('/').replace('/', '_').replace('.', '_')
            ),
            'src': ':components/{}{}'.format(name, slug)
        })

    return out


def add_component(name, file_copies, web_includes):
    """

    :param name:
    :param file_copies:
    :param web_includes:
    :return:
    """

    component_directory = environ.paths.resources(
        'web', 'components', name
    )

    if not os.path.exists(component_directory):
        return False

    glob_path = '{}/**/*'.format(component_directory)
    for path in glob.iglob(glob_path, recursive=True):
        if not os.path.isfile(path):
            continue

        slug = path[len(component_directory):]
        save_path = 'components/{}'.format(slug)
        file_copies[save_path] = path

        if path.endswith('.js') or path.endswith('.css'):
            web_includes.append('/{}'.format(save_path))

    return True


def add_bokeh(step: 'projects.ProjectStep') -> typing.List[dict]:
    """
    :return:
    """

    try:
        from bokeh.resources import Resources as BokehResources
    except Exception:
        return []

    out = []

    if BokehResources is None:
        environ.log(
            """
            [WARNING]: Bokeh library is not installed. Unable to
                include library dependencies, which may result in
                HTML rendering errors. To resolve this make sure
                you have installed the Bokeh library.
            """
        )
        return out

    br = BokehResources(mode='absolute')

    file_writes = dict()
    contents = []
    for p in br.css_files:
        with open(p, 'r+') as fp:
            contents.append(fp.read())
    file_path = os.path.join('bokeh', 'bokeh.css')
    file_writes[file_path] = '\n'.join(contents)

    out.append({
        'name': 'bokeh-css',
        'src': '/bokeh/bokeh.css'
    })

    contents = []
    for p in br.js_files:
        with open(p, 'r+') as fp:
            contents.append(fp.read())
    file_path = os.path.join('bokeh', 'bokeh.js')
    file_writes[file_path] = '\n'.join(contents)

    out.append({
        'name': 'bokeh-js',
        'src': '/bokeh/bokeh.js'
    })

    write_files(file_writes, step.project)
    return out


def add_plotly(step: 'projects.ProjectStep') -> typing.List[dict]:
    """
    :param step:
    :return:
    """

    try:
        from plotly.offline import offline as plotly_offline
    except Exception:
        return []

    out = []

    if plotly_offline is None:
        environ.log(
            """
            [WARNING]: Plotly library is not installed. Unable to
                include library dependencies, which may result in
                HTML rendering errors. To resolve this make sure
                you have installed the Plotly library.
            """
        )
        return out

    p = os.path.join(
        environ.paths.clean(os.path.dirname(plotly_offline.__file__)),
        'plotly.min.js'
    )

    save_path = 'components/plotly/plotly.min.js'
    copy_files({save_path: p}, step.project)

    out.append({
        'name': 'plotly',
        'src': '/{}'.format(save_path)
    })

    return out

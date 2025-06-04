import logging
from cli_base.cli_tools.dev_tools import run_unittest_cli
from cli_base.cli_tools.subprocess_utils import ToolsExecutor
from cli_base.cli_tools.verbosity import setup_logging
from cli_base.tyro_commands import TyroVerbosityArgType
from manageprojects.utilities.publish import publish_package


import kronoterm2mqtt
from kronoterm2mqtt.cli_dev import PACKAGE_ROOT, app

logger = logging.getLogger(__name__)

@app.command
def install():
    """
    Install requirements and 'kronoterm2mqtt' via pip as editable.
    """
    tools_executor = ToolsExecutor(cwd=PACKAGE_ROOT)
    tools_executor.verbose_check_call('uv', 'sync')
    tools_executor.verbose_check_call('pip', 'install', '--no-deps', '-e', '.')
    
def _call_safety():
    """
    Run safety check against current requirements files
    """
    verbose_check_call(
        'safety',
        'check',
        '--ignore',
        '70612',  # Jinja2 Server Side Template Injection (SSTI)
        '--ignore',
        '73725', # starlette DoS 
        '-r',
        'requirements.dev.txt',
    )

    
@app.command
def safety():
    """
    Run safety check against current requirements files
    """
    _call_safety()

@app.command
def pip_audit(verbosity: TyroVerbosityArgType):
    """
    Run pip-audit check against current requirements files
    """
    setup_logging(verbosity=verbosity)
    run_pip_audit(base_path=PACKAGE_ROOT, verbosity=verbosity)
    
@app.command
def update(verbosity: TyroVerbosityArgType):
    """
    Update "requirements*.txt" dependencies files
    """
    setup_logging(verbosity=verbosity)

    tools_executor = ToolsExecutor(cwd=PACKAGE_ROOT)

    tools_executor.verbose_check_call('pip', 'install', '-U', 'pip')
    tools_executor.verbose_check_call('pip', 'install', '-U', 'uv')
    tools_executor.verbose_check_call('uv', 'lock', '--upgrade')

    run_pip_audit(base_path=PACKAGE_ROOT, verbosity=verbosity)

@app.command
def publish():
    """
    Build and upload this project to PyPi
    """
    run_unittest_cli(verbose=False, exit_after_run=False)  # Don't publish a broken state

    publish_package(module=kronoterm2mqtt, package_path=PACKAGE_ROOT)

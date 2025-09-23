from cli_base.cli_tools.code_style import assert_code_style
from cli_base.tyro_commands import TyroVerbosityArgType

from kronoterm2mqtt.cli_dev import PACKAGE_ROOT, app


@app.command
def lint(verbosity: TyroVerbosityArgType):
    """
    Check/fix code style by running: ruff check --fix"
    """
    assert_code_style(package_root=PACKAGE_ROOT, verbose=bool(verbosity), sys_exit=True)

from cli_base.cli_tools.test_utils.assertion import assert_in
from cli_base.cli_tools.test_utils.rich_test_utils import (
    assert_no_color_env,
    assert_rich_click_no_color,
    assert_rich_no_color,
    assert_subprocess_rich_diagnose_no_color,
)
from cli_base.toml_settings.test_utils.cli_mock import TomlSettingsCliMock
from manageprojects.tests.base import BaseTestCase

from kronoterm2mqtt import constants
from kronoterm2mqtt.user_settings import UserSettings
from pathlib import Path
import kronoterm2mqtt

TERM_WIDTH = 100
PACKAGE_ROOT = Path(kronoterm2mqtt.__file__).parent.parent

class ReadmeTestCase(BaseTestCase):
    cli_mock = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        settings_overwrites = dict(
            systemd=dict(
                template_context=dict(
                    user='MockedUserName',
                    group='MockedUserName',
                )
            ),
        )

        cls.cli_mock = TomlSettingsCliMock(
            SettingsDataclass=UserSettings,
            settings_overwrites=settings_overwrites,
            dir_name='kronoterm2mqtt',
            file_name='kronoterm2mqtt',
            width=TERM_WIDTH,
        )
        cls.cli_mock.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass()
        cls.cli_mock.__exit__(None, None, None)

    def test_cli_mock(self):
        assert_no_color_env(width=TERM_WIDTH)
        assert_subprocess_rich_diagnose_no_color(width=TERM_WIDTH)
        assert_rich_no_color(width=TERM_WIDTH)
        assert_rich_click_no_color(width=TERM_WIDTH)

    def invoke_cli(self, *args):
        stdout = self.cli_mock.invoke(cli_bin=PACKAGE_ROOT / 'cli.py', args=args, strip_line_prefix='Usage: ')

        # Remove last line:
        stdout = '\n'.join(stdout.splitlines()[:-1])
        return stdout.rstrip()

    def invoke_dev_cli(self, *args):
        return self.cli_mock.invoke(cli_bin=PACKAGE_ROOT / 'dev-cli.py', args=args, strip_line_prefix='Usage: ')

    def test_main_help(self):
        stdout = self.invoke_cli('--help')
        assert_in(
            content=stdout,
            parts=(
                'Usage: ./cli.py [OPTIONS] COMMAND [ARGS]...',
                'print-values',
                'publish-loop',
            ),
        )

    def test_dev_help(self):
        stdout = self.invoke_dev_cli('--help')
        assert_in(
            content=stdout,
            parts=(
                'Usage: ./dev-cli.py [OPTIONS] COMMAND [ARGS]...',
                'fix-code-style',
                'tox',
                constants.CLI_EPILOG,
            ),
        )

    def test_publish_loop_help(self):
        stdout = self.invoke_cli('publish-loop', '--help')
        assert_in(
            content=stdout,
            parts=(
                'Usage: ./cli.py publish-loop [OPTIONS]',
                '--verbosity',
            ),
        )

    def test_print_values_help(self):
        stdout = self.invoke_cli('print-values', '--help')
        assert_in(
            content=stdout,
            parts=(
                'Usage: ./cli.py print-values [OPTIONS]',
                '--verbosity',
            ),
        )

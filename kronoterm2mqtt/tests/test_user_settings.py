import json
import tempfile
from pathlib import Path
from unittest import TestCase

from bx_py_utils.environ import OverrideEnviron
from bx_py_utils.path import assert_is_file
from cli_base.cli_tools.test_utils.assertion import assert_in
from cli_base.toml_settings.api import TomlSettings

from kronoterm2mqtt.user_settings import SystemdServiceInfo, UserSettings


class UserSettingsTestCase(TestCase):
    def test_systemd_service_info(self):
        user_settings = UserSettings()
        systemd_settings = user_settings.systemd
        self.assertIsInstance(systemd_settings, SystemdServiceInfo)

        # Check some samples:
        self.assertEqual(systemd_settings.template_context.verbose_service_name, 'kronoterm2mqtt')
        self.assertEqual(systemd_settings.service_slug, 'kronoterm2mqtt')
        self.assertEqual(systemd_settings.template_context.syslog_identifier, 'kronoterm2mqtt')
        self.assertEqual(systemd_settings.service_file_path, Path('/etc/systemd/system/kronoterm2mqtt.service'))

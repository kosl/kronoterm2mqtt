from pathlib import Path
from unittest import TestCase

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

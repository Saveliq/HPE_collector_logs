import contextlib
import io
import json
import shlex
import unittest
from unittest.mock import patch

import collectfromOV


class CredentialsTests(unittest.TestCase):
    def test_local_login_explicitly_selects_local_directory(self):
        for directory in ('', '  ', 'local', 'LOCAL'):
            with self.subTest(directory=directory):
                credentials = collectfromOV.build_oneview_credentials(
                    ' Administrator ', ' fake@password\\with spaces ', directory
                )
                self.assertEqual(credentials, {
                    'userName': 'Administrator',
                    'password': ' fake@password\\with spaces ',
                    'authLoginDomain': 'LOCAL',
                })

    def test_directory_name_is_independent_of_login_domain(self):
        for username in ('testuser@example.test', r'EXAMPLE\testuser', 'testuser'):
            with self.subTest(username=username):
                credentials = collectfromOV.build_oneview_credentials(
                    username, 'fake-password', ' Corporate Directory '
                )
                self.assertEqual(credentials['userName'], username)
                self.assertEqual(credentials['authLoginDomain'], 'Corporate Directory')

    def test_common_credentials_include_selected_directory_for_every_appliance(self):
        configs = [{'ip': '192.0.2.1'}, {'ip': '192.0.2.2'}]
        with patch('builtins.input', side_effect=['1', 'testuser@example.test', 'Corporate']), \
                patch.object(collectfromOV.getpass, 'getpass', return_value='fake-password'), \
                contextlib.redirect_stdout(io.StringIO()):
            collectfromOV.prompt_for_credentials(configs)
        for config in configs:
            self.assertEqual(config['credentials'], {
                'userName': 'testuser@example.test',
                'password': 'fake-password',
                'authLoginDomain': 'Corporate',
            })
        self.assertIsNot(configs[0]['credentials'], configs[1]['credentials'])

    def test_separate_credentials_keep_local_and_directory_logins_independent(self):
        configs = [{'ip': '192.0.2.1'}, {'ip': '192.0.2.2'}]
        with patch('builtins.input', side_effect=[
            '2', 'Administrator', 'testuser@example.test', 'Corporate'
        ]), patch.object(collectfromOV.getpass, 'getpass', side_effect=['fake-local', 'fake-ad']), \
                contextlib.redirect_stdout(io.StringIO()):
            collectfromOV.prompt_for_credentials(configs)
        self.assertEqual(configs[0]['credentials'], {
            'userName': 'Administrator', 'password': 'fake-local', 'authLoginDomain': 'LOCAL',
        })
        self.assertEqual(configs[1]['credentials'], {
            'userName': 'testuser@example.test', 'password': 'fake-ad', 'authLoginDomain': 'Corporate',
        })

    def test_common_local_login_does_not_prompt_for_directory(self):
        configs = [{'ip': '192.0.2.1'}, {'ip': '192.0.2.2'}]
        with patch('builtins.input', side_effect=['1', 'Administrator']) as user_input, \
                patch.object(collectfromOV.getpass, 'getpass', return_value='fake@password'), \
                contextlib.redirect_stdout(io.StringIO()):
            collectfromOV.prompt_for_credentials(configs)
        self.assertEqual(user_input.call_count, 2)
        for config in configs:
            self.assertEqual(config['credentials'], {
                'userName': 'Administrator', 'password': 'fake@password', 'authLoginDomain': 'LOCAL',
            })

    def test_domain_login_requires_nonempty_directory_name(self):
        configs = [{'ip': '192.0.2.1'}]
        with patch('builtins.input', side_effect=[
            '2', 'testuser@example.test', '', '   ', ' Corporate Directory '
        ]) as user_input, patch.object(collectfromOV.getpass, 'getpass', return_value='fake-password'), \
                contextlib.redirect_stdout(io.StringIO()):
            collectfromOV.prompt_for_credentials(configs)
        self.assertEqual(user_input.call_count, 5)
        self.assertEqual(configs[0]['credentials']['userName'], 'testuser@example.test')
        self.assertEqual(configs[0]['credentials']['authLoginDomain'], 'Corporate Directory')

    def test_curl_preserves_login_and_directory_without_exposing_password(self):
        credentials = collectfromOV.build_oneview_credentials(
            'testuser@example.test', 'fake-secret', 'Corporate Directory'
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            collectfromOV.print_oneview_login_curl({'ip': '192.0.2.1', 'credentials': credentials})
        self.assertNotIn('fake-secret', output.getvalue())
        command = shlex.split(output.getvalue().splitlines()[-1])
        payload = json.loads(command[command.index('--data') + 1])
        self.assertEqual(payload, {
            'userName': 'testuser@example.test', 'password': '***',
            'authLoginDomain': 'Corporate Directory', 'loginMsgAck': True,
        })
        self.assertEqual(credentials['password'], 'fake-secret')
        self.assertNotIn('loginMsgAck', credentials)


if __name__ == '__main__':
    unittest.main()

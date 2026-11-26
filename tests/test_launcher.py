import unittest
from unittest.mock import MagicMock, patch

import iniciar


class LauncherTests(unittest.TestCase):
    @patch('iniciar.threading.Thread')
    @patch('ponto_apoio.create_app')
    @patch('werkzeug.serving.make_server')
    def test_server_starts_and_closes(self, make_server, create_app, thread):
        server = make_server.return_value
        server.serve_forever.side_effect = KeyboardInterrupt
        with patch('builtins.print'):
            self.assertEqual(iniciar.main(), 0)
        make_server.assert_called_once_with('127.0.0.1', 5000, create_app.return_value)
        thread.return_value.start.assert_called_once()
        server.server_close.assert_called_once()

    @patch('ponto_apoio.create_app')
    @patch('werkzeug.serving.make_server', side_effect=SystemExit(1))
    def test_occupied_port_returns_error(self, make_server, create_app):
        with patch('builtins.print'), patch('iniciar.threading.Thread') as thread:
            self.assertEqual(iniciar.main(), 1)
        thread.assert_not_called()


if __name__ == '__main__':
    unittest.main()

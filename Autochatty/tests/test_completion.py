import tempfile
import unittest
from pathlib import Path

from completion import add_protocol, interpret, marker, missing_files, new_token


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.token = '1' * 24

    def test_end_marker_finishes(self):
        answer = 'Se ha entregado el código y superado la prueba.\n' + marker(self.token, 'TERMINADO')
        self.assertEqual(interpret(answer, self.token)[0], 'done')

    def test_no_marker_is_not_done(self):
        self.assertEqual(interpret('¡Ya está todo terminado!', self.token)[0], 'unknown')

    def test_wrong_token_is_not_done(self):
        answer = 'Terminé.\n' + marker('2'*24, 'TERMINADO')
        self.assertEqual(interpret(answer, self.token)[0], 'unknown')

    def test_marker_not_last_line_is_not_done(self):
        answer = 'Terminé.\n' + marker(self.token, 'TERMINADO') + '\nContinúa mañana.'
        self.assertEqual(interpret(answer, self.token)[0], 'unknown')

    def test_duplicate_marker_is_not_done(self):
        line = marker(self.token, 'TERMINADO')
        self.assertEqual(interpret('Fin.\n'+line+'\n'+line, self.token)[0], 'unknown')

    def test_only_marker_is_not_done(self):
        self.assertEqual(interpret(marker(self.token, 'TERMINADO'), self.token)[0], 'unknown')

    def test_other_states(self):
        for label, outcome in [('PENDIENTE', 'pending'), ('BLOQUEADO', 'blocked')]:
            with self.subTest(label=label):
                self.assertEqual(interpret('Situación actual.\n'+marker(self.token, label), self.token)[0], outcome)

    def test_file_check(self):
        with tempfile.TemporaryDirectory() as folder:
            existing = Path(folder) / 'output.txt'
            existing.write_text('Resultado', encoding='utf-8')
            missing = Path(folder) / 'missing.txt'
            answer = 'Trabajo completado.\n' + marker(self.token, 'TERMINADO')
            self.assertEqual(interpret(answer, self.token, str(existing))[0], 'done')
            self.assertEqual(interpret(answer, self.token, str(existing)+'\n'+str(missing))[0], 'unverified')
            self.assertEqual(missing_files(str(existing)+'\n'+str(missing)), [str(missing)])

    def test_protocol(self):
        token = new_token()
        self.assertEqual(len(token), 24)
        self.assertIn(marker(token, 'TERMINADO'), add_protocol('Continúa.', token, 'Entregar archivo'))


if __name__ == '__main__':
    unittest.main()

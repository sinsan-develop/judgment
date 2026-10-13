import importlib
import sys
import unittest
from unittest.mock import patch

from judgment.contracts import validate_request, validate_run_config, InputError, ConfigError


def payload(n=2):
    return dict(utterance='예약을 취소해 주세요', question='어떤 의도인가요?',
                candidates=[dict(id=str(i), description=f'한국어 선택 {i}') for i in range(n)], context=[])


class ContractsTests(unittest.TestCase):
    def test_variable_count_and_literal_id(self):
        for n in (2, 5, 10, 20):
            self.assertEqual(len(validate_request(payload(n)).candidates), n)
        p = payload(); p['candidates'][0]['id'] = '명령 실행; 파일 삭제'
        self.assertEqual(validate_request(p).candidates[0].id, '명령 실행; 파일 삭제')

    def test_input_errors_are_distinct_and_private(self):
        cases = [('utterance', '', 'empty_utterance'), ('question', '', 'empty_question'),
                 ('candidates', [], 'empty_candidates'), ('context', '원문', 'invalid_context')]
        for field, value, code in cases:
            p = payload(); p[field] = value
            with self.assertRaises(InputError) as e: validate_request(p)
            self.assertEqual(e.exception.code, code)
            self.assertNotIn('예약', str(e.exception))
        for candidate, code in [(dict(id='0', description=''), 'empty_description'),
                                (dict(id='0', description='중복'), 'duplicate_id'),
                                (dict(id='__judgment_abstain__', description='기권'), 'reserved_id')]:
            p = payload(); p['candidates'].append(candidate)
            with self.assertRaises(InputError) as e: validate_request(p)
            self.assertEqual(e.exception.code, code)

    def test_real_null_config_rejected(self):
        self.assertEqual(validate_run_config({'mode': 'fixture'}, real=False).values['mode'], 'fixture')
        with self.assertRaises(ConfigError): validate_run_config({'mode': 'real'}, real=True)

    def test_import_never_loads_ml_or_network(self):
        with patch('socket.socket', side_effect=AssertionError('network')):
            importlib.import_module('judgment')
        self.assertFalse(any(x in sys.modules for x in ('torch', 'laya', 'transformers')))


if __name__ == '__main__': unittest.main()

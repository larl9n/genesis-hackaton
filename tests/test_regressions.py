import unittest

from genesis_fintech.domain.models import DataError
from genesis_fintech.environment.core import AuditEnv
from genesis_fintech.generation.clean import CleanConfig, generate_clean


class RegressionTests(unittest.TestCase):
    def test_extreme_period_fails_with_a_data_error_instead_of_overflow(self):
        with self.assertRaises(DataError):
            generate_clean(42, CleanConfig(period_start='9999-12-01T00:00:00Z',
                                           period_end='9999-12-31T00:00:00Z'))

    def test_malformed_submit_envelope_ends_episode(self):
        env = AuditEnv()
        env.reset(42)
        result = env.step({'action': 'submit'})
        self.assertEqual((result[1], result[2], result[3]), (-1, True, False))


if __name__ == '__main__':
    unittest.main()

from dataclasses import replace
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

from genesis_fintech.domain.models import DataError, PublicEpisode
from genesis_fintech.evaluation.clean import check_clean
from genesis_fintech.generation.clean import CleanConfig, generate_clean
from genesis_fintech.generation.storage import load_public, parse_json, write_clean


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'episode'
        self.generated = generate_clean(42, CleanConfig(invoice_count=3))
        write_clean(self.generated, self.path)

    def test_exact_public_round_trip_and_private_separation(self):
        self.assertEqual(load_public(self.path / 'public'), self.generated.public)
        self.assertEqual(set(p.name for p in (self.path / 'public').iterdir()),
                         {'manifest.json', 'policy.json', 'ledger.csv', 'invoices.jsonl', 'payments.jsonl', 'fx.csv'})
        truth = json.loads((self.path / 'private/truth.json').read_text())
        self.assertEqual(truth['issues'], [])
        self.assertEqual(json.loads((self.path / 'private/provenance.json').read_text())['seed'], 42)

    def test_public_reader_never_reads_private_files(self):
        (self.path / 'private/provenance.json').write_text('not JSON')
        (self.path / 'private/truth.json').unlink()
        self.assertTrue(check_clean(load_public(self.path / 'public')).ok)

    def test_existing_output_is_not_overwritten(self):
        marker = self.path / 'marker'
        marker.write_text('keep')
        with self.assertRaises(FileExistsError):
            write_clean(self.generated, self.path)
        self.assertEqual(marker.read_text(), 'keep')

    def test_csv_explicit_null_and_header_validation(self):
        csv = self.path / 'public/ledger.csv'
        content = csv.read_text()
        self.assertIn('null', content)
        csv.write_text(content.replace('row_id,', 'wrong_id,', 1))
        with self.assertRaises(DataError):
            load_public(self.path / 'public')

    def test_csv_blank_reference_is_not_guessed(self):
        csv = self.path / 'public/ledger.csv'
        csv.write_text(csv.read_text().replace('null', '', 1))
        with self.assertRaises(DataError):
            load_public(self.path / 'public')

    def test_json_duplicate_keys_and_nonfinite_values(self):
        for value in ['{"a": 1, "a": 2}', '{"a": NaN}', '{"a": Infinity}', '{broken',
                      '{"a":' + '9' * 5000 + '}']:
            with self.subTest(value=value), self.assertRaises(DataError):
                parse_json(value)

    def test_oversized_csv_field_produces_data_error(self):
        (self.path / 'public/ledger.csv').write_text('x' * 150000 + '\n')
        with self.assertRaises(DataError):
            load_public(self.path / 'public')

    def test_file_export_rejects_balanced_but_wrong_books(self):
        row = self.generated.public.ledger[0]
        modified = replace(self.generated.public, ledger=(replace(row, entity_id='entity_unknown'),)
                           + self.generated.public.ledger[1:])
        with self.assertRaises(DataError):
            write_clean(replace(self.generated, public=modified), self.path.parent / 'bad')
        self.assertFalse((self.path.parent / 'bad').exists())

    def test_schema_rejects_private_metadata_in_public_manifest(self):
        path = self.path / 'public/manifest.json'
        data = json.loads(path.read_text())
        path.write_text(json.dumps({**data, 'seed': 42}))
        with self.assertRaises(DataError):
            load_public(self.path / 'public')


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'genesis_fintech', *args],
                              capture_output=True, text=True, env=dict(os.environ, PYTHONPATH='src'), timeout=15)

    def test_generate_validate_and_detect_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'episode'
            result = self.run_cli('generate-clean', '--seed', '17', '--config', 'configs/clean.json',
                                  '--output', str(output))
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(json.loads(result.stdout)['ok'])
            checked = self.run_cli('validate-clean', str(output / 'public'))
            self.assertEqual(checked.returncode, 0, checked.stderr)
            manifest_path = output / 'public/manifest.json'
            data = json.loads(manifest_path.read_text())
            data['row_count'] = 1
            manifest_path.write_text(json.dumps(data))
            invalid = self.run_cli('validate-clean', str(output / 'public'))
            self.assertEqual(invalid.returncode, 1)
            self.assertFalse(json.loads(invalid.stdout)['ok'])

    def test_invalid_input_has_bounded_failure_without_traceback(self):
        for args in [('validate-clean', '/missing/genesis/public'),
                     ('generate-clean', '--seed', '-1', '--output', '/not-created'),
                     ('generate-clean', '--seed', '1', '--invoices', '0', '--output', '/not-created')]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(json.loads(result.stdout)['ok'])
                self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()

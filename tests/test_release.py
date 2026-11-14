import importlib.util
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class ReleaseTests(unittest.TestCase):
    def test_source_bundle_repeats_and_round_trips_with_only_allowed_content(self):
        build,verify=module('build_release'),module('verify_release')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'one').mkdir();(root/'two').mkdir()
            a=build.build_source(ROOT,root/'one');b=build.build_source(ROOT,root/'two')
            self.assertEqual(a.read_bytes(),b.read_bytes())
            extracted=verify.unpack_source(a,root/'extract')
            for name,data in build.source_files(ROOT).items():
                self.assertEqual(data,(extracted/name).read_bytes())
            with tarfile.open(a) as archive:
                names=archive.getnames()
                self.assertFalse(any('/CHAT_HISTORY.md' in n or '/private/' in n or '/artifacts/' in n or '/.git/' in n for n in names))
            with self.assertRaises(FileExistsError):build.build_source(ROOT,root/'one')

    def test_source_allowlist_ignores_local_secrets_and_rejects_links(self):
        build=module('build_release')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,data in build.source_files(ROOT).items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            (root/'docs/CHAT_HISTORY.md').write_text('PRIVATE_CHAT_SENTINEL')
            (root/'.env').write_text('PRIVATE_ENV_SENTINEL')
            self.assertNotIn('docs/CHAT_HISTORY.md',build.source_files(root))
            self.assertNotIn('.env',build.source_files(root))
            (root/'docs/linked.md').symlink_to(root/'.env')
            with self.assertRaisesRegex(ValueError,'symbolic links'):build.source_files(root)

    def test_archive_hash_validation_detects_changed_source_before_extraction(self):
        build,verify=module('build_release'),module('verify_release')
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);original=build.build_source(ROOT,root);changed=root/'tampered.tar.gz'
            with tarfile.open(original) as source,tarfile.open(changed,'w:gz') as target:
                for item in source:
                    data=source.extractfile(item).read()
                    if item.name.endswith('/README.md'):data+=b'FORGED'
                    item.size=len(data);target.addfile(item,io.BytesIO(data))
            with self.assertRaisesRegex(ValueError,'manifest mismatch'):verify.unpack_source(changed,root/'out')
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()

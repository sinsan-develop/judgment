"""기존 ROCm 이미지 위에 Linux용 고정 의존성만 프로젝트 venv에 준비한다.

Torch는 이미지의 고정 버전을 유지한다. 나머지는 기존 G1 버전을 Linux wheel로
받고 PyPI 공식 metadata의 hash/size를 대조한 뒤 오프라인·hash고정 설치한다.
"""
import email
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / '.work/pcwsl-runtime'
WHEELS = FOLDER / 'wheels'


def verify_runtime():
    if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != (ROOT / '.work/venv').resolve():
        raise ValueError('dedicated_venv_required')
    if tuple(sys.version_info[:3]) != (3, 12, 3) or importlib.metadata.version('torch') != '2.13.0+rocm7.2':
        raise ValueError('runtime_version')


def run():
    verify_runtime()
    FOLDER.mkdir(exist_ok=True); WHEELS.mkdir(exist_ok=True)
    rows = []
    for line in (ROOT / 'docs/requirements.g1.txt').read_text(encoding='utf-8').splitlines():
        match = re.match(r'^([A-Za-z0-9_.-]+)==([^ ]+)', line)
        if match and match[1].lower() != 'torch': rows.append((match[1], match[2]))
    requirements = FOLDER / 'linux.versions.private.txt'
    requirements.write_text('\n'.join(name + '==' + version for name, version in rows) + '\n', encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--index-url', 'https://pypi.org/simple',
                    '--only-binary=:all:', '--no-deps', '--dest', str(WHEELS), '-r', str(requirements)], check=True)
    downloaded, locked, seen = [], [], set()
    requested = {re.sub(r'[-_.]+', '-', name).lower(): (name, version) for name, version in rows}
    for wheel in sorted(WHEELS.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(names) != 1: raise ValueError('wheel_metadata')
            meta = email.message_from_bytes(archive.read(names[0]))
        normalized = re.sub(r'[-_.]+', '-', meta['Name']).lower()
        if normalized not in requested or normalized in seen: raise ValueError('wheel_package_coverage')
        seen.add(normalized)
        name, version = requested[normalized]
        if meta['Version'] != version: raise ValueError('wheel_version')
        with urllib.request.urlopen('https://pypi.org/pypi/' + name + '/' + version + '/json', timeout=30) as response:
            official = json.load(response)
        candidates = [f for f in official['urls'] if f['filename'] == wheel.name]
        if len(candidates) != 1: raise ValueError('official_file_missing')
        sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
        if sha != candidates[0]['digests']['sha256'] or wheel.stat().st_size != candidates[0]['size']:
            raise ValueError('wheel_hash_size')
        downloaded.append(dict(name=name, version=version, file=wheel.name, bytes=wheel.stat().st_size, sha256=sha))
        locked.append(name + '==' + version + ' --hash=sha256:' + sha)
    if seen != set(requested): raise ValueError('locked_package_count')
    if sum(r['bytes'] for r in downloaded) > 5 * 1024**3: raise ValueError('download_budget')
    lock = FOLDER / 'requirements.rocm.private.txt'
    lock.write_text('\n'.join(locked) + '\n', encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(WHEELS),
                    '--no-deps', '--require-hashes', '-r', str(lock)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e',
                    str(ROOT / '.work/upstream/laya')], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)
    verify_runtime()
    receipt = {'packages': downloaded, 'package_count': len(downloaded),
               'download_bytes': sum(r['bytes'] for r in downloaded),
               'torch': importlib.metadata.version('torch'), 'python': sys.version.split()[0],
               'global_installations_changed': False}
    (FOLDER / 'installation.receipt.private.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'packages'}), flush=True)


if __name__ == '__main__': run()

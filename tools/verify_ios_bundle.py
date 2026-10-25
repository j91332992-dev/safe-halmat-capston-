"""Validate a compiled iOS bundle against the exact shared production web build."""
import argparse
import hashlib
import json
import os
import plistlib
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--web', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    info = plistlib.loads((args.app / 'Info.plist').read_bytes())
    required = ['NSMicrophoneUsageDescription', 'NSCameraUsageDescription', 'NSLocalNetworkUsageDescription']
    for key in required:
        if not info.get(key):
            raise SystemExit('Missing permission description: ' + key)
    if 'arm64' not in info.get('UIRequiredDeviceCapabilities', []):
        raise SystemExit('Device build must declare arm64 support')
    public = args.app / 'public'
    hashes = {}
    for file in sorted(args.web.rglob('*')):
        if not file.is_file():
            continue
        relative = file.relative_to(args.web)
        target = public / relative
        if not target.is_file() or digest(target) != digest(file):
            raise SystemExit('Bundled web parity mismatch: ' + relative.as_posix())
        hashes[relative.as_posix()] = digest(file)
    for required_asset in ['index.html', 'hanmir-call-worklet.js', 'hanmir-call-network.js']:
        if required_asset not in hashes:
            raise SystemExit('Missing shared call/UI asset: ' + required_asset)
    config = json.loads((args.app / 'capacitor.config.json').read_text())
    if config.get('server', {}).get('url'):
        raise SystemExit('A remote development URL must not replace the bundled UI')
    result = {'source_commit': os.environ.get('GITHUB_SHA'), 'bundle_id': info['CFBundleIdentifier'],
              'version': info['CFBundleShortVersionString'], 'build': info['CFBundleVersion'],
              'minimum_os': info.get('MinimumOSVersion'), 'signing': 'unsigned-requires-personal-signing',
              'web_parity': 'exact-sha256-match', 'web_file_count': len(hashes),
              'required_permission_descriptions': required, 'web_sha256': hashes,
              'physical_iphone_tested': False}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'web_sha256'}, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env bash
# Run from any directory: bash frontend/scripts/prepare-ios-mac.sh
set -euo pipefail

OPEN_XCODE=1
case "${1:-}" in
  '') ;;
  --no-open) OPEN_XCODE=0 ;;
  *) echo 'Usage: bash frontend/scripts/prepare-ios-mac.sh [--no-open]' >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != Darwin ]]; then
  echo 'This preparation command requires macOS and Xcode 26 or newer.' >&2
  exit 1
fi
for tool in node npm xcodebuild xcrun python3; do
  command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
NODE_MAJOR=$(node -p 'Number(process.versions.node.split(".")[0])')
if (( NODE_MAJOR < 22 )); then
  echo 'Install Node.js 22 or newer, then run this command again.' >&2
  exit 1
fi
XCODE_MAJOR=$(xcodebuild -version | awk '/^Xcode / {split($2,v,".");print v[1]}')
if [[ -z "$XCODE_MAJOR" ]] || (( XCODE_MAJOR < 26 )); then
  echo 'Select Xcode 26+ in Xcode > Settings > Locations > Command Line Tools.' >&2
  exit 1
fi
xcrun --sdk iphoneos --show-sdk-version

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$FRONTEND_DIR"
npm ci
npm run build
npx cap sync ios

python3 - <<'PY'
import hashlib, json
from pathlib import Path
dist = Path('dist')
public = Path('ios/App/App/public')
files = [p for p in dist.rglob('*') if p.is_file()]
for source in files:
    target = public / source.relative_to(dist)
    if not target.is_file() or hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
        raise SystemExit('iOS UI mismatch: ' + str(source))
config = json.loads(Path('ios/App/App/capacitor.config.json').read_text())
if config.get('server', {}).get('url'):
    raise SystemExit('Remove development server.url before installing the bundled app.')
print(f'PASS: {len(files)} production web files match the iOS bundle exactly.')
PY

echo 'Ready: select App > Signing & Capabilities > your Apple Team in Xcode.'
echo 'Connect the iPhone, select it as the destination, then press Run.'
echo 'In the app, save the current backend PC LAN address (not localhost).'
if (( OPEN_XCODE )); then
  npx cap open ios
fi

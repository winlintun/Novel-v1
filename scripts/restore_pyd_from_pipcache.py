"""One-off recovery: restore deleted *.pyd native extensions into the venv.

A bad `find . -name "*.pyd" -delete` wiped every compiled extension in env/.
There is no network, but pip's http-v2 cache still holds the original wheels.
This walks that cache, and for each cached wheel whose package+version matches
what is installed in the venv, extracts only the *.pyd members back into
site-packages. Non-matching versions and already-present files are skipped.
"""

import sys
import zipfile
from pathlib import Path

CACHE = Path.home() / "AppData/Local/pip/cache/http-v2"
SITE = Path("env/Lib/site-packages").resolve()


def installed_versions() -> dict[str, str]:
    """Map normalized package name -> installed version from *.dist-info dirs."""
    versions = {}
    for di in SITE.glob("*.dist-info"):
        meta = di.name[: -len(".dist-info")]
        if "-" not in meta:
            continue
        name, ver = meta.rsplit("-", 1)
        versions[name.replace("_", "-").lower()] = ver
    return versions


def wheel_id(zf: zipfile.ZipFile):
    """Return (normalized_name, version) from a wheel's dist-info, or None."""
    for n in zf.namelist():
        if n.endswith(".dist-info/METADATA"):
            meta = n.split("/")[0][: -len(".dist-info")]
            if "-" in meta:
                name, ver = meta.rsplit("-", 1)
                return name.replace("_", "-").lower(), ver
    return None


def main() -> int:
    if not CACHE.is_dir():
        print(f"pip cache not found: {CACHE}")
        return 1

    versions = installed_versions()
    restored = 0
    pkgs_touched = set()

    for body in CACHE.rglob("*.body"):
        if not zipfile.is_zipfile(body):
            continue
        try:
            with zipfile.ZipFile(body) as zf:
                wid = wheel_id(zf)
                if not wid:
                    continue
                name, ver = wid
                # Only restore wheels matching the installed version exactly.
                if versions.get(name) != ver:
                    continue
                pyds = [n for n in zf.namelist() if n.endswith(".pyd")]
                if not pyds:
                    continue
                for member in pyds:
                    dest = SITE / member
                    if dest.exists():
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as out:
                        out.write(src.read())
                    restored += 1
                    pkgs_touched.add(name)
                    print(f"  restored {member}")
        except (zipfile.BadZipFile, OSError) as e:
            print(f"  skip {body.name}: {e}")

    print(f"\nRestored {restored} .pyd file(s) across {len(pkgs_touched)} package(s): "
          f"{', '.join(sorted(pkgs_touched)) or '(none)'}")
    return 0 if restored else 2


if __name__ == "__main__":
    sys.exit(main())

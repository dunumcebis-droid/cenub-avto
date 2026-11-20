#!/usr/bin/env python3
"""Build a public_html ZIP from the reviewed, explicit public-file list."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import time
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parent.parent
ROOT_FILES = {
    "index.html", "about.html", "support.html", "terms.html", "privacy.html",
    "reset-password.html", "robots.txt", "sitemap.xml",
}
ASSET_PATH = re.compile(
    r"assets/(?:site\.css|branding/avtounvan-logo\.png|"
    r"js/[0-9]{2}-[a-z0-9-]+\.js|images/[0-9a-f]{64}\.(?:jpg|png))"
)


def public_files():
    paths = json.loads((ROOT / "deployment/public-files.json").read_text())["files"]
    if not isinstance(paths, list) or len(paths) != 77:
        raise ValueError("The reviewed allowlist must contain exactly 77 files.")
    seen, files = set(), []
    for name in paths:
        if not isinstance(name, str):
            raise ValueError("Every public path must be a string.")
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in name
                or relative.as_posix() != name or name in seen
                or not (name in ROOT_FILES or ASSET_PATH.fullmatch(name))):
            raise ValueError(f"Unsafe or non-public allowlist path: {name!r}")
        source = ROOT
        for part in relative.parts:
            source = source / part
            if source.is_symlink():
                raise ValueError(f"Symlinks cannot be published: {name}")
        if not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing or invalid public file: {name}")
        seen.add(name)
        files.append((name, source.read_bytes()))
    if not ROOT_FILES.issubset(seen):
        raise ValueError("The allowlist is missing a required root page or SEO file.")
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--index-only", action="store_true",
                        help="Build an index.html patch for an already deployed full site.")
    args = parser.parse_args()
    output = args.output.absolute()
    if (output.is_symlink() or output.resolve().is_relative_to(ROOT)
            or output.suffix.lower() != ".zip" or not output.parent.is_dir()):
        parser.error("Output must be a ZIP outside the repository in an existing temporary directory.")
    files = public_files()
    if args.index_only:
        files = [(name, content) for name, content in files if name == "index.html"]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".zip", delete=False) as handle:
            temporary = Path(handle.name)
        build_time = time.gmtime()[:6]
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            for name, content in files:
                info = ZipInfo(name, date_time=build_time)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, content)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(json.dumps({
        "output": str(output), "files": len(files),
        "uncompressed_bytes": sum(len(content) for _, content in files),
        "zip_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }))


if __name__ == "__main__":
    main()

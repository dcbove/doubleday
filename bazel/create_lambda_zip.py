"""Build a Lambda deployment zip with prefix stripping and SQL remapping.

Invoked by the lambda_zip Bazel rule. Reads a manifest file where each line
is ``source_path<TAB>zip_path``, then writes a deterministic zip archive
(sorted entries, fixed timestamp) so that Terraform's filebase64sha256 is
stable across identical builds.
"""

import sys
import zipfile

# Fixed timestamp for deterministic zips (2024-01-01 00:00:00).
FIXED_DATE = (2024, 1, 1, 0, 0, 0)


def main() -> None:
    """Entry point: read manifest, write zip."""
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <output.zip> <manifest.txt>", file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]
    manifest_path = sys.argv[2]

    entries: list[tuple[str, str]] = []
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            source_path, zip_path = line.split("\t", 1)
            entries.append((source_path, zip_path))

    # Sort by zip path for deterministic ordering.
    entries.sort(key=lambda e: e[1])

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for source_path, zip_path in entries:
            info = zipfile.ZipInfo(filename=zip_path, date_time=FIXED_DATE)
            info.external_attr = 0o644 << 16
            with open(source_path, "rb") as src:
                zf.writestr(info, src.read())


if __name__ == "__main__":
    main()

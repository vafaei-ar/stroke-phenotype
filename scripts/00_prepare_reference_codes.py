#!/usr/bin/env python
"""Create canonical code-list CSVs from the historical reference files.

This script is intentionally limited to code-list files. It validates the known
historical file hashes and schemas before writing standardized copies under
reference/. It never reads or writes patient-level data.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

LIPID_SHA256 = "89524fe32e4f08d4e297873d8a48dbb9ebafcf56d9bcd0b42f8217f14444747a"
REHAB_SHA256 = "c85255d34eff3cb2f8dcfabea56e8a37906d54b779f8ead661d577b879ee4854"

LIPID_ROWS = 214
REHAB_ROWS = 65


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_validated_reference(
    path: Path,
    *,
    expected_sha256: str,
    expected_columns: tuple[str, str],
    expected_rows: int,
    code_name: str,
    description_name: str,
) -> pd.DataFrame:
    observed_sha256 = sha256_file(path)
    if observed_sha256 != expected_sha256:
        raise ValueError(
            f"Unexpected SHA-256 for {path}: {observed_sha256}; "
            f"expected {expected_sha256}"
        )

    df = pd.read_csv(path, dtype="string", keep_default_na=False)
    if tuple(df.columns) != expected_columns:
        raise ValueError(
            f"Unexpected columns for {path}: {list(df.columns)}; "
            f"expected {list(expected_columns)}"
        )
    if len(df) != expected_rows:
        raise ValueError(
            f"Unexpected row count for {path}: {len(df)}; expected {expected_rows}"
        )

    out = df.rename(
        columns={
            expected_columns[0]: code_name,
            expected_columns[1]: description_name,
        }
    ).copy()
    for column in out.columns:
        out[column] = out[column].str.strip()

    if out[code_name].eq("").any():
        raise ValueError(f"Blank codes found in {path}")

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lipid", required=True, help="Historical lipid code-list CSV")
    parser.add_argument("--rehab", required=True, help="Historical rehabilitation code-list CSV")
    parser.add_argument("--out-dir", default="reference")
    args = parser.parse_args()

    lipid_path = Path(args.lipid)
    rehab_path = Path(args.rehab)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lipid = read_validated_reference(
        lipid_path,
        expected_sha256=LIPID_SHA256,
        expected_columns=("LOINC_NUM", "COMPONENT"),
        expected_rows=LIPID_ROWS,
        code_name="loinc_code",
        description_name="component",
    )
    rehab = read_validated_reference(
        rehab_path,
        expected_sha256=REHAB_SHA256,
        expected_columns=("CPT Code", "Description"),
        expected_rows=REHAB_ROWS,
        code_name="cpt_code",
        description_name="description",
    )

    lipid_out = out_dir / "lipid_loinc.csv"
    rehab_out = out_dir / "rehab_cpt.csv"
    lipid.to_csv(lipid_out, index=False)
    rehab.to_csv(rehab_out, index=False)

    print(f"Wrote {len(lipid):,} lipid rows to {lipid_out}")
    print(f"Wrote {len(rehab):,} rehabilitation rows to {rehab_out}")
    print("Source hashes matched the historical reference files.")


if __name__ == "__main__":
    main()

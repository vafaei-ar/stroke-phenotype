#!/usr/bin/env python
"""Run count-based validation for all centers in a local configuration file."""

from __future__ import annotations

import argparse

from stroke_phenotype.io import write_table
from stroke_phenotype.validation import validate_centers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    metrics = validate_centers(args.config)
    write_table(metrics, args.out)


if __name__ == "__main__":
    main()

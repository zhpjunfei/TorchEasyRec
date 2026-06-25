# Copyright (c) 2025, Alibaba Group;
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import collections
import sys

import pyarrow.parquet as pq


def main():
    """Check feature distribution in parquet files."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_path", required=True, help="Glob pattern for parquet files"
    )
    parser.add_argument(
        "--feature_name", default="gender", help="Feature column to inspect"
    )
    parser.add_argument(
        "--num_files", type=int, default=3, help="Number of files to read"
    )
    parser.add_argument(
        "--show_values", type=int, default=20, help="Number of top values to show"
    )
    args = parser.parse_args()

    import glob

    files = sorted(glob.glob(args.input_path))[: args.num_files]
    if not files:
        print(f"No files found at {args.input_path}")
        sys.exit(1)

    print(f"Reading {len(files)} files: {files[0]} ... {files[-1]}")

    all_values = []
    total_rows = 0
    for f in files:
        table = pq.read_table(f, columns=[args.feature_name])
        total_rows += len(table)
        col = table[args.feature_name]
        # col is potentially list<item: string>
        for row in col.to_pylist():
            if row is not None:
                all_values.extend(v for v in row)

    counter = collections.Counter(all_values)

    print(f"\nTotal rows: {total_rows}")
    print(f"Total values (after flattening lists): {len(all_values)}")
    print(f"Unique values: {len(counter)}\n")
    print(f"{'Value':<40} {'Count':>8} {'%':>8}")
    print("-" * 60)
    for v, n in counter.most_common(args.show_values):
        print(f"{str(v)[:40]:<40} {n:>8} {n / total_rows * 100:>7.2f}%")
    if len(counter) > args.show_values:
        print(f"... ({len(counter) - args.show_values} more values)")


if __name__ == "__main__":
    main()

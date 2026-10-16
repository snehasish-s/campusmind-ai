import argparse
import csv
from pathlib import Path


def generate(path, count=1000):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(["roll_no", "full_name", "email", "department", "graduation_year", "cgpa", "active_backlogs", "phone"])
        for i in range(1, count + 1):
            writer.writerow(
                [
                    f"SYN2027{i:05d}",
                    f"Synthetic Student {i:04d}",
                    f"student{i:05d}@example.com",
                    ["CSE", "ECE", "EE", "ME", "CE"][(i - 1) % 5],
                    2027,
                    round(6 + (i % 40) / 10, 1),
                    int(i % 17 == 0),
                    "",
                ]
            )
    print(f"Created {count} entirely synthetic records at {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--output", default="data/synthetic-students.csv")
    args = parser.parse_args()
    generate(args.output, args.count)

"""Print a StatsCollector summary."""
from typing import Any

MAX_ERRORS_SHOWN = 5


def print_summary(summary: dict[str, Any]) -> None:
    """Print the dictionary StatsCollector.get_summary() returns."""
    files = summary['files']
    print("\n=== Code Scanning Summary ===")
    print(f"Time elapsed: {summary['time_elapsed']:.2f} seconds")
    print(f"Files scanned: {files['total']} ({files['skipped']} skipped, {files['error']} errors)")
    print(f"File types: {files['by_type']}")
    print("Elements found:")
    for name, count in summary['elements'].items():
        print(f"  - {name}: {count}")

    print("Unique elements:")
    for name, count in summary['unique'].items():
        print(f"  - {name}: {count}")

    errors = summary['errors']
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        for error in errors[:MAX_ERRORS_SHOWN]:
            print(f"  - {error['file']}: {error['type']} - {error['message']}")

        if len(errors) > MAX_ERRORS_SHOWN:
            print(f"  ... and {len(errors) - MAX_ERRORS_SHOWN} more errors")

    print("=== End of Summary ===")

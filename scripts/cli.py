"""
CLI interface for testing reports locally
"""

import sys
from report_generator import ReportGenerator


def main():
    if len(sys.argv) < 2:
        print("Usage: python cli.py [sales|profit|stock|pending] [args...]")
        sys.exit(1)

    generator = ReportGenerator()
    command = sys.argv[1]

    if command == 'sales':
        if len(sys.argv) != 4:
            print("Usage: python cli.py sales START_DATE END_DATE")
            sys.exit(1)
        report = generator.sales_report(sys.argv[2], sys.argv[3])
        print(report)

    elif command == 'profit':
        if len(sys.argv) != 4:
            print("Usage: python cli.py profit START_DATE END_DATE")
            sys.exit(1)
        report = generator.profit_analysis(sys.argv[2], sys.argv[3])
        print(report)

    elif command == 'stock':
        threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        report = generator.stock_alert(threshold)
        print(report)

    elif command == 'pending':
        report = generator.pending_orders()
        print(report)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == '__main__':
    main()

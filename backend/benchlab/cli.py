"""
backend/benchlab/cli.py - Main Command-Line Interface for BenchLab
Implements CLI commands defined in SPEC.md section 15.
"""

import sys
import argparse
from pathlib import Path


def cmd_doctor(args):
    """Run pre-flight environment checks."""
    from scripts.doctor import run_doctor
    return run_doctor()


def cmd_dataset(args):
    action = args.dataset_action
    if action == "generate":
        print(f"[Dataset] Sẽ sinh dữ liệu với profile='{args.profile}', seed={args.seed} (Phase 2)")
    elif action == "load":
        print(f"[Dataset] Sẽ nạp dataset='{args.dataset}', track='{args.track}' (Phase 2)")
    elif action == "validate":
        print(f"[Dataset] Sẽ kiểm tra tính toàn vẹn và tương đương dataset='{args.dataset}' (Phase 2)")
    else:
        print("Vui lòng chọn: generate, load, hoặc validate.")
    return 0


def cmd_indexes(args):
    action = args.index_action
    if action == "apply":
        print(f"[Indexes] Sẽ áp dụng profile='{args.profile}' cho dataset='{args.dataset}' (Phase 2)")
    return 0


def cmd_test(args):
    print(f"[Test] Sẽ chạy test suite='{args.suite}' (Phase 1, 3, 7)")
    return 0


def cmd_benchmark(args):
    if args.dry_run:
        print(f"[Benchmark] DRY-RUN cho experiment='{args.experiment}' (Phase 4)")
    else:
        print(f"[Benchmark] Chạy experiment='{args.experiment}' (Phase 4, 8)")
    return 0


def cmd_report(args):
    print(f"[Report] Xuất báo cáo cho experiment_id='{args.experiment_id}' (Phase 6)")
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="python -m benchlab",
        description="BenchLab CLI - Đánh giá hiệu năng truy vấn PostgreSQL vs MongoDB (SPEC v1.0)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Lệnh chức năng")

    # doctor
    sub_doctor = subparsers.add_parser("doctor", help="Kiểm tra môi trường pre-flight")
    sub_doctor.set_defaults(func=cmd_doctor)

    # dataset
    sub_dataset = subparsers.add_parser("dataset", help="Quản lý dataset (generate, load, validate)")
    dataset_subs = sub_dataset.add_subparsers(dest="dataset_action", help="Hành động dataset")

    ds_gen = dataset_subs.add_parser("generate", help="Sinh dữ liệu giả lập chuẩn")
    ds_gen.add_argument("--profile", default="small", choices=["fixture", "small", "medium", "large"], help="Profile dữ liệu")
    ds_gen.add_argument("--seed", type=int, default=42, help="Seed giả ngẫu nhiên")

    ds_load = dataset_subs.add_parser("load", help="Nạp dữ liệu vào CSDL")
    ds_load.add_argument("--dataset", required=True, help="Tên dataset (vd: small-seed42)")
    ds_load.add_argument("--track", default="all", choices=["all", "A", "B"], help="Mô hình track")

    ds_val = dataset_subs.add_parser("validate", help="Kiểm tra tính tương đương của dataset")
    ds_val.add_argument("--dataset", required=True, help="Tên dataset")
    sub_dataset.set_defaults(func=cmd_dataset)

    # indexes
    sub_indexes = subparsers.add_parser("indexes", help="Quản lý cấu hình index")
    idx_subs = sub_indexes.add_subparsers(dest="index_action", help="Hành động index")
    idx_apply = idx_subs.add_parser("apply", help="Áp dụng profile index")
    idx_apply.add_argument("--profile", required=True, choices=["I0", "I1"], help="Profile index")
    idx_apply.add_argument("--dataset", required=True, help="Tên dataset")
    sub_indexes.set_defaults(func=cmd_indexes)

    # test
    sub_test = subparsers.add_parser("test", help="Chạy bộ kiểm thử")
    sub_test.add_argument("--suite", default="smoke", choices=["smoke", "functional", "correctness", "all"], help="Suite kiểm thử")
    sub_test.set_defaults(func=cmd_test)

    # benchmark
    sub_bench = subparsers.add_parser("benchmark", help="Chạy thực nghiệm hiệu năng")
    sub_bench.add_argument("--experiment", required=True, choices=["E0", "E1", "E2", "E3", "E4"], help="Mã thí nghiệm")
    sub_bench.add_argument("--dry-run", action="store_true", help="Ước tính ma trận và thời gian, không đo thật")
    sub_bench.set_defaults(func=cmd_benchmark)

    # report
    sub_report = subparsers.add_parser("report", help="Xuất báo cáo kết quả thí nghiệm")
    sub_report.add_argument("--experiment-id", required=True, help="Mã thí nghiệm thực tế")
    sub_report.set_defaults(func=cmd_report)

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

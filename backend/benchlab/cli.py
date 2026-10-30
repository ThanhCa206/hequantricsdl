"""backend/benchlab/cli.py - Main Command-Line Interface for BenchLab
Implements CLI commands defined in SPEC.md section 15.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


def cmd_doctor(args):
    """Run pre-flight environment checks."""
    from scripts.doctor import run_doctor
    return run_doctor()


def cmd_health(args):
    """Check health and ping PostgreSQL and MongoDB adapters directly."""
    from app.adapters.mongodb import MongoAdapter
    from app.adapters.postgres import PostgresAdapter
    from app.config import get_settings

    settings = get_settings()
    print("=" * 70)
    print(" BenchLab Database Adapters Health Check")
    print("=" * 70)

    pg = PostgresAdapter(settings=settings)
    pg_status = pg.health(timeout_seconds=2.0)
    print(f"[*] PostgreSQL ({settings.postgres_host}:{settings.postgres_port}):")
    print(f"    - Trạng thái: {'ONLINE' if pg_status.is_healthy else 'OFFLINE'}")
    if pg_status.is_healthy:
        print(f"    - Phiên bản:  {pg_status.version}")
        print(f"    - Độ trễ:     {pg_status.latency_ms:.2f} ms")
    else:
        print(f"    - Chi tiết:   {pg_status.error}")

    mongo = MongoAdapter(settings=settings)
    mongo_status = mongo.health(timeout_seconds=2.0)
    print(f"\n[*] MongoDB ({settings.mongo_host}:{settings.mongo_port}):")
    print(f"    - Trạng thái: {'ONLINE' if mongo_status.is_healthy else 'OFFLINE'}")
    if mongo_status.is_healthy:
        print(f"    - Phiên bản:  {mongo_status.version}")
        print(f"    - Độ trễ:     {mongo_status.latency_ms:.2f} ms")
    else:
        print(f"    - Chi tiết:   {mongo_status.error}")

    print("=" * 70)
    return 0 if (pg_status.is_healthy and mongo_status.is_healthy) else 1


def cmd_dataset(args):
    """Manage dataset generation, validation, and loading."""
    from app.datasets.generator import DataGenerator
    from app.datasets.loader import DatasetLoader
    from app.datasets.validator import validate_dataset
    from configs.profiles import load_profile

    action = args.dataset_action
    if action == "generate":
        profile = load_profile(args.profile)
        seed = args.seed
        print(f"[*] Đang sinh dữ liệu streaming cho profile='{args.profile}', seed={seed}...")

        gen = DataGenerator(profile, seed=seed)
        customers = []
        for b in gen.stream_customers():
            customers.extend([c.to_dict() for c in b])

        products = []
        for b in gen.stream_products():
            products.extend([p.to_dict() for p in b])

        orders = []
        items = []
        for ord_b, it_b, _ in gen.stream_orders():
            orders.extend([o.to_dict() for o in ord_b])
            items.extend([it.to_dict() for it in it_b])

        report = validate_dataset(customers, products, orders, items)
        print("=" * 70)
        print(" KẾT QUẢ SINH VÀ KIỂM TRA DỮ LIỆU:")
        print(f"    - Customers:      {report.total_customers:,}")
        print(f"    - Products:       {report.total_products:,}")
        print(f"    - Orders:         {report.total_orders:,}")
        print(f"    - Order Items:    {report.total_items:,}")
        print(f"    - Total Revenue:  {report.total_revenue_minor:,} VND")
        print(f"    - SHA-256 Hash:   {report.checksum_sha256}")
        print(f"    - Tính hợp lệ:    {'PASS (100% hợp lệ)' if report.is_valid else 'FAIL'}")
        print("=" * 70)
        return 0 if report.is_valid else 1

    elif action == "validate":
        profile_name = getattr(args, "profile", "fixture") or "fixture"
        profile = load_profile(profile_name)
        print(f"[*] Kiểm tra toàn vẹn và canonical checksum cho profile='{profile_name}'...")
        gen = DataGenerator(profile, seed=42)
        customers = [c.to_dict() for b in gen.stream_customers() for c in b]
        products = [p.to_dict() for b in gen.stream_products() for p in b]
        orders = []
        items = []
        for ord_b, it_b, _ in gen.stream_orders():
            orders.extend([o.to_dict() for o in ord_b])
            items.extend([it.to_dict() for it in it_b])

        report = validate_dataset(customers, products, orders, items)
        print(f"[*] Kết quả: {'HỢP LỆ (PASS)' if report.is_valid else 'LỖI'}")
        print(f"    - Checksum SHA-256: {report.checksum_sha256}")
        return 0 if report.is_valid else 1

    elif action == "load":
        from app.adapters.mongodb import MongoAdapter
        from app.adapters.postgres import PostgresAdapter
        from app.config import get_settings
        from app.domain.schema import apply_mongo_schema, apply_postgres_schema

        profile_name = args.dataset.split("-")[0] if "-" in args.dataset else args.dataset
        try:
            profile = load_profile(profile_name)
        except ValueError:
            profile = load_profile("fixture")

        settings = get_settings()
        gen = DataGenerator(profile, seed=42)
        print(f"[*] Nạp dữ liệu profile='{profile.name}' vào CSDL (Track: {args.track})...")

        # Load PostgreSQL
        pg = PostgresAdapter(settings=settings)
        pg_health = pg.health(timeout_seconds=2.0)
        if pg_health.is_healthy:
            apply_postgres_schema(pg)
            res_pg = DatasetLoader.load_postgres(pg, gen)
            print(f"    - PostgreSQL: Nạp {res_pg.num_orders} đơn trong {res_pg.duration_seconds}s")
        else:
            print("    - PostgreSQL: OFFLINE (Bỏ qua nạp PG)")

        # Load MongoDB
        mongo = MongoAdapter(settings=settings)
        mongo_health = mongo.health(timeout_seconds=2.0)
        if mongo_health.is_healthy:
            apply_mongo_schema(mongo)
            res_mg = DatasetLoader.load_mongo(mongo, gen, track=args.track)
            print(f"    - MongoDB: Nạp {res_mg.num_orders} đơn trong {res_mg.duration_seconds}s")
        else:
            print("    - MongoDB: OFFLINE (Bỏ qua nạp Mongo)")

        return 0
    else:
        print("Vui lòng chọn: generate, load, hoặc validate.")
        return 0


def cmd_indexes(args):
    """Manage index application (I0 and I1)."""
    from app.adapters.mongodb import MongoAdapter
    from app.adapters.postgres import PostgresAdapter
    from app.config import get_settings
    from configs.indexes import apply_indexes

    action = args.index_action
    if action == "apply":
        profile = args.profile  # "I0" or "I1"
        settings = get_settings()
        print(f"[*] Áp dụng cấu hình index '{profile}'...")

        pg = PostgresAdapter(settings=settings)
        if pg.health(timeout_seconds=2.0).is_healthy:
            res_pg = apply_indexes("postgresql", profile, pg)
            print(f"    - PostgreSQL: {res_pg['applied_indexes']} ({res_pg['duration_ms']} ms)")
        else:
            print("    - PostgreSQL: OFFLINE")

        mongo = MongoAdapter(settings=settings)
        if mongo.health(timeout_seconds=2.0).is_healthy:
            res_mg = apply_indexes("mongodb", profile, mongo)
            print(f"    - MongoDB: {res_mg['applied_indexes']} ({res_mg['duration_ms']} ms)")
        else:
            print("    - MongoDB: OFFLINE")
    return 0


def cmd_test(args):
    """Execute pytest test suite."""
    suite = args.suite
    suite_map = {
        "smoke": ["tests/unit"],
        "functional": ["tests/integration"],
        "correctness": ["tests/correctness"],
        "all": ["tests/"],
    }
    targets = suite_map.get(suite, ["tests/"])
    print(f"[Test] Chạy test suite='{suite}' ({', '.join(targets)})...")

    cmd = [sys.executable, "-m", "pytest"] + targets + ["-v"]
    res = subprocess.run(cmd)
    return res.returncode


def cmd_benchmark(args):
    from app.benchmark.runner import BenchmarkConfig, BenchmarkRunner

    exp_name = args.experiment.upper()
    now_tag = time.strftime("%Y%m%d_%H%M%S")
    exp_id = f"{exp_name}-{now_tag}"

    if exp_name == "E0":
        config = BenchmarkConfig(
            experiment_id=exp_id,
            mode="L",
            dataset="fixture-seed42",
            profile="fixture",
            index_profile="I1",
            queries=["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7_offset", "Q7_keyset", "Q8_track_a"],
            engines=["postgresql", "mongodb"],
            repeats=1,
            fixed_count=20,
            warmup_min_requests=5,
            warmup_min_duration_s=0.2,
        )
    elif exp_name == "E1":
        config = BenchmarkConfig(
            experiment_id=exp_id,
            mode="L",
            dataset="small-seed42",
            profile="small",
            index_profile="I1",
            queries=["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7_offset", "Q7_keyset", "Q8_track_a"],
            engines=["postgresql", "mongodb"],
            repeats=5,
            fixed_count=1000,
        )
    elif exp_name == "E2":
        config = BenchmarkConfig(
            experiment_id=exp_id,
            mode="T",
            dataset="medium-seed42",
            profile="medium",
            index_profile="I1",
            queries=["Q1", "Q3", "Q5", "Q8_track_a"],
            engines=["postgresql", "mongodb"],
            repeats=5,
            concurrency=8,
            duration_seconds=60.0,
        )
    elif exp_name == "E3":
        config = BenchmarkConfig(
            experiment_id=exp_id,
            mode="L",
            dataset="medium-seed42",
            profile="medium",
            index_profile="I0",
            queries=["Q8_track_b"],
            engines=["mongodb"],
            repeats=5,
            fixed_count=1000,
        )
    else:
        config = BenchmarkConfig(
            experiment_id=exp_id,
            mode="L",
            dataset="fixture-seed42",
            profile="fixture",
            index_profile="I1",
        )

    runner = BenchmarkRunner(config)

    if args.dry_run:
        plan = runner.dry_run()
        print("=" * 70)
        print(f" KẾT QUẢ DRY-RUN CHO THỰC NGHIỆM {exp_name}")
        print("=" * 70)
        print(f" - Experiment ID:          {plan['experiment_id']}")
        print(f" - Mode:                   {plan['mode']}")
        print(f" - Tổng số cells đo:       {plan['total_cells']}")
        print(f" - Ước tính thời gian:     ~{plan['estimated_duration_minutes']} phút")
        print("=" * 70)
        return 0

    print(f"[*] Đang thực thi benchmark {exp_name} ({exp_id})...")
    res = runner.run()
    print("=" * 70)
    print(f" KẾT QUẢ THỰC NGHIỆM {exp_name}:")
    print(f" - Trạng thái:     {res['status']}")
    print(f" - Tổng samples:   {res['total_samples']}")
    print(f" - Thời gian đo:   {res['wall_elapsed_seconds']}s")
    print(f" - Thư mục kết quả: results/{exp_id}")
    print("=" * 70)
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

    # health
    sub_health = subparsers.add_parser("health", help="Kiểm tra sức khỏe kết nối CSDL")
    sub_health.set_defaults(func=cmd_health)

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

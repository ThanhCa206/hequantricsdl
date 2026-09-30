#!/usr/bin/env python3
"""
scripts/doctor.py - Diagnostic and Environment Pre-flight Verification Script
Kiểm tra các yêu cầu tiên quyết cho môi trường thực nghiệm theo SPEC.md (Phase 0).
"""

import sys
import os
import shutil
import socket
import platform
import subprocess
from pathlib import Path


def format_bytes(bytes_val: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} PB"


def check_port_free(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) != 0
    except Exception:
        return False


def run_command_output(cmd: list[str]) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        out = (res.stdout + " " + res.stderr).strip()
        return (res.returncode == 0, out)
    except Exception as e:
        return (False, str(e))


def run_doctor() -> int:
    print("=" * 70)
    print(" BenchLab Environment Doctor (Pre-flight Checks)")
    print(" SPEC Version: 1.0 | Target: PostgreSQL vs MongoDB Benchmark")
    print("=" * 70)

    issues: list[dict] = []
    warnings: list[dict] = []
    passes: list[dict] = []

    # 1. OS & Platform
    os_info = f"{platform.system()} {platform.release()} ({platform.version()})"
    print(f"\n[1] Hệ điều hành: {os_info}")
    passes.append({"name": "OS", "detail": os_info})

    # 2. CPU
    cpu_count = os.cpu_count() or 1
    print(f"[2] CPU Logical Processors: {cpu_count}")
    if cpu_count < 4:
        warnings.append({
            "name": "CPU",
            "detail": f"Host có {cpu_count} logical cores (< 4). Cần hạ quota container DB xuống 1-2 vCPU để tránh nghẽn OS/worker.",
            "remedy": "Thiết lập CONTAINER_CPU_LIMIT=1.0 hoặc 2.0 trong .env."
        })
    else:
        passes.append({"name": "CPU", "detail": f"{cpu_count} logical processors available."})

    # 3. Memory
    mem_total_gb = None
    try:
        if platform.system() == "Windows":
            cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize"]
            ok, out = run_command_output(cmd)
            if ok and out.strip().isdigit():
                mem_kb = int(out.strip())
                mem_total_gb = mem_kb / (1024 * 1024)
    except Exception:
        pass

    if mem_total_gb:
        print(f"[3] RAM tổng: {mem_total_gb:.2f} GiB")
        if mem_total_gb < 8.0:
            warnings.append({
                "name": "RAM",
                "detail": f"RAM {mem_total_gb:.2f} GiB nhỏ hơn 8 GiB khuyến nghị.",
                "remedy": "Giới hạn memory container DB ở mức 1024m-2048m và chỉ chạy profile small/medium."
            })
        else:
            passes.append({"name": "RAM", "detail": f"{mem_total_gb:.2f} GiB"})
    else:
        print("[3] RAM: Không thể đọc tự động.")

    # 4. Disk Space
    cwd = Path.cwd()
    disk_usage = shutil.disk_usage(cwd)
    free_gb = disk_usage.free / (1024**3)
    print(f"[4] Dung lượng ổ đĩa tại {cwd.drive or '/'}: {free_gb:.2f} GB trống")
    if free_gb < 15.0:
        issues.append({
            "name": "Ổ đĩa",
            "detail": f"Dung lượng trống còn {free_gb:.2f} GB (< 15 GB). Có nguy cơ đầy đĩa khi sinh dữ liệu large hoặc Docker images.",
            "remedy": "Giải phóng dung lượng ổ đĩa hoặc chuyển dữ liệu benchmark sang phân vùng lớn hơn."
        })
    else:
        passes.append({"name": "Ổ đĩa", "detail": f"{free_gb:.2f} GB trống"})

    # 5. Python Version
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    print(f"[5] Python: {py_str}")
    if (py_ver.major, py_ver.minor) < (3, 11):
        issues.append({
            "name": "Python",
            "detail": f"Phiên bản Python hiện tại là {py_str}, cần >= 3.11.",
            "remedy": "Cài đặt Python 3.11 hoặc 3.12 từ python.org."
        })
    else:
        passes.append({"name": "Python", "detail": f"Python {py_str}"})

    # 6. Node & npm
    node_ok, node_out = run_command_output(["node", "--version"])
    npm_ok, npm_out = run_command_output(["npm", "--version"])
    if node_ok:
        print(f"[6] Node.js: {node_out.strip()} | npm: {npm_out.strip() if npm_ok else 'N/A'}")
        passes.append({"name": "Node.js", "detail": f"{node_out.strip()}"})
    else:
        warnings.append({
            "name": "Node.js",
            "detail": "Không tìm thấy Node.js trong PATH. Frontend Vite sẽ không thể khởi động nếu không có Node hoặc Docker container.",
            "remedy": "Cài đặt Node.js LTS (>= 18) hoặc dùng winget install OpenJS.NodeJS.LTS."
        })

    # 7. Git
    git_ok, git_out = run_command_output(["git", "--version"])
    if git_ok:
        print(f"[7] Git: {git_out.strip()}")
        passes.append({"name": "Git", "detail": git_out.strip()})
    else:
        issues.append({
            "name": "Git",
            "detail": "Không tìm thấy Git trong PATH.",
            "remedy": "Cài đặt Git for Windows."
        })

    # 8. Docker & Docker Compose
    docker_ok, docker_out = run_command_output(["docker", "--version"])
    compose_ok, compose_out = run_command_output(["docker", "compose", "version"])
    if docker_ok and compose_ok:
        print(f"[8] Docker: {docker_out.strip()} | Compose: {compose_out.strip()}")
        # Check docker daemon running
        daemon_ok, _ = run_command_output(["docker", "info"])
        if daemon_ok:
            passes.append({"name": "Docker", "detail": f"Daemon online. {docker_out.strip()}"})
        else:
            warnings.append({
                "name": "Docker Daemon",
                "detail": "Docker CLI có sẵn nhưng Docker Daemon chưa chạy.",
                "remedy": "Khởi động Docker Desktop trước khi chạy Phase 1."
            })
    else:
        warnings.append({
            "name": "Docker / Compose",
            "detail": "Docker hoặc Docker Compose chưa được cài đặt hoặc chưa có trong PATH.",
            "remedy": "Để chạy theo kiến trúc container: Cài đặt Docker Desktop for Windows (hoặc cấu hình native PostgreSQL 17 và MongoDB 8.0 cho môi trường phát triển cục bộ)."
        })
        print(f"[8] Docker: CHƯA PHÁT HIỆN TRONG PATH (Cần thiết cho Phase 1 hạ tầng)")

    # 9. Ports check
    ports_to_check = [
        (5432, "PostgreSQL"),
        (27017, "MongoDB"),
        (8000, "FastAPI Backend"),
        (5173, "Vite Frontend"),
    ]
    print("\n[9] Kiểm tra các port dịch vụ:")
    ports_conflict = False
    for port, service in ports_to_check:
        free = check_port_free("127.0.0.1", port)
        status = "TRỐNG (Sẵn sàng)" if free else "ĐANG BỊ CHIẾM DỤNG"
        print(f"    - Port {port:5d} ({service:18s}): {status}")
        if not free:
            ports_conflict = True
            warnings.append({
                "name": f"Port {port}",
                "detail": f"Port {port} ({service}) đang có tiến trình lắng nghe.",
                "remedy": f"Dừng dịch vụ chiếm port {port} hoặc đổi cấu hình port trong file .env."
            })
    if not ports_conflict:
        passes.append({"name": "Ports", "detail": "Tất cả các port (5432, 27017, 8000, 5173) đều trống."})

    # 10. Config files
    print("\n[10] Kiểm tra tệp cấu hình:")
    env_example = Path(".env.example")
    env_file = Path(".env")
    if env_example.exists():
        print("    - .env.example: TỒN TẠI (Đạt chuẩn)")
        passes.append({"name": ".env.example", "detail": "Đã tạo mẫu môi trường."})
    else:
        issues.append({
            "name": ".env.example",
            "detail": "Thiếu tệp .env.example mẫu.",
            "remedy": "Tạo lại tệp .env.example theo quy định."
        })

    if not env_file.exists() and env_example.exists():
        print("    - .env: CHƯA CÓ (Tạo tự động từ .env.example cho local dev)")
        shutil.copy(env_example, env_file)
        print("      -> Đã tạo .env từ .env.example")
    elif env_file.exists():
        print("    - .env: TỒN TẠI")

    # Summary
    print("\n" + "=" * 70)
    print(" KẾT QUẢ ĐÁNH GIÁ MÔI TRƯỜNG PRE-FLIGHT")
    print("=" * 70)
    print(f" Pass: {len(passes)} mục")
    print(f" Cảnh báo: {len(warnings)} mục")
    print(f" Lỗi chặn: {len(issues)} mục")

    if warnings:
        print("\n--- CÁC CẢNH BÁO / LƯU Ý HẠ TẦNG ---")
        for w in warnings:
            print(f" [!] {w['name']}: {w['detail']}")
            print(f"     Cách xử lý: {w['remedy']}")

    if issues:
        print("\n--- CÁC LỖI CẦN KHẮC PHỤC ---")
        for err in issues:
            print(f" [X] {err['name']}: {err['detail']}")
            print(f"     Cách xử lý: {err['remedy']}")
        return 1

    print("\n>>> KẾT LUẬN PRE-FLIGHT: ĐẠT ĐIỀU KIỆN TIÊN QUYẾT CHO PHASE 0 <<<")
    return 0


if __name__ == "__main__":
    sys.exit(run_doctor())

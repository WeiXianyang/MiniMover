#!/usr/bin/env python3
"""Start the real PC-ASR + Jetson hospital-guide defense demo.

This is a local orchestration helper for Windows. It starts/reuses the real
PC FunASR WebSocket server, uploads the non-secret Jetson launcher, then runs
that launcher over SSH. It never creates mock ASR, KB, telemetry, or navigation
responses.
"""

from __future__ import annotations

import argparse
import getpass
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import paramiko
except ImportError as exc:  # pragma: no cover - exercised by the launcher itself
    raise SystemExit(
        "缺少 paramiko。请执行: python -m pip install paramiko"
    ) from exc


DEFAULT_JETSON_HOST = "192.168.202.171"
DEFAULT_JETSON_USER = "jetson"
DEFAULT_ASR_PORT = 8765


def _listener(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _local_ip_for(target: str) -> str:
    """Select the local interface used to reach the Jetson without sending data."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((target, 1))
        return sock.getsockname()[0]


def _process_command(pid: int) -> str:
    if os.name != "nt":
        return ""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _listener_command(port: int) -> str:
    """Return the command owning a Windows listener, when it is observable."""
    if os.name != "nt":
        return ""
    script = (
        f"$pid=(Get-NetTCPConnection -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess); "
        "if ($pid) { (Get-CimInstance Win32_Process -Filter \"ProcessId=$pid\").CommandLine }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _start_pc_asr(project_dir: Path, port: int, force_restart: bool) -> None:
    if _listener(port) and not force_restart:
        print(f"[OK] PC ASR 已在监听 0.0.0.0:{port}，复用现有真实进程")
        return

    if _listener(port) and force_restart:
        raise RuntimeError(
            f"端口 {port} 已被占用；为避免误杀非 ASR 服务，请先手动停止占用进程"
        )

    log_dir = project_dir / "tmp"
    log_dir.mkdir(exist_ok=True)
    stdout_path = log_dir / "hospital_guide_pc_asr.out.log"
    stderr_path = log_dir / "hospital_guide_pc_asr.err.log"
    out = stdout_path.open("ab")
    err = stderr_path.open("ab")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(
        [sys.executable, str(project_dir / "voice_assistant" / "pc_asr_server.py"), str(port)],
        cwd=project_dir,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=err,
        creationflags=creationflags,
    )
    # The child owns the file descriptors after Popen returns.
    out.close()
    err.close()
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if _listener(port):
            command = _process_command(proc.pid)
            if command and "pc_asr_server.py" not in command:
                raise RuntimeError(f"端口 {port} 被非预期进程占用: {command}")
            print(f"[OK] PC ASR 已启动，pid={proc.pid}，日志={stderr_path}")
            return
        if proc.poll() is not None:
            raise RuntimeError(
                f"PC ASR 启动失败，退出码={proc.returncode}，日志={stderr_path}"
            )
        time.sleep(0.5)
    raise TimeoutError(f"等待 PC ASR 监听 {port} 超时，日志={stderr_path}")


def _exec_remote(client: paramiko.SSHClient, command: str) -> str:
    stdin, stdout, stderr = client.exec_command(command, get_pty=False, timeout=90)
    # The remote launcher uses sudo -n and never receives the SSH password in
    # the command line or through the remote shell environment.
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    if stdout.channel.recv_exit_status() != 0:
        raise RuntimeError(f"Jetson launcher failed with exit code {stdout.channel.recv_exit_status()}")
    return out


def _upload_launcher(client: paramiko.SSHClient, local_path: Path, remote_path: str) -> None:
    sftp = client.open_sftp()
    try:
        sftp.put(str(local_path), remote_path)
        sftp.chmod(remote_path, 0o755)
    finally:
        sftp.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="MiniMover hospital-guide live demo launcher")
    parser.add_argument("--jetson-host", default=os.getenv("MINIMOVER_JETSON_HOST", DEFAULT_JETSON_HOST))
    parser.add_argument("--jetson-user", default=os.getenv("MINIMOVER_JETSON_USER", DEFAULT_JETSON_USER))
    parser.add_argument("--asr-port", type=int, default=int(os.getenv("MINIMOVER_ASR_PORT", DEFAULT_ASR_PORT)))
    parser.add_argument("--asr-host", default=os.getenv("MINIMOVER_ASR_HOST"))
    parser.add_argument("--force-pc-asr", action="store_true", help="拒绝复用已占用端口；不会自动杀进程")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parents[1]
    launcher = project_dir / "scripts" / "start_hospital_guide_demo.sh"
    if not launcher.is_file():
        raise FileNotFoundError(launcher)
    if args.asr_port <= 0 or args.asr_port > 65535:
        raise ValueError("ASR port must be between 1 and 65535")

    asr_host = args.asr_host or _local_ip_for(args.jetson_host)
    print("=== MiniMover 医院导诊现场启动 ===")
    print(f"Jetson: {args.jetson_user}@{args.jetson_host}")
    print(f"PC ASR: {asr_host}:{args.asr_port}")
    _start_pc_asr(project_dir, args.asr_port, args.force_pc_asr)

    password = os.getenv("MINIMOVER_SSH_PASSWORD") or getpass.getpass(
        f"请输入 {args.jetson_user}@{args.jetson_host} SSH 密码（不会写入文件）: "
    )
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            args.jetson_host,
            username=args.jetson_user,
            password=password,
            timeout=10,
            look_for_keys=True,
            allow_agent=True,
        )
        remote_path = f"/home/{args.jetson_user}/MiniMover/scripts/start_hospital_guide_demo.sh"
        _upload_launcher(client, launcher, remote_path)
        command = (
            f"cd /home/{args.jetson_user}/MiniMover && "
            f"bash scripts/start_hospital_guide_demo.sh "
            f"--asr-host {asr_host!r} --asr-port {args.asr_port}"
        )
        _exec_remote(client, command)
    finally:
        client.close()

    print("=== 现场演示链已启动 ===")
    print(f"控制台: http://{args.jetson_host}:5000/hospital-guide")
    print(f"地图选点: http://{args.jetson_host}:5000/nav/patrol")
    print("真实演示: 你好小北 -> 我要去内科 -> 好的，带我去")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("已取消")
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)

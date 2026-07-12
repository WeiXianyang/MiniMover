# Fire Smoke Detection Module Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the runnable fire/smoke YOLOv5 detector, complete training dataset, training records, and verifiable source-history evidence from `E:\fire-smoke-detect-yolov4` into an independent `E:\MiniMover\fire_smoke_detection` module, then delete the source only after all critical verification passes.

**Architecture:** Keep the legacy YOLOv5 inference implementation isolated under `yolov5_runtime/` and expose a small path-stable `detector.py` launcher. Store reproducibility materials under `training/`, Git/worktree evidence under `evidence/`, and validate copies with a dedicated manifest verifier before any deletion. Windows and Linux/Jetson launchers call the same Python entry point.

**Tech Stack:** Python 3, legacy PyTorch/YOLOv5, OpenCV, PowerShell, Bash, Git/Git LFS, `unittest`.

---

## File Map

**Create:**

- `fire_smoke_detection/detector.py` — stable cross-platform command launcher.
- `fire_smoke_detection/yolov5_runtime/` — legacy YOLOv5 detector, models, and utilities.
- `fire_smoke_detection/model/best.pt` — trained fire/smoke model.
- `fire_smoke_detection/run.bat` and `run.sh` — Windows and Linux/Jetson launchers.
- `fire_smoke_detection/requirements*.txt` and `README.md` — installation and usage.
- `fire_smoke_detection/tests/` — launcher and migration-verifier tests.
- `fire_smoke_detection/tools/verify_migration.py` — copy verifier and checksum writer.
- `fire_smoke_detection/training/` — complete VOC2020 dataset, runs, scripts, source snapshot, and original docs.
- `fire_smoke_detection/evidence/` — results, Git bundle, patch, inventory, hashes, provenance, and migration report.

**Modify:**

- `.gitattributes` — track model, dataset image, and video formats with Git LFS.
- `.gitignore` — ignore only `fire_smoke_detection/output/`.

**Do not modify:** `traffic_light/`, `app_pc.py`, root `run.sh`, `oh-ai-car-ros-app/`, vehicle control, or Web application files.

---

### Task 1: Capture the Source State Before Copying

**Files:**
- Create: `fire_smoke_detection/evidence/source-history.bundle`
- Create: `fire_smoke_detection/evidence/working-tree.patch`
- Create: `fire_smoke_detection/evidence/untracked-files.txt`
- Create: `fire_smoke_detection/evidence/provenance.txt`

- [ ] **Step 1: Verify absolute source and target paths**

```powershell
$source = (Resolve-Path -LiteralPath 'E:\fire-smoke-detect-yolov4').Path
$target = [System.IO.Path]::GetFullPath('E:\MiniMover\fire_smoke_detection')
if ($source -ne 'E:\fire-smoke-detect-yolov4') { throw "Unexpected source: $source" }
if (-not $target.StartsWith('E:\MiniMover\', [System.StringComparison]::OrdinalIgnoreCase)) { throw "Unexpected target: $target" }
```

Expected: no exception.

- [ ] **Step 2: Create evidence directories**

```powershell
New-Item -ItemType Directory -Force -Path 'E:\MiniMover\fire_smoke_detection\evidence\results' | Out-Null
```

- [ ] **Step 3: Export and verify committed history**

```powershell
git -C 'E:\fire-smoke-detect-yolov4' bundle create 'E:\MiniMover\fire_smoke_detection\evidence\source-history.bundle' --all
git bundle verify 'E:\MiniMover\fire_smoke_detection\evidence\source-history.bundle'
```

Expected: bundle is reported as okay.

- [ ] **Step 4: Export tracked changes and full untracked inventory**

```powershell
git -C 'E:\fire-smoke-detect-yolov4' diff --binary HEAD | Set-Content -Encoding UTF8 'E:\MiniMover\fire_smoke_detection\evidence\working-tree.patch'
git -C 'E:\fire-smoke-detect-yolov4' status --short --untracked-files=all | Set-Content -Encoding UTF8 'E:\MiniMover\fire_smoke_detection\evidence\untracked-files.txt'
```

Expected: patch includes modified YOLOv5 code; inventory includes `VOC2020/`, `yolov5/runs/`, and `yolov5/scripts/`.

- [ ] **Step 5: Write provenance**

```powershell
$commit = git -C 'E:\fire-smoke-detect-yolov4' rev-parse HEAD
$branch = git -C 'E:\fire-smoke-detect-yolov4' branch --show-current
$status = git -C 'E:\fire-smoke-detect-yolov4' status --short --untracked-files=all
@('Source path: E:\fire-smoke-detect-yolov4','Target path: E:\MiniMover\fire_smoke_detection','Migration date: 2026-07-11',"Source commit: $commit","Source branch: $branch",'Source status before migration:',$status) | Set-Content -Encoding UTF8 'E:\MiniMover\fire_smoke_detection\evidence\provenance.txt'
```

- [ ] **Step 6: Commit source-state evidence only**

```powershell
git add -- 'fire_smoke_detection/evidence/source-history.bundle' 'fire_smoke_detection/evidence/working-tree.patch' 'fire_smoke_detection/evidence/untracked-files.txt' 'fire_smoke_detection/evidence/provenance.txt'
git commit -m "Preserve fire smoke project history"
```

---

### Task 2: Configure Large-File Tracking

**Files:**
- Modify: `.gitattributes`
- Modify: `.gitignore`

- [ ] **Step 1: Require Git LFS before copying large artifacts**

```powershell
git lfs version
git lfs install --local
```

Expected: version prints. If unavailable, stop and do not delete the source.

- [ ] **Step 2: Append missing LFS rules**

```gitattributes
*.pt filter=lfs diff=lfs merge=lfs -text
*.weights filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.avi filter=lfs diff=lfs merge=lfs -text
```

- [ ] **Step 3: Ignore only runtime output**

```gitignore
# Fire/smoke detector runtime output
/fire_smoke_detection/output/
```

- [ ] **Step 4: Verify and commit rules**

```powershell
git check-attr filter -- 'fire_smoke_detection/model/best.pt' 'fire_smoke_detection/training/VOC2020/JPEGImages/example.jpg' 'fire_smoke_detection/evidence/results/example.mp4'
git add -- '.gitattributes' '.gitignore'
git commit -m "Configure fire smoke artifact tracking"
```

Expected: all sample paths report `filter: lfs`; only the two rule files are committed.

---

### Task 3: Copy Runtime, Training, and Evidence Assets

**Files:**
- Create: `fire_smoke_detection/model/`, `yolov5_runtime/`, `training/`, `samples/`, and `evidence/results/`.

- [ ] **Step 1: Create target directories**

```powershell
@('model','yolov5_runtime','training/source','training/original_readmes','samples','output') | ForEach-Object { New-Item -ItemType Directory -Force -Path (Join-Path 'E:\MiniMover\fire_smoke_detection' $_) | Out-Null }
```

- [ ] **Step 2: Copy runtime model and inference code**

```powershell
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\best.pt' 'E:\MiniMover\fire_smoke_detection\model\best.pt'
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\detect.py' 'E:\MiniMover\fire_smoke_detection\yolov5_runtime\detect.py'
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\models' 'E:\MiniMover\fire_smoke_detection\yolov5_runtime\models' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\utils' 'E:\MiniMover\fire_smoke_detection\yolov5_runtime\utils' -Recurse
```

- [ ] **Step 3: Copy complete training evidence**

```powershell
Copy-Item 'E:\fire-smoke-detect-yolov4\VOC2020' 'E:\MiniMover\fire_smoke_detection\training\VOC2020' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\runs' 'E:\MiniMover\fire_smoke_detection\training\runs' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\scripts' 'E:\MiniMover\fire_smoke_detection\training\scripts' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\models' 'E:\MiniMover\fire_smoke_detection\training\source\models' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\utils' 'E:\MiniMover\fire_smoke_detection\training\source\utils' -Recurse
@('train.py','test.py','hubconf.py','requirements.txt') | ForEach-Object { Copy-Item (Join-Path 'E:\fire-smoke-detect-yolov4\yolov5' $_) (Join-Path 'E:\MiniMover\fire_smoke_detection\training\source' $_) }
Copy-Item 'E:\fire-smoke-detect-yolov4\yolov5\data\fire_smoke.yaml' 'E:\MiniMover\fire_smoke_detection\training\source\fire_smoke.original.yaml'
```

- [ ] **Step 4: Create relocatable dataset YAML**

Create `fire_smoke_detection/training/fire_smoke.yaml`:

```yaml
train: ./VOC2020/train.txt
val: ./VOC2020/val.txt
nc: 2
names: ['fire', 'smoke']
```

The paths are resolved relative to the `training/` directory by the documented reproduction command.

- [ ] **Step 5: Copy original documentation and visual evidence**

```powershell
Copy-Item 'E:\fire-smoke-detect-yolov4\README.md' 'E:\MiniMover\fire_smoke_detection\training\original_readmes\README.md'
Copy-Item 'E:\fire-smoke-detect-yolov4\LICENSE' 'E:\MiniMover\fire_smoke_detection\training\original_readmes\LICENSE'
Copy-Item 'E:\fire-smoke-detect-yolov4\readmes' 'E:\MiniMover\fire_smoke_detection\training\original_readmes\readmes' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\result' 'E:\MiniMover\fire_smoke_detection\evidence\results\result' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\xml_lab' 'E:\MiniMover\fire_smoke_detection\evidence\results\xml_lab' -Recurse
Copy-Item 'E:\fire-smoke-detect-yolov4\result\result_demo.jpg' 'E:\MiniMover\fire_smoke_detection\samples\result_demo.jpg'
```

- [ ] **Step 6: Remove copied caches only inside verified target**

```powershell
$root=(Resolve-Path 'E:\MiniMover\fire_smoke_detection').Path
if($root -ne 'E:\MiniMover\fire_smoke_detection'){throw "Unexpected cleanup root: $root"}
Get-ChildItem $root -Directory -Recurse -Force | Where-Object Name -in '__pycache__','.pytest_cache' | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
Get-ChildItem $root -File -Recurse -Force | Where-Object Extension -in '.pyc','.pyo' | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }
```

---

### Task 4: Build the Stable Detector Launcher with TDD

**Files:**
- Create: `fire_smoke_detection/tests/test_detector.py`
- Create: `fire_smoke_detection/detector.py`

- [ ] **Step 1: Write failing tests**

```python
# fire_smoke_detection/tests/test_detector.py
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import detector

class DetectorTests(unittest.TestCase):
    def test_defaults_are_module_relative(self):
        command = detector.build_command(["--source", "0"])
        self.assertEqual(Path(command[1]), ROOT / "yolov5_runtime" / "detect.py")
        self.assertEqual(command[2:6], ["--weights", str(ROOT / "model" / "best.pt"), "--output", str(ROOT / "output")])

    def test_relative_source_uses_calling_directory(self):
        with patch("detector.Path.cwd", return_value=Path("C:/captures")):
            command = detector.build_command(["--source", "fire.jpg"])
        self.assertEqual(Path(command[command.index("--source") + 1]), Path("C:/captures/fire.jpg"))

    def test_url_is_unchanged(self):
        source = "rtsp://camera/live"
        command = detector.build_command(["--source", source])
        self.assertEqual(command[command.index("--source") + 1], source)

    @patch("detector.subprocess.run")
    def test_main_returns_child_code(self, run):
        run.return_value.returncode = 7
        self.assertEqual(detector.main(["--source", "0"]), 7)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Confirm failure**

```powershell
python -m unittest discover -s 'fire_smoke_detection/tests' -p 'test_detector.py' -v
```

Expected: import failure because `detector.py` does not exist.

- [ ] **Step 3: Implement launcher**

```python
#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT / "yolov5_runtime" / "detect.py"
MODEL = ROOT / "model" / "best.pt"
OUTPUT = ROOT / "output"

def _normalize_source(value: str) -> str:
    if value.isdigit() or urlparse(value).scheme.lower() in {"http", "https", "rtsp", "rtmp"}:
        return value
    path = Path(value).expanduser()
    return str((path if path.is_absolute() else Path.cwd() / path).resolve())

def build_command(arguments: Sequence[str]) -> list[str]:
    forwarded = list(arguments)
    if "--source" in forwarded:
        index = forwarded.index("--source") + 1
        if index >= len(forwarded):
            raise ValueError("--source requires a value")
        forwarded[index] = _normalize_source(forwarded[index])
    else:
        forwarded += ["--source", "0"]
    return [sys.executable, str(LEGACY), "--weights", str(MODEL), "--output", str(OUTPUT)] + forwarded

def main(arguments: Sequence[str] | None = None) -> int:
    return subprocess.run(build_command(sys.argv[1:] if arguments is None else arguments), cwd=str(ROOT), check=False).returncode

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Confirm tests pass and commit runtime slice**

```powershell
python -m unittest discover -s 'fire_smoke_detection/tests' -p 'test_detector.py' -v
git add -- 'fire_smoke_detection/detector.py' 'fire_smoke_detection/tests/test_detector.py' 'fire_smoke_detection/yolov5_runtime' 'fire_smoke_detection/model/best.pt'
git commit -m "Add standalone fire smoke detector launcher"
```

Expected: 4 tests pass and `best.pt` is committed through LFS.


### Task 5: Add Cross-Platform Launchers and Documentation

**Files:**
- Create: `fire_smoke_detection/run.bat`
- Create: `fire_smoke_detection/run.sh`
- Create: `fire_smoke_detection/requirements.txt`
- Create: `fire_smoke_detection/requirements-jetson.txt`
- Create: `fire_smoke_detection/README.md`

- [ ] **Step 1: Create Windows launcher**

```bat
@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (echo [ERROR] Python was not found on PATH.& exit /b 1)
if not exist "model\best.pt" (echo [ERROR] Missing model\best.pt& exit /b 1)
if "%~1"=="" (python detector.py --source 0 --view-img) else (python detector.py %*)
exit /b %errorlevel%
```

- [ ] **Step 2: Create Linux/Jetson launcher with LF line endings**

```bash
#!/usr/bin/env bash
set -euo pipefail
MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MODULE_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "[ERROR] $PYTHON_BIN was not found." >&2; exit 1; }
[[ -f "$MODULE_DIR/model/best.pt" ]] || { echo "[ERROR] Missing model/best.pt" >&2; exit 1; }
if [[ $# -eq 0 ]]; then exec "$PYTHON_BIN" detector.py --source 0 --view-img; else exec "$PYTHON_BIN" detector.py "$@"; fi
```

- [ ] **Step 3: Create common requirements**

```text
matplotlib>=3.2.2
numpy>=1.18.5
opencv-python>=4.1.2
Pillow
PyYAML>=5.3
scipy>=1.4.1
torch>=1.6.0
torchvision>=0.7.0
tqdm>=4.41.0
```

- [ ] **Step 4: Create Jetson guidance**

```text
# Install torch and torchvision from NVIDIA wheels matching JetPack/CUDA first.
-r requirements.txt
```

- [ ] **Step 5: Write README with exact commands and evidence map**

The README must include:

```markdown
# MiniMover 烟火识别模块

使用 `model/best.pt` 识别 `fire` 与 `smoke`，独立于车牌、红绿灯和 Web 控制模块。

## Windows
```powershell
cd E:\MiniMover\fire_smoke_detection
python -m pip install -r requirements.txt
run.bat --source 0 --view-img
run.bat --source samples\result_demo.jpg
```

## Linux/Jetson
先安装与 JetPack 匹配的 NVIDIA PyTorch/torchvision，再运行：
```bash
cd /path/to/MiniMover/fire_smoke_detection
python3 -m pip install -r requirements.txt
bash run.sh --source 0 --view-img
bash run.sh --source samples/result_demo.jpg
```

## 目录
- `training/VOC2020/`：完整数据集。
- `training/runs/`：训练与验证记录。
- `training/source/`：训练源码与数据配置。
- `evidence/`：Git 历史、未提交修改、哈希和迁移报告。

结果默认写入 `output/`，旧版检测器每次运行会重新创建该目录。
```

Also document CPU/GPU selection, the `fire`/`smoke` classes, reproduction YAML, original license location, and the fact that ONNX/TensorRT conversion is out of scope.

- [ ] **Step 6: Validate and commit**

```powershell
python -m py_compile 'fire_smoke_detection/detector.py'
Select-String 'fire_smoke_detection/run.bat' -Pattern 'python detector.py'
Select-String 'fire_smoke_detection/run.sh' -Pattern 'exec.*detector.py'
# Run when Bash is available:
bash -n 'fire_smoke_detection/run.sh'
git add -- 'fire_smoke_detection/run.bat' 'fire_smoke_detection/run.sh' 'fire_smoke_detection/requirements.txt' 'fire_smoke_detection/requirements-jetson.txt' 'fire_smoke_detection/README.md'
git commit -m "Document fire smoke detector usage"
```

Expected: static checks pass; only launcher/docs files are committed.

---

### Task 6: Implement Migration Verification with TDD

**Files:**
- Create: `fire_smoke_detection/tests/test_verify_migration.py`
- Create: `fire_smoke_detection/tools/verify_migration.py`
- Create: `fire_smoke_detection/evidence/checksums.sha256`

- [ ] **Step 1: Write failing verifier tests**

```python
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import verify_migration

class VerifyMigrationTests(unittest.TestCase):
    def test_tree_summary_ignores_caches(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/"data").mkdir(); (root/"data/a.txt").write_text("abc")
            (root/"__pycache__").mkdir(); (root/"__pycache__/a.pyc").write_bytes(b"ignored")
            self.assertEqual(verify_migration.tree_summary(root), verify_migration.TreeSummary(1,3))

    def test_compare_trees_accepts_equal_content(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left=Path(a); right=Path(b); (left/"x").write_text("same"); (right/"x").write_text("same")
            self.assertEqual(verify_migration.compare_trees(left,right), [])

    def test_write_checksums_uses_sha256(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); target=root/"model.pt"; target.write_bytes(b"model"); manifest=root/"m.txt"
            verify_migration.write_checksums(root,[target],manifest)
            self.assertEqual(manifest.read_text().strip(), f"{hashlib.sha256(b'model').hexdigest()}  model.pt")
```

- [ ] **Step 2: Confirm failure**

```powershell
python -m unittest discover -s 'fire_smoke_detection/tests' -p 'test_verify_migration.py' -v
```

Expected: import failure.

- [ ] **Step 3: Implement verifier**

```python
#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
IGNORED_DIRS={"__pycache__",".pytest_cache"}; IGNORED_SUFFIXES={".pyc",".pyo"}

@dataclass(frozen=True)
class TreeSummary:
    file_count:int
    byte_count:int

def iter_files(root:Path)->Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(p in IGNORED_DIRS for p in path.relative_to(root).parts) and path.suffix.lower() not in IGNORED_SUFFIXES:
            yield path

def tree_summary(root:Path)->TreeSummary:
    files=list(iter_files(root)); return TreeSummary(len(files),sum(p.stat().st_size for p in files))

def sha256(path:Path)->str:
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""): digest.update(block)
    return digest.hexdigest()

def compare_trees(source:Path,target:Path)->list[str]:
    left={p.relative_to(source):p for p in iter_files(source)}; right={p.relative_to(target):p for p in iter_files(target)}; problems=[]
    for rel in sorted(left.keys()|right.keys()):
        if rel not in left: problems.append(f"extra target file: {rel}")
        elif rel not in right: problems.append(f"missing target file: {rel}")
        elif left[rel].stat().st_size!=right[rel].stat().st_size: problems.append(f"size mismatch: {rel}")
        elif sha256(left[rel])!=sha256(right[rel]): problems.append(f"hash mismatch: {rel}")
    return problems

def write_checksums(root:Path,files:Iterable[Path],manifest:Path)->None:
    manifest.write_text("\n".join(f"{sha256(p)}  {p.relative_to(root).as_posix()}" for p in files)+"\n",encoding="utf-8")

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--source-root",type=Path,required=True); parser.add_argument("--target-root",type=Path,required=True); parser.add_argument("--manifest",type=Path,required=True); args=parser.parse_args()
    mappings=[(args.source_root/"VOC2020",args.target_root/"training/VOC2020"),(args.source_root/"yolov5/runs",args.target_root/"training/runs"),(args.source_root/"yolov5/scripts",args.target_root/"training/scripts"),(args.source_root/"result",args.target_root/"evidence/results/result"),(args.source_root/"xml_lab",args.target_root/"evidence/results/xml_lab")]
    problems=[]
    for source,target in mappings: problems += [f"{source.name}: {p}" for p in compare_trees(source,target)]
    source_model=args.source_root/"yolov5/best.pt"; target_model=args.target_root/"model/best.pt"
    if sha256(source_model)!=sha256(target_model): problems.append("model: hash mismatch")
    critical=[target_model,args.target_root/"training/fire_smoke.yaml",args.target_root/"evidence/source-history.bundle",args.target_root/"evidence/working-tree.patch",args.target_root/"evidence/provenance.txt"]
    write_checksums(args.target_root,critical,args.manifest)
    for problem in problems: print(f"FAIL: {problem}")
    if problems:return 1
    print("Migration tree verification passed."); return 0

if __name__=="__main__": raise SystemExit(main())
```

- [ ] **Step 4: Run tests and full source/target comparison**

```powershell
python -m unittest discover -s 'fire_smoke_detection/tests' -p 'test_verify_migration.py' -v
python 'fire_smoke_detection/tools/verify_migration.py' --source-root 'E:\fire-smoke-detect-yolov4' --target-root 'E:\MiniMover\fire_smoke_detection' --manifest 'E:\MiniMover\fire_smoke_detection\evidence\checksums.sha256'
```

Expected: 3 tests pass and migration verification prints PASS. Any mismatch blocks deletion.

- [ ] **Step 5: Commit training evidence and verifier**

```powershell
git add -- 'fire_smoke_detection/tools' 'fire_smoke_detection/tests/test_verify_migration.py' 'fire_smoke_detection/training' 'fire_smoke_detection/evidence/results' 'fire_smoke_detection/evidence/checksums.sha256' 'fire_smoke_detection/samples'
git commit -m "Preserve fire smoke training evidence"
```

---

### Task 7: Run Full Verification Before Deletion

**Files:**
- Create: `fire_smoke_detection/evidence/migration-report.txt`

- [ ] **Step 1: Confirm unrelated MiniMover files remain untouched**

```powershell
git status --short
```

Expected: pre-existing untracked `app_pc.py`, root `run.sh`, `traffic_light/`, and `oh-ai-car-ros-app/` remain untracked; no unrelated tracked file is modified.

- [ ] **Step 2: Run all unit and syntax checks**

```powershell
python -m unittest discover -s 'fire_smoke_detection/tests' -p 'test_*.py' -v
python -m compileall -q 'fire_smoke_detection' -x 'training[\\/]VOC2020|training[\\/]runs'
git bundle verify 'fire_smoke_detection/evidence/source-history.bundle'
```

Expected: all tests and checks pass.

- [ ] **Step 3: Load model on CPU**

```powershell
$python=if(Test-Path 'E:\fire-smoke-detect-yolov4\.venv\Scripts\python.exe'){'E:\fire-smoke-detect-yolov4\.venv\Scripts\python.exe'}else{'python'}
& $python -c "import sys,torch;sys.path.insert(0,r'E:\MiniMover\fire_smoke_detection\yolov5_runtime');from models.experimental import attempt_load;m=attempt_load(r'E:\MiniMover\fire_smoke_detection\model\best.pt',map_location=torch.device('cpu'));print(m.names)"
```

Expected: prints names containing `fire` and `smoke`. If compatibility fails, fix compatibility before continuing; never alter the model bytes.

- [ ] **Step 4: Run end-to-end sample inference**

```powershell
& $python 'E:\MiniMover\fire_smoke_detection\detector.py' --source 'E:\MiniMover\fire_smoke_detection\samples\result_demo.jpg' --device cpu --conf-thres 0.4
```

Expected: exit 0 and a result file appears in `output/`.

- [ ] **Step 5: Check launchers**

```powershell
cmd /c "E:\MiniMover\fire_smoke_detection\run.bat --help"
# When Bash is available:
bash -n 'E:\MiniMover\fire_smoke_detection\run.sh'
```

- [ ] **Step 6: Write truthful pre-deletion report**

```powershell
$modelHash=(Get-FileHash -Algorithm SHA256 'E:\MiniMover\fire_smoke_detection\model\best.pt').Hash
$data=@(Get-ChildItem 'E:\MiniMover\fire_smoke_detection\training\VOC2020' -File -Recurse -Force)
$runs=@(Get-ChildItem 'E:\MiniMover\fire_smoke_detection\training\runs' -File -Recurse -Force)
@('Migration verification: PASS','Verified on: 2026-07-11',"Model SHA256: $modelHash","Dataset files: $($data.Count)","Dataset bytes: $(($data|Measure-Object Length -Sum).Sum)","Run-record files: $($runs.Count)",'Git bundle verification: PASS','Unit tests: PASS','Model load: PASS','Sample inference: PASS','Source deletion authorized by completed verification.') | Set-Content -Encoding UTF8 'E:\MiniMover\fire_smoke_detection\evidence\migration-report.txt'
```

Do not write PASS for an unexecuted or failed check.

- [ ] **Step 7: Commit report before deletion**

```powershell
git add -- 'fire_smoke_detection/evidence/migration-report.txt'
git commit -m "Record fire smoke migration verification"
```

---

### Task 8: Delete Source Safely and Audit

**Files:**
- Modify: `fire_smoke_detection/evidence/migration-report.txt`

- [ ] **Step 1: Enforce deletion gates**

```powershell
if(-not(Select-String 'E:\MiniMover\fire_smoke_detection\evidence\migration-report.txt' -Pattern '^Migration verification: PASS$')){throw 'Verification not PASS'}
@('model\best.pt','training\VOC2020','training\runs','evidence\source-history.bundle') | ForEach-Object { if(-not(Test-Path (Join-Path 'E:\MiniMover\fire_smoke_detection' $_))){throw "Missing $_"} }
```

- [ ] **Step 2: Verify exact deletion path and parent relationships**

```powershell
$deleteTarget=(Resolve-Path -LiteralPath 'E:\fire-smoke-detect-yolov4').Path
$workspace=(Resolve-Path -LiteralPath 'E:\MiniMover').Path
if($deleteTarget -ne 'E:\fire-smoke-detect-yolov4'){throw "Unexpected target: $deleteTarget"}
if($deleteTarget.StartsWith($workspace,[System.StringComparison]::OrdinalIgnoreCase)){throw 'Source is inside workspace'}
if($workspace.StartsWith($deleteTarget,[System.StringComparison]::OrdinalIgnoreCase)){throw 'Source is workspace parent'}
```

- [ ] **Step 3: Delete using native PowerShell only**

```powershell
Remove-Item -LiteralPath $deleteTarget -Recurse -Force
```

Do not use `cmd`, Bash, wildcards, or string-built deletion commands.

- [ ] **Step 4: Verify source absence and target survival**

```powershell
if(Test-Path 'E:\fire-smoke-detect-yolov4'){throw 'Source still exists'}
@('model\best.pt','training\VOC2020','training\runs','evidence\source-history.bundle','evidence\working-tree.patch') | ForEach-Object { if(-not(Test-Path (Join-Path 'E:\MiniMover\fire_smoke_detection' $_))){throw "Missing target $_"} }
```

- [ ] **Step 5: Append deletion result and run final checks**

```powershell
@('','Source deletion: PASS','Deleted source path: E:\fire-smoke-detect-yolov4','Post-deletion target audit: PASS') | Add-Content -Encoding UTF8 'E:\MiniMover\fire_smoke_detection\evidence\migration-report.txt'
git status --short
git lfs ls-files
git diff --check
python -m unittest discover -s 'fire_smoke_detection/tests' -p 'test_*.py' -v
```

Expected: only report is modified; tests and diff check pass; LFS lists model/images/videos.

- [ ] **Step 6: Commit completion report**

```powershell
git add -- 'fire_smoke_detection/evidence/migration-report.txt'
git commit -m "Complete fire smoke project move"
```

- [ ] **Step 7: Final response**

Report the created module path, Windows/Linux commands, model hash, inference result, dataset/run counts and sizes, Git bundle result, deleted source path, tests run, untouched pre-existing untracked files, and any Jetson GPU checks not performed.

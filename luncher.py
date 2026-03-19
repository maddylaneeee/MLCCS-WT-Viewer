from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, BooleanVar, StringVar, Tk, Toplevel
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from urllib import error as url_error
from urllib import request as url_request


APP_NAME = "MLCCS-wt-viewer"
LAUNCHER_TITLE = "MLCCS WT Luncher"
PROJECT_DIR_NAME = "MLCCS-wt-viewer"
ZIP_URL = "https://lixinchen.ca/docs/MLCCS-wt-viewer.zip"
MAIN_EXE_RELATIVE = Path("dist") / APP_NAME / f"{APP_NAME}.exe"
BUILD_SCRIPT_NAME = "build.ps1"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _install_parent(base_dir: Path) -> Path:
    return base_dir / "installed"


def _staging_root(base_dir: Path) -> Path:
    return _install_parent(base_dir) / "_staging"


def _active_project_dir(base_dir: Path) -> Path:
    return _install_parent(base_dir) / PROJECT_DIR_NAME


def _resolve_main_executable(project_dir: Path) -> Path:
    return project_dir / MAIN_EXE_RELATIVE


def _resolve_project_dir(extract_root: Path) -> Path:
    direct = extract_root / PROJECT_DIR_NAME
    if direct.exists():
        return direct

    candidates = [path for path in extract_root.iterdir() if path.is_dir()]
    for candidate in candidates:
        if (candidate / BUILD_SCRIPT_NAME).exists():
            return candidate
    raise FileNotFoundError(f"Unable to locate extracted project directory in {extract_root}")


def _remove_extracted_noise(project_dir: Path) -> None:
    for relative in (".git",):
        target = project_dir / relative
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)

    for cache_dir in project_dir.rglob("__pycache__"):
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir, ignore_errors=True)


def _powershell_path() -> str:
    for candidate in ("pwsh.exe", "powershell.exe"):
        try:
            completed = subprocess.run(
                [candidate, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            continue
        if completed.returncode == 0:
            return candidate
    raise RuntimeError("PowerShell is required but was not found.")


def _python_command_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []
    executable = Path(sys.executable)
    if not getattr(sys, "frozen", False) and executable.name.lower().startswith("python"):
        candidates.append([str(executable)])
    candidates.extend(
        [
            ["py", "-3.10"],
            ["py", "-3"],
            ["py"],
            ["python"],
            ["python3"],
        ]
    )
    return candidates


def _find_python_command() -> list[str]:
    for candidate in _python_command_candidates():
        try:
            completed = subprocess.run(
                candidate + ["--version"],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            continue
        if completed.returncode == 0:
            return candidate
    raise RuntimeError("Python 3.10 or newer is required to build the downloaded package.")


def _run_logged_process(cmd: list[str], cwd: Path, log) -> int:
    process = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        creationflags=CREATE_NO_WINDOW,
    )
    assert process.stdout is not None
    for line in process.stdout:
        log(line.rstrip())
    return process.wait()


def _ensure_virtualenv(project_dir: Path, log) -> Path:
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python

    python_cmd = _find_python_command()
    log(f"Creating virtual environment with: {' '.join(python_cmd)}")
    rc = _run_logged_process(python_cmd + ["-m", "venv", ".venv"], project_dir, log)
    if rc != 0 or not venv_python.exists():
        raise RuntimeError("Failed to create the virtual environment required by build.ps1.")
    return venv_python


def _download_zip(target_zip: Path, log, status) -> None:
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    req = url_request.Request(ZIP_URL, method="GET")
    with url_request.urlopen(req, timeout=120) as response, target_zip.open("wb") as stream:
        total = int(response.headers.get("Content-Length", "0") or "0")
        downloaded = 0
        status("Downloading package...")
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            stream.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                percent = downloaded * 100.0 / total
                status(f"Downloading package... {percent:.1f}%")
    log(f"Downloaded package to {target_zip}")


def _extract_zip(target_zip: Path, extract_root: Path, log, status) -> Path:
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    status("Extracting package...")
    with zipfile.ZipFile(target_zip, "r") as archive:
        archive.extractall(extract_root)
    project_dir = _resolve_project_dir(extract_root)
    _remove_extracted_noise(project_dir)
    log(f"Extracted package to {project_dir}")
    return project_dir


def _promote_installation(base_dir: Path, staged_project_dir: Path, log) -> Path:
    install_parent = _install_parent(base_dir)
    install_parent.mkdir(parents=True, exist_ok=True)
    final_dir = _active_project_dir(base_dir)
    backup_dir = install_parent / "_backup"

    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)

    if final_dir.exists():
        try:
            final_dir.replace(backup_dir)
            log(f"Backed up existing installation to {backup_dir}")
        except Exception as exc:
            log(f"Could not replace existing installation cleanly: {exc}")
            return staged_project_dir

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    staged_project_dir.replace(final_dir)
    shutil.rmtree(_staging_root(base_dir), ignore_errors=True)
    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)
    log(f"Activated installation at {final_dir}")
    return final_dir


def _desktop_shortcut_path() -> Path:
    return Path.home() / "Desktop" / f"{APP_NAME}.lnk"


def _escape_powershell_literal(value: str) -> str:
    return value.replace("'", "''")


def _create_desktop_shortcut(target_exe: Path) -> Path:
    shortcut_path = _desktop_shortcut_path()
    working_dir = target_exe.parent
    ps = _powershell_path()
    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $shell.CreateShortcut('{_escape_powershell_literal(str(shortcut_path))}'); "
        f"$shortcut.TargetPath = '{_escape_powershell_literal(str(target_exe))}'; "
        f"$shortcut.WorkingDirectory = '{_escape_powershell_literal(str(working_dir))}'; "
        f"$shortcut.IconLocation = '{_escape_powershell_literal(str(target_exe))},0'; "
        "$shortcut.Save()"
    )
    completed = subprocess.run(
        [ps, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=CREATE_NO_WINDOW,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Failed to create shortcut")
    return shortcut_path


def _spawn_detached(executable: Path) -> None:
    subprocess.Popen(
        [str(executable)],
        cwd=str(executable.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    )


def install_package(base_dir: Path, log, status) -> Path:
    temp_zip = Path(tempfile.gettempdir()) / "MLCCS-wt-viewer_download.zip"
    staged_root = _staging_root(base_dir)
    _download_zip(temp_zip, log, status)
    staged_project = _extract_zip(temp_zip, staged_root, log, status)
    _ensure_virtualenv(staged_project, log)

    status("Running build.ps1...")
    powershell = _powershell_path()
    build_script = staged_project / BUILD_SCRIPT_NAME
    rc = _run_logged_process(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(build_script)],
        staged_project,
        log,
    )
    if rc != 0:
        raise RuntimeError("build.ps1 failed.")

    final_project = _promote_installation(base_dir, staged_project, log)
    final_exe = _resolve_main_executable(final_project)
    if not final_exe.exists():
        raise FileNotFoundError(f"Built executable not found: {final_exe}")
    status("Installation completed.")
    return final_exe


class LuncherApp:
    def __init__(self) -> None:
        self.base_dir = _runtime_base_dir()
        self.root = Tk()
        self.root.title(LAUNCHER_TITLE)
        self.root.geometry("780x540")
        self.root.minsize(720, 460)
        self.status_var = StringVar(value="Status: idle")
        self._busy = False
        self._pending_launch: Path | None = None
        self._build_ui()
        self._log(f"base_dir={self.base_dir}")
        self._log(f"install_root={_install_parent(self.base_dir)}")
        self._log(f"package_url={ZIP_URL}")

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root)
        top.pack(fill=X, padx=8, pady=8)

        self.install_button = ttk.Button(top, text="下载并安装", command=lambda: self._run_async(self._install_action))
        self.install_button.pack(side=LEFT, padx=4)

        ttk.Button(top, text="打开安装目录", command=self._open_install_dir).pack(side=LEFT, padx=4)
        ttk.Button(top, text="打开已安装程序目录", command=self._open_built_dir).pack(side=LEFT, padx=4)
        ttk.Button(top, text="退出", command=self._close).pack(side=RIGHT, padx=4)

        ttk.Label(self.root, textvariable=self.status_var).pack(fill=X, padx=10)

        self.log = ScrolledText(self.root, height=24)
        self.log.pack(fill=BOTH, expand=True, padx=8, pady=8)

    def _set_busy(self, value: bool) -> None:
        self._busy = value
        state = "disabled" if value else "normal"
        self.install_button.configure(state=state)

    def _run_async(self, fn) -> None:
        if self._busy:
            return
        self._set_busy(True)
        threading.Thread(target=fn, daemon=True).start()

    def _log(self, text: str) -> None:
        def append() -> None:
            self.log.insert(END, f"{text}\n")
            self.log.see(END)

        self.root.after(0, append)

    def _set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(f"Status: {text}"))

    def _install_action(self) -> None:
        try:
            final_exe = install_package(self.base_dir, self._log, self._set_status)
        except url_error.URLError as exc:
            self._log(f"Download failed: {exc}")
            self.root.after(0, lambda: messagebox.showerror(LAUNCHER_TITLE, f"下载失败：{exc}"))
            self.root.after(0, lambda: self._set_busy(False))
            return
        except Exception as exc:
            self._log(f"Installation failed: {exc}")
            self.root.after(0, lambda: messagebox.showerror(LAUNCHER_TITLE, f"安装失败：{exc}"))
            self.root.after(0, lambda: self._set_busy(False))
            return

        self._log(f"Main executable ready: {final_exe}")
        self.root.after(0, lambda: self._show_completion_dialog(final_exe))

    def _show_completion_dialog(self, final_exe: Path) -> None:
        dialog = Toplevel(self.root)
        dialog.title("安装完成")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        create_shortcut = BooleanVar(value=True)
        launch_after_close = BooleanVar(value=True)

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=BOTH, expand=True)

        ttk.Label(frame, text="MLCCS-wt-viewer 已安装完成。").pack(anchor="w")
        ttk.Label(frame, text=str(final_exe), wraplength=540).pack(anchor="w", pady=(6, 12))

        ttk.Checkbutton(frame, text="在桌面创建快捷方式", variable=create_shortcut).pack(anchor="w", pady=2)
        ttk.Checkbutton(frame, text="关闭 luncher 后启动程序", variable=launch_after_close).pack(anchor="w", pady=2)

        actions = ttk.Frame(frame)
        actions.pack(fill=X, pady=(14, 0))

        def apply_choices(close_launcher: bool) -> None:
            try:
                if create_shortcut.get():
                    shortcut = _create_desktop_shortcut(final_exe)
                    self._log(f"Shortcut created: {shortcut}")
            except Exception as exc:
                self._log(f"Shortcut creation failed: {exc}")
                messagebox.showwarning(LAUNCHER_TITLE, f"创建快捷方式失败：{exc}")

            self._set_busy(False)
            dialog.destroy()

            if close_launcher and launch_after_close.get():
                self._pending_launch = final_exe
                self._close()

        ttk.Button(actions, text="完成", command=lambda: apply_choices(False)).pack(side=RIGHT, padx=4)
        ttk.Button(actions, text="关闭 Luncher", command=lambda: apply_choices(True)).pack(side=RIGHT, padx=4)

        dialog.protocol("WM_DELETE_WINDOW", lambda: apply_choices(False))

    def _open_install_dir(self) -> None:
        target = _install_parent(self.base_dir)
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))

    def _open_built_dir(self) -> None:
        target = _active_project_dir(self.base_dir)
        if not target.exists():
            messagebox.showinfo(LAUNCHER_TITLE, "尚未安装程序。")
            return
        os.startfile(str(target))

    def _close(self) -> None:
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
        if self._pending_launch is not None:
            try:
                _spawn_detached(self._pending_launch)
            except Exception as exc:
                messagebox.showerror(LAUNCHER_TITLE, f"启动程序失败：{exc}")


def main() -> int:
    app = LuncherApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

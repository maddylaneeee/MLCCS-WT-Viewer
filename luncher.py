from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
import hashlib
import string
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, BooleanVar, StringVar, Tk, Toplevel
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from urllib import error as url_error
from urllib import request as url_request


APP_NAME = "MLCCS-wt-viewer"
LAUNCHER_TITLE = "MLCCS WT Luncher"
INSTALL_DIR_NAME = APP_NAME
PACKAGE_FILE_NAME = "MLCCS-wt-viewer-win64.zip"
ZIP_URL = f"https://lixinchen.ca/docs/{PACKAGE_FILE_NAME}"
SHA256_URL = f"{ZIP_URL}.sha256"
MAIN_EXE_NAME = f"{APP_NAME}.exe"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _runtime_data_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def _install_parent(base_dir: Path) -> Path:
    return base_dir / "installed"


def _staging_root(base_dir: Path) -> Path:
    return _install_parent(base_dir) / "_staging"


def _active_install_dir(base_dir: Path) -> Path:
    return _install_parent(base_dir) / INSTALL_DIR_NAME


def _resolve_main_executable(install_dir: Path) -> Path:
    return install_dir / MAIN_EXE_NAME


def _looks_like_app_root(path: Path) -> bool:
    return (path / MAIN_EXE_NAME).exists()


def _resolve_package_dir(extract_root: Path) -> Path:
    direct = extract_root / INSTALL_DIR_NAME
    if _looks_like_app_root(direct):
        return direct

    if _looks_like_app_root(extract_root):
        return extract_root

    candidates = [path for path in extract_root.iterdir() if path.is_dir()]
    for candidate in candidates:
        if _looks_like_app_root(candidate):
            return candidate
    raise FileNotFoundError(f"Unable to locate extracted application directory in {extract_root}")


def _bundled_package_path() -> Path | None:
    candidates = [
        _runtime_data_dir() / PACKAGE_FILE_NAME,
        Path(__file__).resolve().parent / "dist" / PACKAGE_FILE_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _bundled_checksum_path() -> Path | None:
    candidates = [
        _runtime_data_dir() / f"{PACKAGE_FILE_NAME}.sha256",
        Path(__file__).resolve().parent / "dist" / f"{PACKAGE_FILE_NAME}.sha256",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


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


def _parse_sha256_text(text: str) -> str | None:
    parts = text.strip().split()
    if not parts:
        return None

    token = parts[0].strip().lower()
    if len(token) != 64:
        return None
    if any(char not in string.hexdigits for char in token):
        return None
    return token


def _load_checksum_from_file(path: Path, log, label: str) -> str | None:
    if not path.exists():
        log(f"{label} checksum file not found: {path}")
        return None

    try:
        payload = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        log(f"{label} checksum file could not be read ({exc}), skipping package integrity verification.")
        return None

    checksum = _parse_sha256_text(payload)
    if checksum is None:
        log(f"{label} checksum file format is invalid, skipping package integrity verification.")
        return None

    log(f"Loaded {label} checksum from {path}")
    return checksum


def _download_expected_sha256(log) -> str | None:
    req = url_request.Request(SHA256_URL, method="GET")
    try:
        with url_request.urlopen(req, timeout=30) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except url_error.URLError as exc:
        log(f"Checksum file could not be fetched ({exc}), skipping package integrity verification.")
        return None

    checksum = _parse_sha256_text(payload)
    if checksum is None:
        log("Checksum file format is invalid, skipping package integrity verification.")
        return None
    log(f"Fetched package checksum from {SHA256_URL}")
    return checksum


def _copy_file_with_sha256(source: Path, target: Path, log, status_text: str) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with source.open("rb") as input_stream, target.open("wb") as output_stream:
        while True:
            chunk = input_stream.read(1024 * 256)
            if not chunk:
                break
            output_stream.write(chunk)
            digest.update(chunk)
    log(f"{status_text}: {source} -> {target}")
    return digest.hexdigest()


def _download_zip(target_zip: Path, log, status) -> str:
    target_zip.parent.mkdir(parents=True, exist_ok=True)
    req = url_request.Request(ZIP_URL, method="GET")
    digest = hashlib.sha256()
    with url_request.urlopen(req, timeout=120) as response, target_zip.open("wb") as stream:
        total = int(response.headers.get("Content-Length", "0") or "0")
        downloaded = 0
        status("Downloading package...")
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            stream.write(chunk)
            digest.update(chunk)
            downloaded += len(chunk)
            if total > 0:
                percent = downloaded * 100.0 / total
                status(f"Downloading package... {percent:.1f}%")
    log(f"Downloaded package to {target_zip}")
    return digest.hexdigest()


def _extract_zip(target_zip: Path, extract_root: Path, log, status) -> Path:
    if extract_root.exists():
        shutil.rmtree(extract_root, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    status("Extracting package...")
    with zipfile.ZipFile(target_zip, "r") as archive:
        archive.extractall(extract_root)
    install_dir = _resolve_package_dir(extract_root)
    log(f"Extracted package to {install_dir}")
    return install_dir


def _promote_installation(base_dir: Path, staged_install_dir: Path, log) -> Path:
    install_parent = _install_parent(base_dir)
    install_parent.mkdir(parents=True, exist_ok=True)
    final_dir = _active_install_dir(base_dir)
    backup_dir = install_parent / "_backup"

    if backup_dir.exists():
        shutil.rmtree(backup_dir, ignore_errors=True)

    if final_dir.exists():
        try:
            final_dir.replace(backup_dir)
            log(f"Backed up existing installation to {backup_dir}")
        except Exception as exc:
            raise RuntimeError(
                "Existing installation could not be replaced. Close the running application and try again."
            ) from exc

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        staged_install_dir.replace(final_dir)
    except Exception:
        if backup_dir.exists() and not final_dir.exists():
            backup_dir.replace(final_dir)
        raise
    finally:
        shutil.rmtree(_staging_root(base_dir), ignore_errors=True)

    if backup_dir.exists() and backup_dir != final_dir:
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
    temp_zip = Path(tempfile.gettempdir()) / PACKAGE_FILE_NAME
    staged_root = _staging_root(base_dir)
    bundled_package = _bundled_package_path()
    if bundled_package is not None:
        status("Preparing bundled package...")
        bundled_checksum = _bundled_checksum_path()
        expected_sha256 = (
            _load_checksum_from_file(bundled_checksum, log, "Bundled")
            if bundled_checksum is not None
            else None
        )
        actual_sha256 = _copy_file_with_sha256(bundled_package, temp_zip, log, "Copied bundled package")
        log(f"Using bundled release package: {bundled_package}")
    else:
        expected_sha256 = _download_expected_sha256(log)
        actual_sha256 = _download_zip(temp_zip, log, status)

    if expected_sha256 is not None and actual_sha256.lower() != expected_sha256:
        raise RuntimeError("Package checksum mismatch.")

    staged_install = _extract_zip(temp_zip, staged_root, log, status)
    final_install = _promote_installation(base_dir, staged_install, log)
    final_exe = _resolve_main_executable(final_install)
    if not final_exe.exists():
        raise FileNotFoundError(f"Installed executable not found: {final_exe}")
    try:
        temp_zip.unlink(missing_ok=True)
    except Exception:
        pass
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
        self._log(f"checksum_url={SHA256_URL}")

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
        target = _active_install_dir(self.base_dir)
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

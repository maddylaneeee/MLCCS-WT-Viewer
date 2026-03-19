from __future__ import annotations

import sys

from PyQt5.QtCore import QLocale, Qt
from PyQt5.QtGui import QIcon, QSurfaceFormat
from PyQt5.QtWidgets import QApplication, QMessageBox, QProgressDialog

from wt_model_viewer.branding import APP_NAME, current_icon_path
from wt_model_viewer.i18n import tr
from wt_model_viewer.runtime_paths import runtime_bootstrap_enabled


def _bootstrap_locale() -> str:
    locale_name = QLocale.system().name().lower()
    if locale_name.startswith("zh"):
        return "zh"
    if locale_name.startswith("ja"):
        return "ja"
    return "en"


def _ensure_runtime_payload(app: QApplication) -> bool:
    from wt_model_viewer.bootstrap import ensure_runtime_files, missing_runtime_files

    missing = missing_runtime_files()
    if not missing:
        return True

    locale = _bootstrap_locale()
    progress = QProgressDialog()
    progress.setWindowTitle(tr(locale, "bootstrap_title"))
    progress.setLabelText(tr(locale, "bootstrap_checking"))
    progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setRange(0, len(missing))

    icon_path = current_icon_path()
    if icon_path is not None:
        progress.setWindowIcon(QIcon(str(icon_path)))

    progress.show()
    app.processEvents()

    def update_progress(current: int, total: int, name: str) -> None:
        progress.setRange(0, max(1, total))
        progress.setValue(max(0, current - 1))
        progress.setLabelText(
            tr(locale, "bootstrap_downloading", current=str(current), total=str(total), name=name)
        )
        app.processEvents()

    try:
        ensure_runtime_files(progress=update_progress)
    except Exception as exc:
        progress.close()
        QMessageBox.critical(None, tr(locale, "bootstrap_title"), tr(locale, "bootstrap_failed", error=str(exc)))
        return False

    progress.setValue(progress.maximum())
    progress.close()
    return True


def main() -> int:
    QApplication.setAttribute(Qt.AA_UseDesktopOpenGL, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    surface_format = QSurfaceFormat()
    surface_format.setRenderableType(QSurfaceFormat.OpenGL)
    surface_format.setVersion(3, 3)
    surface_format.setProfile(QSurfaceFormat.CoreProfile)
    surface_format.setDepthBufferSize(24)
    surface_format.setSwapBehavior(QSurfaceFormat.DoubleBuffer)
    surface_format.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(surface_format)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    icon_path = current_icon_path()
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    if runtime_bootstrap_enabled() and not _ensure_runtime_payload(app):
        return 1

    from wt_model_viewer.gui import MainWindow

    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

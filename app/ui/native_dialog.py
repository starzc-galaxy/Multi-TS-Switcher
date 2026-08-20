"""原生文件对话框统一入口：打开前强制主窗口激活并置顶，避免对话框被遮挡。"""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog


def open_file_dialog(parent, title: str, directory: str = "",
                     name_filter: str = "", save: bool = False) -> str:
    dlg = QFileDialog(parent, title, directory)
    dlg.setNameFilter(name_filter)
    if save:
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    else:
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    if parent is not None:
        parent.activateWindow()
        parent.raise_()
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    if dlg.exec() and dlg.selectedFiles():
        return dlg.selectedFiles()[0]
    return ""

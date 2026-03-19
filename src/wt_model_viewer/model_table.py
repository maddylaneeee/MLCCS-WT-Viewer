from __future__ import annotations

from typing import Any

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QSortFilterProxyModel

from .i18n import tr
from .types import ModelFamily


class ModelTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[ModelFamily] = []
        self._locale = "en"

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return 4

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None

        item = self._items[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            if column == 0:
                return item.base_name
            if column == 1:
                return item.variant_count
            if column == 2:
                return item.pack_name
            if column == 3:
                return item.group_relpath
        elif role == Qt.UserRole:
            return item

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = (
                tr(self._locale, "table_model"),
                tr(self._locale, "table_variants"),
                tr(self._locale, "table_pack"),
                tr(self._locale, "table_group"),
            )
            return headers[section]
        return super().headerData(section, orientation, role)

    def set_items(self, items: list[ModelFamily]) -> None:
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def item_at(self, row: int) -> ModelFamily:
        return self._items[row]

    def set_locale(self, locale: str) -> None:
        self._locale = locale
        self.headerDataChanged.emit(Qt.Horizontal, 0, self.columnCount() - 1)


class ModelFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._needle = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setDynamicSortFilter(True)

    def set_query(self, text: str) -> None:
        self._needle = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._needle:
            return True

        model = self.sourceModel()
        assert isinstance(model, ModelTableModel)
        item = model.item_at(source_row)
        return self._needle in item.search_text

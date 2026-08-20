from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QScrollArea, QVBoxLayout, QWidget

from app.config.models import GroupConfig
from app.ui.group_card import GroupCard


class MonitorWall(QScrollArea):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._container = QWidget()
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(12, 12, 12, 12)
        self._grid.setSpacing(12)
        self.setWidget(self._container)
        self._cards: dict[int, GroupCard] = {}

    def set_groups(self, groups: list[GroupConfig]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards.clear()
        for g in groups:
            card = GroupCard(g)
            self._cards[g.id] = card
            self._grid.addWidget(card)
        self.relayout()

    def card(self, group_id: int) -> GroupCard | None:
        return self._cards.get(group_id)

    def cards(self) -> list[GroupCard]:
        return list(self._cards.values())

    def relayout(self) -> None:
        n = len(self._cards)
        if n == 0:
            return
        width = max(100, self.viewport().width())
        if width < 760:
            cols = 1
        elif width < 1400:
            cols = 2
        elif width < 2100:
            cols = 3
        else:
            cols = 4
        cols = min(cols, n)
        for i, card in enumerate(self.cards()):
            row, col = divmod(i, cols)
            self._grid.removeWidget(card)
            self._grid.addWidget(card, row, col)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.relayout()

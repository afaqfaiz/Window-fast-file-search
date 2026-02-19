import os
import time
import platform
import subprocess

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QTreeWidget,
    QTreeWidgetItem, QProgressBar, QComboBox,
    QFileDialog, QMessageBox, QHeaderView,
    QStackedWidget, QTreeView, QMenu
)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QAction, QFileSystemModel, QGuiApplication

from indexer import IndexerWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Fast File Search & Explorer")
        self.resize(1100, 750)

        self.indexer = IndexerWorker()
        self.indexer.progress_update.connect(self.update_progress)
        self.indexer.finished_indexing.connect(self.indexing_finished)
        self.indexer.error_occurred.connect(self.show_error)

        self.current_folder = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout(central_widget)

        # Header
        header = QHBoxLayout()
        self.btn_select = QPushButton("Select Folder")
        self.btn_select.clicked.connect(self.select_folder)
        self.lbl_path = QLabel("No folder selected")

        header.addWidget(self.btn_select)
        header.addWidget(self.lbl_path)
        header.addStretch()
        self.layout.addLayout(header)

        # Search Bar
        search_box = QHBoxLayout()

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("Search filename...")
        self.input_search.textChanged.connect(self.on_search_text_change)

        self.input_ext = QLineEdit()
        self.input_ext.setPlaceholderText("Ext (e.g. py, png)")
        self.input_ext.setFixedWidth(120)
        self.input_ext.textChanged.connect(self.on_search_text_change)

        self.combo_filter = QComboBox()
        self.combo_filter.addItems(["All Types"])
        self.combo_filter.currentTextChanged.connect(
            self.on_search_text_change
        )

        search_box.addWidget(self.input_search)
        search_box.addWidget(self.input_ext)
        search_box.addWidget(self.combo_filter)

        self.layout.addLayout(search_box)

        # Views
        self.stack = QStackedWidget()

        self.empty_view = QLabel("Select a folder to start.")
        self.empty_view.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.file_model = QFileSystemModel()
        self.file_model.setFilter(
            QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot
        )

        self.browser_view = QTreeView()
        self.browser_view.setModel(self.file_model)
        self.browser_view.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )

        self.search_view = QTreeWidget()
        self.search_view.setHeaderLabels(
            ["Name", "Type", "Size", "Date Modified", "Full Path"]
        )

        self.stack.addWidget(self.empty_view)
        self.stack.addWidget(self.browser_view)
        self.stack.addWidget(self.search_view)

        self.layout.addWidget(self.stack)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready")
        self.layout.addWidget(self.status_label)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder to Index"
        )
        if folder:
            self.current_folder = folder
            self.lbl_path.setText(folder)
            self.stack.setCurrentIndex(1)

            root_index = self.file_model.setRootPath(folder)
            self.browser_view.setRootIndex(root_index)

            self.start_indexing(folder)

    def start_indexing(self, folder):
        self.btn_select.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Indexing...")
        self.indexer.prepare(folder)
        self.indexer.start()

    def update_progress(self, count):
        self.status_label.setText(f"Indexing... {count} items")

    def indexing_finished(self, count, duration):
        self.btn_select.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(
            f"Indexed {count} items in {duration:.2f}s"
        )

        sorted_exts = self.indexer.get_sorted_extensions()
        self.combo_filter.clear()
        self.combo_filter.addItem("All Types")
        self.combo_filter.addItems(sorted_exts)

    def show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)

    def on_search_text_change(self):
        query = self.input_search.text().strip()
        manual_ext = self.input_ext.text().strip()

        if not query and not manual_ext:
            self.stack.setCurrentIndex(1)
            return

        self.stack.setCurrentIndex(2)
        if not self.indexer.doc_store:
            return

        start = time.time()

        if not query:
            results = []
            target_exts = [
                e if e.startswith(".") else "." + e
                for e in manual_ext.lower().split(",")
            ] if manual_ext else []

            for doc in self.indexer.doc_store.values():
                if doc['ext'] in target_exts:
                    results.append(doc)
        else:
            results = self.indexer.search_index(
                query,
                manual_ext_input=manual_ext,
                dropdown_filter=self.combo_filter.currentText()
            )

        dur = (time.time() - start) * 1000

        self.search_view.clear()
        for doc in results[:500]:
            item = QTreeWidgetItem([
                doc['name'], doc['ext'], doc['size'],
                doc['date'], doc['path']
            ])
            self.search_view.addTopLevelItem(item)

        self.status_label.setText(
            f"Found {len(results)} matches in {dur:.2f} ms"
        )


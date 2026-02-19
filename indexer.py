import os
import time
import datetime
from collections import defaultdict, Counter
from PyQt6.QtCore import QThread, pyqtSignal


class IndexerWorker(QThread):
    progress_update = pyqtSignal(int)
    finished_indexing = pyqtSignal(int, float)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.root_path = ""
        self.doc_store = {}
        self.inverted_index = defaultdict(set)
        self.extension_counts = Counter()
        self.is_running = False

    def prepare(self, path):
        self.root_path = path

    def generate_trigrams(self, text):
        text = text.lower()
        if len(text) < 3:
            return {text}
        return {text[i:i+3] for i in range(len(text) - 2)}

    def format_size(self, size_bytes):
        if size_bytes is None:
            return "--"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def index_item(self, name, full_path, count, is_folder=False):
        try:
            stats = os.stat(full_path)
            doc_id = count

            if is_folder:
                ext = "Folder"
                size_str = "--"
            else:
                ext = os.path.splitext(name)[1].lower()
                if not ext:
                    ext = "File"
                size_str = self.format_size(stats.st_size)

            self.extension_counts[ext] += 1

            self.doc_store[doc_id] = {
                'name': name,
                'path': full_path,
                'ext': ext,
                'size': size_str,
                'date': datetime.datetime.fromtimestamp(
                    stats.st_mtime
                ).strftime('%Y-%m-%d %H:%M'),
                'lower_name': name.lower(),
                'is_folder': is_folder
            }

            trigrams = self.generate_trigrams(name)
            for gram in trigrams:
                self.inverted_index[gram].add(doc_id)

            return True
        except (PermissionError, OSError):
            return False

    def run(self):
        self.is_running = True
        self.doc_store = {}
        self.inverted_index = defaultdict(set)
        self.extension_counts = Counter()

        count = 0
        start_time = time.time()

        try:
            for root, dirs, files in os.walk(self.root_path):
                if not self.is_running:
                    break

                for d_name in dirs:
                    full_path = os.path.join(root, d_name)
                    if self.index_item(d_name, full_path, count, is_folder=True):
                        count += 1

                for f_name in files:
                    full_path = os.path.join(root, f_name)
                    if self.index_item(f_name, full_path, count, is_folder=False):
                        count += 1

                if count % 500 == 0:
                    self.progress_update.emit(count)

        except Exception as e:
            self.error_occurred.emit(str(e))
            return

        duration = time.time() - start_time
        self.finished_indexing.emit(count, duration)

    def search_index(self, query, manual_ext_input=None, dropdown_filter=None):
        if not query:
            return []

        query = query.lower()
        trigrams = self.generate_trigrams(query)
        if not trigrams:
            return []

        sorted_grams = sorted(
            trigrams,
            key=lambda t: len(self.inverted_index.get(t, []))
        )

        candidate_ids = self.inverted_index.get(
            sorted_grams[0], set()
        ).copy()

        for gram in sorted_grams[1:]:
            if not candidate_ids:
                break
            candidate_ids &= self.inverted_index.get(gram, set())

        target_extensions = set()

        if manual_ext_input:
            parts = manual_ext_input.lower().replace(" ", "").split(",")
            for p in parts:
                if not p.startswith("."):
                    p = "." + p
                target_extensions.add(p)

        elif dropdown_filter and dropdown_filter != "All Types":
            target_extensions.add(dropdown_filter)

        results = []
        for doc_id in candidate_ids:
            doc = self.doc_store[doc_id]

            if target_extensions:
                if doc['ext'] not in target_extensions:
                    continue

            if query in doc['lower_name']:
                results.append(doc)

        results.sort(key=lambda x: (len(x['name']), x['name']))
        return results

    def get_sorted_extensions(self):
        sorted_exts = sorted(
            self.extension_counts.items(),
            key=lambda item: (-item[1], item[0])
        )
        return [item[0] for item in sorted_exts]


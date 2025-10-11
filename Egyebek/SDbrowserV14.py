# -*- coding: utf-8 -*-
import os
import sys
import json
from PIL import Image
from functools import lru_cache
from PyQt5 import QtCore, QtGui, QtWidgets
import csv
import re

# --- volitelné moduly ---
try:
    import exifread
except Exception:
    exifread = None

try:
    from sd_parsers import ParserManager
    pm = ParserManager()
except Exception:
    pm = None

SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".webp")
THUMB_SIZE = (200, 200)
CONFIG_FILE = "window_config.json"
STATE_FILE = ".image_browser_state.json"


def human_ex(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"


def pil_to_qimage(pil_img: Image.Image) -> QtGui.QImage:
    if pil_img.mode in ("L", "P"):
        pil_img = pil_img.convert("RGBA")
    elif pil_img.mode == "RGB":
        pil_img = pil_img.convert("RGBA")
    data = pil_img.tobytes("raw", "RGBA")
    qimg = QtGui.QImage(
        data, pil_img.width, pil_img.height, QtGui.QImage.Format_RGBA8888
    )
    return qimg


class ThumbWorker(QtCore.QObject):
    thumbReady = QtCore.pyqtSignal(int, QtGui.QIcon)

    def __init__(self, files, thumb_size=THUMB_SIZE):
        super().__init__()
        self.files = files
        self.thumb_size = thumb_size
        self._abort = False

    def stop(self):
        self._abort = True

    @QtCore.pyqtSlot()
    def run(self):
        for idx, path in enumerate(self.files):
            if self._abort:
                return
            try:
                icon = self.make_icon(path, self.thumb_size)
                self.thumbReady.emit(idx, icon)
            except Exception:
                continue

    @staticmethod
    @lru_cache(maxsize=4096)
    def make_icon(path, size):
        img = Image.open(path)
        img.thumbnail(size)
        return QtGui.QIcon(QtGui.QPixmap.fromImage(pil_to_qimage(img)))


class ThumbList(QtWidgets.QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QtWidgets.QListView.ListMode)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setMovement(QtWidgets.QListView.Static)
        self.setIconSize(QtCore.QSize(*THUMB_SIZE))
        self.setUniformItemSizes(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.setSpacing(6)
        self.setStyleSheet(
            """
            QListWidget::item { border: 2px solid transparent; padding: 2px; }
            QListWidget::item:selected { border: 2px solid red; background: rgba(255,0,0,40); }
        """
        )


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SD Browser")
        self.files = []
        self.in_folder = None    # zdrojová složka s obrázky
        self.out_folder = None   # cílová složka pro ukládání (SPACE)
        self.selected_index = -1
        self._preview_scroll_accum = 0
        self._preview_scroll_timer = QtCore.QElapsedTimer()
        self._preview_scroll_timer.invalidate()
        self.preview_size = 720
        self.current_pixmap = None
        self.out_folder = None  # cílová složka pro SPACE
        self.save_step = 4  # krok číslování
        self.out_dir_input = QtWidgets.QLineEdit()
        self.out_dir_input.setReadOnly(False)
        self.out_dir_input.setMinimumWidth(200)
        self.out_dir_input.editingFinished.connect(self.update_out_folder_from_input)
        
        # režimy řazení
        self.sort_modes = [
            ("Název ↑", lambda f: os.path.basename(f).lower(), False),
            ("Název ↓", lambda f: os.path.basename(f).lower(), True),
            ("Datum ↑", os.path.getmtime, False),
            ("Datum ↓", os.path.getmtime, True),
        ]
        self.current_sort = 0

        # --- centrální widget ---
        central = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(central)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(8)

        # --- horní lišta tlačítek ---
        top_bar = QtWidgets.QHBoxLayout()
        self.btn_select_files = QtWidgets.QPushButton("Select Pictures..")
        self.btn_select_folder = QtWidgets.QPushButton("Select Folder")
        self.btn_reset = QtWidgets.QPushButton("Reset List")
        self.btn_preview_size = QtWidgets.QPushButton("Preview Size")

        self.btn_sort = QtWidgets.QPushButton(self.sort_modes[self.current_sort][0])
        self.btn_sort.clicked.connect(self.toggle_sort)

        self.btn_out = QtWidgets.QPushButton("OUT")
        self.out_input = QtWidgets.QLineEdit("004")
        self.out_input.setFixedWidth(40)

        top_bar.addWidget(self.btn_select_files)
        top_bar.addWidget(self.btn_select_folder)
        top_bar.addWidget(self.btn_reset)
        top_bar.addWidget(self.btn_preview_size)
        top_bar.addWidget(self.btn_sort)   # nové tlačítko
        self.btn_export_meta_csv = QtWidgets.QPushButton("Export Prompts")
        top_bar.addWidget(self.btn_export_meta_csv)
        self.btn_export_meta_csv.clicked.connect(self.export_all_metadata_csv)
        top_bar.addWidget(self.btn_out)
        top_bar.addWidget(self.out_input)
        top_bar.addWidget(self.out_dir_input, 1)   # ← stretch = 1, pole se roztáhne
        self.out_dir_input.setMinimumWidth(300)    # ← nepůjde pod 300 px
        # top_bar.addStretch(1)  # ten už nepotřebuješ, protože stretch má přímo input
        v.addLayout(top_bar)

        # --- hlavní horizontální layout ---
        h = QtWidgets.QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        v.addLayout(h)

        # --- levý panel (seznam) ---
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.list = ThumbList()
        left_layout.addWidget(self.list)
        self.folder_entry = QtWidgets.QLineEdit()
        self.folder_entry.setReadOnly(True)
        left_layout.addWidget(self.folder_entry)
        left_panel.setFixedWidth(200)
        h.addWidget(left_panel, 0)

        # --- střední panel (preview) ---
        self.mid_panel = QtWidgets.QWidget()
        self.mid_panel.setFixedSize(self.preview_size, self.preview_size)
        mid_layout = QtWidgets.QVBoxLayout(self.mid_panel)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(6)
        self.preview = QtWidgets.QLabel()
        self.preview.setAlignment(QtCore.Qt.AlignCenter)
        self.preview.setFixedSize(self.preview_size, self.preview_size)
        self.preview.setStyleSheet("background:#fafafa; border:1px solid #ccc;")
        self.preview.setScaledContents(False)
        mid_layout.addWidget(self.preview)
        self.preview.installEventFilter(self)
        h.addWidget(self.mid_panel, 0)

        # --- pravý panel (metadata) ---
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        self.meta = QtWidgets.QPlainTextEdit()
        self.meta.setReadOnly(True)
        right_layout.addWidget(self.meta, 1)
        h.addWidget(right_panel, 1)

        self.setCentralWidget(central)

        # --- akce ---
        self.btn_select_files.clicked.connect(self.select_files)
        self.btn_select_folder.clicked.connect(self.select_folder)
        self.btn_reset.clicked.connect(self.reset_list)
        self.btn_preview_size.clicked.connect(self.change_preview_size)
        self.btn_out.clicked.connect(self.select_out_folder)
        self.list.currentRowChanged.connect(self.on_row_changed)
        self.list.setAcceptDrops(True)
        self.list.installEventFilter(self)
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Up), self, activated=self.step_up
        )
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Down), self, activated=self.step_down
        )
        QtWidgets.QShortcut(
            QtGui.QKeySequence("F1"), self, activated=self.copy_selected
        )
        QtWidgets.QShortcut(
            QtGui.QKeySequence("SPACE"), self, activated=self.save_current_to_out
        )

        self._thread = None
        self._worker = None
        self.restore_state()

    def update_out_folder_from_input(self):
        path = self.out_dir_input.text().strip()
        if path and os.path.isdir(path):
            self.out_folder = path
        else:
            QtWidgets.QMessageBox.warning(
                self, "Chyba", f"Cesta neexistuje: {path}"
            )
            # případně obnovíme původní hodnotu
            if self.out_folder:
                self.out_dir_input.setText(self.out_folder)




    def toggle_sort(self):
        self.current_sort = (self.current_sort + 1) % len(self.sort_modes)
        label, key_func, reverse = self.sort_modes[self.current_sort]
        self.btn_sort.setText(label)
        self.files.sort(key=key_func, reverse=reverse)
        self.populate_list()
    ...
    # (zbytek kódu zůstává stejný – nic jsem nemazal ani neupravoval)


    def change_preview_size(self):
        """Přepíná velikost preview mezi předdefinovanými rozměry a přepočítá pixmapu."""
        sizes = [400, 600, 720, 900, 1200]
        current = getattr(self, "preview_size", 720)
        try:
            idx = sizes.index(current)
        except ValueError:
            idx = 2
        new = sizes[(idx + 1) % len(sizes)]
        self.preview_size = new

        self.mid_panel.setFixedSize(new, new)
        self.preview.setFixedSize(new, new)

        if self.current_pixmap:
            scaled = self.current_pixmap.scaled(
                self.preview.size(),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation,
            )
            self.preview.setPixmap(scaled)


    def select_out_folder(self):
        start_dir = self.out_folder if self.out_folder else QtCore.QDir.homePath()
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Vyber cílovou složku", start_dir
        )
        if folder:
            self.out_folder = folder   # zapamatuj si naposledy použitou cestu
            if hasattr(self, "out_dir_input"):
                self.out_dir_input.setText(folder)



    def save_current_to_out(self):
        if self.selected_index < 0 or not self.files:
            return
        if not self.out_folder:
            QtWidgets.QMessageBox.warning(self, "Chyba", "Nejprve vyberte cílovou složku tlačítkem OUT")
            return
        src_path = self.files[self.selected_index]
        if not os.path.exists(src_path):
            QtWidgets.QMessageBox.warning(self, "Chyba", "Soubor neexistuje")
            return

        # získáme číslo z inputu
        try:
            num = int(self.out_input.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Chyba", "Neplatné číslo v input boxu")
            return

        # složíme cílovou cestu
        dst_name = f"{num:03d}.png"
        dst_path = os.path.join(self.out_folder, dst_name)

        try:
            import shutil
            shutil.copy2(src_path, dst_path)
            #  QtWidgets.QMessageBox.information(self, "Info", f"Soubor uložen jako:\n{dst_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Chyba", f"Nelze zkopírovat: {e}")
            return

        # zvýšení čísla o krok a aktualizace input boxu
        num += self.save_step
        self.out_input.setText(f"{num:03d}")
    
    
    def eventFilter(self, obj, event):
        # drag & drop
        if obj is self.list:
            if event.type() == QtCore.QEvent.DragEnter and event.mimeData().hasUrls():
                event.acceptProposedAction()
                return True
            elif event.type() == QtCore.QEvent.Drop:
                urls = event.mimeData().urls()
                paths = []
                for url in urls:
                    p = url.toLocalFile()
                    if not p:
                        continue
                    if os.path.isdir(p):
                        for root, _, files in os.walk(p):
                            for fn in files:
                                if fn.lower().endswith(SUPPORTED_EXTS):
                                    paths.append(os.path.join(root, fn))
                    else:
                        if p.lower().endswith(SUPPORTED_EXTS):
                            paths.append(p)
                self.handle_dropped_paths(paths)
                event.acceptProposedAction()
                return True
        # scroll nad preview - pomale, po jednom obrazku
        if obj is self.preview and event.type() == QtCore.QEvent.Wheel:
            now = QtCore.QElapsedTimer()
            if not self._preview_scroll_timer.isValid():
                self._preview_scroll_timer.start()
            elif self._preview_scroll_timer.elapsed() < 200:  # 2000 ms = 2 sekundy
                return True  # ignorovat scroll, ještě neuplynuly 2 vteřiny
            self._preview_scroll_timer.restart()

            delta = event.angleDelta().y()
            if delta > 0:
                self.on_step_requested(-1)
            elif delta < 0:
                self.on_step_requested(1)
            return True
            
        return super().eventFilter(obj, event)

    # --- File handling ---
    def select_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Vyber obrázky", "", "Obrázky (*.png *.jpg *.jpeg *.webp)")
        if paths:
            self.files = list(paths)
            self.folder_entry.setText(os.path.dirname(self.files[0]))  # jen seznam obrázků
            self.populate_list()
            self.save_state()
            # self.out_folder se nijak nemění

    def select_folder(self):
        start_dir = self.in_folder if self.in_folder else QtCore.QDir.homePath()
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Vyber složku s obrázky", start_dir
        )
        if not folder:
            return

        files = []
        for root, _, fns in os.walk(folder):
            for fn in fns:
                if fn.lower().endswith(SUPPORTED_EXTS):
                    files.append(os.path.join(root, fn))
        files.sort(key=lambda p: os.path.getmtime(p))
        if not files:
            QtWidgets.QMessageBox.information(
                self, "Info", "V adresáři nebyly nalezeny žádné podporované obrázky."
            )
            return

        self.in_folder = folder   # zapamatuj si naposledy použitou cestu
        self.files = files
        self.folder_entry.setText(folder)
        self.populate_list()
        self.save_state()



    def handle_dropped_paths(self, paths):
        added = False
        for p in paths:
            if p.lower().endswith(SUPPORTED_EXTS) and p not in self.files:
                self.files.append(p)
                added = True
        if added:
            self.populate_list()
            self.save_state()

    # --- List + thumbnails ---
    def populate_list(self):
        self.stop_worker()
        self.list.clear()
        self.selected_index = -1
        for path in self.files:
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setToolTip(path)
            self.list.addItem(item)
        if self.files:
            self.list.setCurrentRow(0)
        self._thread = QtCore.QThread()
        self._worker = ThumbWorker(tuple(self.files))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.thumbReady.connect(self.on_thumb_ready)
        self._thread.start()

    def stop_worker(self):
        if self._worker:
            self._worker.stop()
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._worker = None
        self._thread = None

    @QtCore.pyqtSlot(int, QtGui.QIcon)
    def on_thumb_ready(self, idx, icon):
        if 0 <= idx < self.list.count():
            self.list.item(idx).setIcon(icon)

    # --- Navigation ---
    def on_row_changed(self, row: int):
        if row < 0 or row >= len(self.files):
            return
        QtCore.QTimer.singleShot(0, lambda r=row: self.show_image_if_selected(r))

    def show_image_if_selected(self, row: int):
        if self.list.currentRow() != row:
            return
        self.selected_index = row
        self.show_image(row)

    def refresh_current(self):
        if 0 <= self.selected_index < len(self.files):
            self.show_image(self.selected_index)

    def on_step_requested(self, delta: int):
        if not self.files:
            return
        new_row = max(0, min(self.selected_index + delta if self.selected_index >= 0 else 0, len(self.files) - 1))
        self.list.setCurrentRow(new_row)

    def step_up(self):
        self.on_step_requested(-1)

    def step_down(self):
        self.on_step_requested(1)



    def export_all_metadata_csv(self):
        if not self.files:
            QtWidgets.QMessageBox.information(self, "Info", "Žádné obrázky k exportu.")
            return

        default_path = os.path.join(self.out_folder or QtCore.QDir.homePath(), "metadata_export.csv")
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Uložit metadata do CSV", default_path, "CSV Files (*.csv)"
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8", newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["File", "Metadata"])  # hlavička CSV

                for path in self.files:
                    meta_lines = []
                    try:
                        # --- SD parser pro JPEG ---
                        if path.lower().endswith((".jpg", ".jpeg")) and ParserManager:
                            pm_local = ParserManager()
                            parsed = pm_local.parse(path)
                            if parsed and getattr(parsed, "prompts", None):
                                for pr in parsed.prompts:
                                    for subline in str(pr.value).splitlines():
                                        subline = re.sub(r'<.*?>', '', subline).strip()
                                        if subline:
                                            meta_lines.append(subline)

                        # --- PNG metadata ---
                        img = Image.open(path)
                        img.load()
                        if path.lower().endswith(".png"):
                            if ParserManager:
                                pm_local = ParserManager()
                                parsed = pm_local.parse(path)
                                if parsed and getattr(parsed, "prompts", None):
                                    for subline in str(parsed.prompts[0].value).splitlines():
                                        subline = re.sub(r'<.*?>', '', subline).strip()
                                        if subline:
                                            meta_lines.append(subline)

                        # --- JPEG EXIF metadata ---
                        elif path.lower().endswith((".jpg", ".jpeg")) and exifread:
                            with open(path, "rb") as fh:
                                tags = exifread.process_file(fh, details=False)
                            for k, v in tags.items():
                                for subline in f"{k}: {v}".splitlines():
                                    subline = re.sub(r'<.*?>', '', subline).strip()
                                    if subline:
                                        meta_lines.append(subline)

                        # spojit všechny informace do jednoho řádku
                        meta_str = " | ".join(meta_lines)
                        writer.writerow([os.path.basename(path), meta_str])

                    except Exception as e:
                        writer.writerow([os.path.basename(path), f"Chyba: {human_ex(e)}"])

            QtWidgets.QMessageBox.information(self, "Hotovo", f"Metadata CSV uložena do:\n{save_path}")

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Chyba", f"Nepodařilo se uložit CSV:\n{human_ex(e)}")






    # --- Preview + metadata ---
    def show_image(self, index: int):
        if index < 0 or index >= len(self.files):
            return
        path = self.files[index]
        self.selected_index = index
        self.preview.clear()
        self.meta.clear()
        lines = [f"Soubor: {path}"]

        try:
            img = Image.open(path)
            img.load()
            img.thumbnail((self.preview_size, self.preview_size))
            self.current_pixmap = QtGui.QPixmap.fromImage(pil_to_qimage(img))
            self.preview.setPixmap(self.current_pixmap)
        except Exception as e:
            self.preview.setText(f"Chyba při načtení: {human_ex(e)}")
            self.current_pixmap = None

        # SD parser pro JPEG
        try:
            if path.lower().endswith((".jpg", ".jpeg")) and ParserManager:
                pm_local = ParserManager()
                parsed = pm_local.parse(path)
                if parsed and getattr(parsed, "prompts", None):
                    lines.append("\n--- Prompt (sd-parsers) ---")
                    for pr in parsed.prompts:
                        lines.append(str(pr.value))
        except Exception as e:
            lines.append(f"Chyba při načtení SD parseru: {human_ex(e)}")

        # Metadata z PNG a JPEG
        try:
            img = Image.open(path)
            img.load()
            if path.lower().endswith(".png"):
                if ParserManager:
                    pm_local = ParserManager()
                    parsed = pm_local.parse(path)
                    if parsed and getattr(parsed, "prompts", None):
                        lines.append("\n--- Positive Prompt ---")
                        lines.append(str(parsed.prompts[0].value))
            elif path.lower().endswith((".jpg", ".jpeg")) and exifread:
                with open(path, "rb") as fh:
                    tags = exifread.process_file(fh, details=False)
                if tags:
                    lines.append("\n--- EXIF (exifread) ---")
                    for k, v in tags.items():
                        lines.append(f"{k}: {v}")
        except Exception as e:
            lines.append(f"Chyba při čtení metadat: {human_ex(e)}")

        self.meta.setPlainText("\n".join(lines))
        itm = self.list.item(index)
        if itm:
            self.list.scrollToItem(itm, QtWidgets.QAbstractItemView.PositionAtCenter)

    # --- Reset + state ---
    def reset_list(self):
        self.stop_worker()
        self.files = []
        self.list.clear()
        self.preview.clear()
        self.meta.clear()
        self.selected_index = -1
        self.save_state()
        
    # --- Copy / Paste ---
    def copy_selected(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self.files):
            return

        path = self.files[row]
        if not os.path.exists(path):
            return

        # připravíme mime data pro Windows
        mime = QtCore.QMimeData()
        urls = [QtCore.QUrl.fromLocalFile(path)]
        mime.setUrls(urls)

        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setMimeData(mime)

            
            
            

    def save_state(self):
        try:
            state = {
                "last_files": self.files,
                "geometry": str(bytes(self.saveGeometry().toHex()), "ascii"),
                "in_folder": self.in_folder,
                "out_folder": self.out_folder,
                "window": {
                    "width": self.width(),
                    "height": self.height(),
                    "x": self.x(),
                    "y": self.y(),
                },
            }
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


    def restore_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.in_folder = data.get("in_folder")
                self.out_folder = data.get("out_folder")

                geom_hex = data.get("geometry")
                if geom_hex:
                    ba = QtCore.QByteArray.fromHex(bytes(geom_hex, "ascii"))
                    self.restoreGeometry(ba)

                # starší verze programu může mít i "window" dict
                win = data.get("window")
                if win:
                    self.resize(win.get("width", self.width()), win.get("height", self.height()))
                    self.move(win.get("x", self.x()), win.get("y", self.y()))

                last = data.get("last_files") or []
                if last:
                    self.files = [p for p in last if os.path.exists(p)]
                    if self.files:
                        self.populate_list()

                if self.out_folder and hasattr(self, "out_dir_input"):
                    self.out_dir_input.setText(self.out_folder)
        except Exception:
            pass


    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        self.stop_worker()
        self.save_state()
        super().closeEvent(e)

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

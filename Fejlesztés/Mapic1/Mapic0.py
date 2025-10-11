import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QTextEdit, QFileDialog, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PIL import Image
from PIL.PngImagePlugin import PngImageFile
import exifread


class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Képnézegető + Metaadatok")

        self.image_files = []
        self.current_index = -1

        layout = QVBoxLayout()

        # kép kijelző
        self.image_label = QLabel("Nincs betöltve kép")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)

        # metaadat kijelző
        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        layout.addWidget(self.meta_text)

        # gombok sorban
        btn_layout = QHBoxLayout()

        self.btn_open = QPushButton("Mappa megnyitása")
        self.btn_open.clicked.connect(self.open_folder)
        btn_layout.addWidget(self.btn_open)

        self.btn_prev = QPushButton("◀ Előző")
        self.btn_prev.clicked.connect(self.show_prev)
        btn_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Következő ▶")
        self.btn_next.clicked.connect(self.show_next)
        btn_layout.addWidget(self.btn_next)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz mappát")
        if folder:
            # képfájlok szűrése
            exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp")
            self.image_files = [os.path.join(folder, f) for f in os.listdir(folder)
                                if f.lower().endswith(exts)]
            self.image_files.sort()
            self.current_index = 0
            if self.image_files:
                self.show_image(self.image_files[self.current_index])

    def show_image(self, fname):
        pixmap = QPixmap(fname)
# kép méretezése az ablakhoz, arány megtartással
        scaled = pixmap.scaled(
              self.image_label.size(),
              Qt.AspectRatioMode.KeepAspectRatio,
              Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

        meta_info = f"Fájl: {os.path.basename(fname)}\n\n"

        # EXIF kiolvasás
        try:
            with open(fname, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                if tags:
                    meta_info += "--- EXIF metaadatok ---\n"
                    for tag in tags.keys():
                        meta_info += f"{tag}: {tags[tag]}\n"
        except Exception as e:
            meta_info += f"EXIF hiba: {e}\n"

        # PNG chunk (AI generálási infók)
        try:
            img = Image.open(fname)
            if isinstance(img, PngImageFile) and img.text:
                meta_info += "\n--- PNG szöveges chunkok ---\n"
                for k, v in img.text.items():
                    meta_info += f"{k}: {v}\n"
        except Exception as e:
            meta_info += f"\nPNG metaadat hiba: {e}\n"

        self.meta_text.setPlainText(meta_info)

    def show_next(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_image(self.image_files[self.current_index])

    def show_prev(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_image(self.image_files[self.current_index])

    def resizeEvent(self, event):
        if self.image_files and 0 <= self.current_index < len(self.image_files):
            self.show_image(self.image_files[self.current_index])
        super().resizeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.resize(1000, 700)
    window.show()
    sys.exit(app.exec())

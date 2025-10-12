import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QTextEdit, QFileDialog, QPushButton, QHBoxLayout,
    QSizePolicy, QSplitter
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from PIL import Image

# ----------- AI metaadatok kiolvasása -----------
def extract_prompts(image_path):
    try:
        img = Image.open(image_path)
        metadata = img.info
        raw_prompt = metadata.get("prompt", None)
        if not raw_prompt:
            return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

        prompt_json = json.loads(raw_prompt)

        # --- minden "text" érték összegyűjtése ---
        texts = []

        def collect_texts(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "text" and isinstance(v, str):
                        texts.append(v)
                    else:
                        collect_texts(v)
            elif isinstance(obj, list):
                for item in obj:
                    collect_texts(item)

        collect_texts(prompt_json)

        pos = texts[0] if len(texts) > 0 else "N/A"
        neg = texts[1] if len(texts) > 1 else "N/A"

        # --- kereső segédfüggvény ---
        def find_key(obj, target):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == target:
                        return v
                    res = find_key(v, target)
                    if res is not None:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = find_key(item, target)
                    if res is not None:
                        return res
            return None

        ckpt     = find_key(prompt_json, "ckpt_name") or "-"
        sampler  = find_key(prompt_json, "sampler_name") or "-"
        scheduler= find_key(prompt_json, "scheduler") or "-"
        step     = find_key(prompt_json, "steps") or "-"
        cfg      = find_key(prompt_json, "cfg") or "-"
        seed     = find_key(prompt_json, "seed") or "-"
        denoise  = find_key(prompt_json, "denoise") or "-"
        vae      = find_key(prompt_json, "vae_name") or "-"
        lora     = find_key(prompt_json, "lora_name") or "-"

        return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, denoise, vae, lora)

    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-")
# ----------- Képnézegető osztály -----------
class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Képnézegető + AI Metaadatok")

        self.image_files = []
        self.current_index = -1

        self.layout = QVBoxLayout(self)

        # --- alap splitter (függőleges) ---
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)

        self.image_label = QLabel("Nincs betöltve kép")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.splitter.addWidget(self.image_label)

        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        self.splitter.addWidget(self.meta_text)

        self.splitter.setSizes([600, 200])
        self.layout.addWidget(self.splitter)

        # --- gombok ---
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

        # új gomb: váltás függőleges/vízszintes
        self.btn_toggle = QPushButton("↔ / ↕")
        self.btn_toggle.clicked.connect(self.toggle_orientation)
        btn_layout.addWidget(self.btn_toggle)

        self.layout.addLayout(btn_layout)


    def toggle_orientation(self):
        """Splitter váltása vízszintes és függőleges között"""
        if self.splitter.orientation() == Qt.Orientation.Vertical:
            self.splitter.setOrientation(Qt.Orientation.Horizontal)
            self.splitter.setSizes([500, 500])
        else:
            self.splitter.setOrientation(Qt.Orientation.Vertical)
            self.splitter.setSizes([600, 200])


    # -- kép betöltés és prompt kiírás innen folytatódik...

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Válassz mappát")
        if folder:
            exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
            self.image_files = sorted(
                [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(exts)]
            )
            self.current_index = 0
            if self.image_files:
                self.show_image(self.image_files[self.current_index])

    def _update_image_label(self):
        """Skálázzuk le az eltárolt pixmap-et a jelenlegi label mérethez."""
        if self.current_pixmap is None or self.current_pixmap.isNull():
            return
        w = max(50, self.image_label.width())
        h = max(50, self.image_label.height())
        scaled = self.current_pixmap.scaled(w, h,
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    def show_image(self, fname):
        pixmap = QPixmap(fname)
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

        # --- prompt kinyerés ---
        result = extract_prompts(fname)

        # sortörések eltüntetése
        pos = result[0].replace("\n", " ")
        neg = result[1].replace("\n", " ")

        meta_info = f"✅ Prompt: {pos}\n"
        meta_info += f"🚫 Negative Prompt: {neg}\n"
        meta_info += f"📦 Checkpoint: {result[2]}\n"
        meta_info += f"🔁 Sampler: {result[3]}    "
        meta_info += f"📈 Scheduler: {result[4]}    "
        meta_info += f"📏 Steps: {result[5]}\n"
        meta_info += f"🎯 CFG scale: {result[6]}    "
        meta_info += f"🎲 Seed: {result[7]}    "
        meta_info += f"🌀 Denoise: {result[8]}\n"
        meta_info += f"🧠 VAE: {result[9]}\n"
        meta_info += f"✨ LoRA: {result[10]}\n"

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
        # Ablak átméretezésekor csak újraskálázzuk az aktuális pixmap-et (nem töltjük újra a fájlt)
        if self.image_files and 0 <= self.current_index < len(self.image_files):
            self.show_image(self.image_files[self.current_index])
        super().resizeEvent(event)
#        self._update_image_label()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.resize(1000, 700)
    window.show()
    sys.exit(app.exec())

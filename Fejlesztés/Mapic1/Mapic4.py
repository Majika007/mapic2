#!/usr/bin/env python3
import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QTextEdit, QFileDialog, QPushButton, QHBoxLayout, QSplitter,
    QSizePolicy
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QTimer
from PIL import Image

# ---------- Prompt extract (robosztusabb) ----------
def extract_prompts(image_path):
    try:
        img = Image.open(image_path)
        metadata = img.info

        # gyakori kulcsok, ahol a prompt/params előfordulhat
        raw_prompt = metadata.get("prompt") or metadata.get("parameters") or metadata.get("Description") or metadata.get("comment") or None
        if not raw_prompt:
            return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

        # Ha raw_prompt nem JSON, próbáljuk meg JSON-ként parse-olni továbbra is.
        try:
            prompt_json = json.loads(raw_prompt)
        except Exception:
            # Ha nem JSON, visszaadjuk a teljes stringet mint positive prompt (biztonsági fallback)
            text_all = str(raw_prompt)
            text_all = " ".join(text_all.split())  # collapse whitespace
            return (text_all, "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

        # --- összegyűjtjük az első két "text" mezőt rekurzívan ---
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

        # --- kereső segédfüggvény (bárhol a JSON-ban) ---
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
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")


# ---------- Main viewer ----------
class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Képnézegető + AI Metaadatok")

        self.image_files = []
        self.current_index = -1
        self.current_pixmap = None

        main_layout = QVBoxLayout(self)

        # Splitter: alapértelmezés: függőleges (kép fent, meta lent)
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)

        # kép
        self.image_label = QLabel("Nincs betöltve kép")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.splitter.addWidget(self.image_label)

        # meta
        self.meta_text = QTextEdit()
        self.meta_text.setReadOnly(True)
        self.meta_text.setMinimumHeight(120)
        self.meta_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.splitter.addWidget(self.meta_text)

        # kezdő arányok
        self.splitter.setSizes([600, 200])
        main_layout.addWidget(self.splitter)

        # gombok + toggle
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

        # toggle orientation gomb
        self.btn_toggle = QPushButton("↔ / ↕")
        self.btn_toggle.clicked.connect(self.toggle_orientation)
        btn_layout.addWidget(self.btn_toggle)

        main_layout.addLayout(btn_layout)

    # mappa betöltése
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

    # segédfüggvény: biztonságos skálázás a cache-elt pixmapből
    def _update_image_label(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            return
        w = max(50, self.image_label.width())
        h = max(50, self.image_label.height())
        scaled = self.current_pixmap.scaled(w, h,
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(scaled)

    # kép megjelenítése + meta
    def show_image(self, fname):
        pix = QPixmap(fname)
        if pix.isNull():
            self.image_label.setText("Nem sikerült betölteni a képet")
            self.meta_text.setPlainText(f"Nem sikerült betölteni: {fname}")
            self.current_pixmap = None
            return

        self.current_pixmap = pix
        self._update_image_label()

        # metaadatok
        result = extract_prompts(fname)
        pos = result[0] if result[0] else "N/A"
        neg = result[1] if result[1] else "N/A"
        # sortörések eltávolítása és whitespace collapse
        pos = " ".join(str(pos).replace("\r", " ").replace("\n", " ").split())
        neg = " ".join(str(neg).replace("\r", " ").replace("\n", " ").split())

        meta_info = f"Fájl: {os.path.basename(fname)}\n\n"
        meta_info += f"✅ Prompt: {pos}\n"
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

    # következő/előző
    def show_next(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_image(self.image_files[self.current_index])

    def show_prev(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_image(self.image_files[self.current_index])

    # orientáció váltás - megőrizzük az arányokat, majd újrakalkuláljuk új tengelyhez
    def toggle_orientation(self):
        s = self.splitter
        old_sizes = s.sizes()
        total_old = sum(old_sizes) if sum(old_sizes) > 0 else 1
        ratios = [float(x) / total_old for x in old_sizes]

        # biztosítjuk a minimumméretet a gyerekeknél
        for i in range(s.count()):
            w = s.widget(i)
            if w:
                w.setMinimumSize(50, 50)

        # váltás
        if s.orientation() == Qt.Orientation.Vertical:
            s.setOrientation(Qt.Orientation.Horizontal)
        else:
            s.setOrientation(Qt.Orientation.Vertical)

        # A layout frissítése után alkalmazzuk az új pixelméreteket (ugyanazok az arányok)
        QTimer.singleShot(0, lambda: self._apply_new_sizes(ratios))

    def _apply_new_sizes(self, ratios):
        s = self.splitter
        if s.orientation() == Qt.Orientation.Horizontal:
            total = max(100, s.width())
        else:
            total = max(100, s.height())
        new_sizes = [max(50, int(r * total)) for r in ratios]
        s.setSizes(new_sizes)
        s.update()
        # újraskálázás a megváltozott labelmérethez
        self._update_image_label()

    # ablak méretezés -> csak újraskálázunk a cache-elt pixmapből
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_image_label)

    # billentyűzet: jobb/left/ up/down
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.show_next()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.show_prev()
        else:
            super().keyPressEvent(event)


# ---------- run ----------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ImageViewer()
    w.resize(1000, 700)
    w.show()
    sys.exit(app.exec())

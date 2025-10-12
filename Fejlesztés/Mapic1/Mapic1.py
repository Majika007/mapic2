import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QTextEdit, QFileDialog, QPushButton, QHBoxLayout
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from PIL import Image
from PIL.PngImagePlugin import PngImageFile
import exifread

class ImageViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Képnézegető + AI Metaadatok")

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

        # gombok
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
            exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
            self.image_files = sorted(
                [os.path.join(folder, f) for f in os.listdir(folder)
                 if f.lower().endswith(exts)]
            )
            self.current_index = 0
            if self.image_files:
                self.show_image(self.image_files[self.current_index])

    def show_image(self, fname):
        # Kép betöltése arányosan
        pixmap = QPixmap(fname)
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

        # AI metaadatok kibontása
    try:
        result = extract_prompts(fname)
        meta_info = f"Fájl: {os.path.basename(fname)}\n\n"
        meta_info += f"✅ Prompt: {result[0]}\n"
        meta_info += f"🚫 Negative Prompt: {result[1]}\n"
        meta_info += f"📦 Checkpoint: {result[2]}\n"
        meta_info += f"🔁 Sampler: {result[3]}    "
        meta_info += f"📈 Scheduler: {result[4]}    "
        meta_info += f"📏 Steps: {result[5]}\n"
        meta_info += f"🎯 CFG scale: {result[6]}    "
        meta_info += f"🎲 Seed: {result[7]}    "
        meta_info += f"🌀 Denoise: {result[8]}\n"
        meta_info += f"🧠 VAE: {result[9]}\n"
        meta_info += f"✨ LoRA: {result[10]}\n"
    except Exception as e:
        meta_info = f"Metaadat hiba: {e}"

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
        # ablak átméretezéskor újraméretezés arányosan
        if self.image_files and 0 <= self.current_index < len(self.image_files):
            self.show_image(self.image_files[self.current_index])
        super().resizeEvent(event)
        
    def extract_prompts(image_path):
        try:
            img = Image.open(image_path)
            metadata = img.info
            raw_prompt = metadata.get("prompt", None)
            if not raw_prompt:
                return (image_path, "N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-")
    
            prompt_json = json.loads(raw_prompt)
            pos = prompt_json["6"]["inputs"]["text"]
            neg = prompt_json["7"]["inputs"]["text"]
            ckpt = prompt_json["4"]["inputs"].get("ckpt_name", "-")
            sampler = prompt_json["3"]["inputs"].get("sampler_name", "-")
            scheduler = prompt_json["3"]["inputs"].get("scheduler", "-")
            step = prompt_json["3"]["inputs"].get("steps", "-")
            cfg = prompt_json["3"]["inputs"].get("cfg", "-")
            seed = prompt_json["3"]["inputs"].get("seed", "-")
            denoise = prompt_json["3"]["inputs"].get("denoise", "-")
            vae = prompt_json.get("14", {}).get("inputs", {}).get("vae_name", "-")
            lora = prompt_json.get("16", {}).get("inputs", {}).get("lora_name", "-")
    
            return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, denoise, vae, lora)
    
        except Exception as e:
            return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-")

    


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ImageViewer()
    window.resize(1000, 700)
    window.show()
    sys.exit(app.exec())

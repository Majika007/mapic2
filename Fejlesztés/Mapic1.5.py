"""
Image Viewer + AI Metadata

Author: Majika77
Date: 2025-09-12
Description: A lightweight image viewer that displays AI generation metadata alongside images.
__version__ = "1.5"
Developed with assistance from ChatGPT (OpenAI GPT-5 mini) :)
"""
#!/usr/bin/env python3
import sys
import os
import subprocess, json
import exifread, re
import html
import unicodedata
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QTextEdit, QFileDialog, QPushButton, QHBoxLayout, QSplitter,
    QSizePolicy
)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QTimer
from PIL import Image

def decode_surrogate_pair(txt):
    if not txt:
        return "-"
    try:
        import codecs
        return codecs.decode(txt, 'unicode_escape')
    except Exception:
        return txt
        
def decode_surrogates(txt):
    if not txt:
        return "-"
    try:
        # kényszerített dekódolás surrogate-okból
        return txt.encode('utf-16', 'surrogatepass').decode('utf-16')
    except Exception:
        return txt
    
# ---------- Prompt extract (robosztusabb) ----------
def extract_from_usercomment(raw_uc):
    """
    UserComment mezőből próbálja kiszedni:
    - pozítiv prompt
    - negatív prompt
    - model neve
    - sampler
    - steps
    - cfg
    - seed
    A visszatérés mindig 11 elemű tuple legyen.
    """
    pos, neg, ckpt, sampler, scheduler, step, cfg, seed = "-", "-", "-", "-", "-", "-", "-", "-"
    
    try:
        # --- JSON-szerű formátum ---
        if raw_uc.strip().startswith("{"):
            data = json.loads(raw_uc)

            # Positive/negative prompt
            if "extraMetadata" in data:
                extra = json.loads(data["extraMetadata"])
                pos = extra.get("prompt", "-")
                neg = extra.get("negativePrompt", "-")
                sampler = extra.get("sampler", "-")
                step = str(extra.get("steps", "-"))
                cfg = str(extra.get("cfgScale", "-"))
                ckpt = extra.get("modelName", "-")  # ha van
                seed = str(extra.get("seed", "-")) if "seed" in extra else "-"
            
            # Bizonyos A1111/Comfy mentésnél a text közvetlenül van
            for k, v in data.items():
                if isinstance(v, dict) and v.get("class_type") == "smZ CLIPTextEncode":
                    if v["_meta"]["title"] == "Positive":
                        pos = v["inputs"].get("text", pos)
                    elif v["_meta"]["title"] == "Negative":
                        neg = v["inputs"].get("text", neg)

                if isinstance(v, dict) and v.get("class_type") == "CheckpointLoaderSimple":
                    ckpt = v["inputs"].get("ckpt_name", ckpt)

                if isinstance(v, dict) and v.get("class_type") == "FaceDetailer":
                    step = str(v["inputs"].get("steps", step))
                    cfg = str(v["inputs"].get("cfg", cfg))
                    sampler = v["inputs"].get("sampler_name", sampler)
                    seed = str(v["inputs"].get("seed", seed))

        # --- sima szöveges formátum ---
        else:
            # Positive prompt (eleje a "Steps:" előtt)
            m = re.split(r"Steps:|steps:", raw_uc, 1)
            if len(m) > 1:
                pos = m[0].strip().rstrip(",.")
            else:
                pos = raw_uc.strip()

            # Negative prompt
            neg_m = re.search(r"Negative prompt:\s*(.*)", raw_uc, re.IGNORECASE)
            if neg_m:
                neg = neg_m.group(1).strip()

            # Steps
            step_m = re.search(r"Steps:\s*(\d+)", raw_uc)
            if step_m:
                step = step_m.group(1)

            # Sampler
            sampler_m = re.search(r"Sampler:\s*([^\n,]+)", raw_uc)
            if sampler_m:
                sampler = sampler_m.group(1).strip()

            # CFG
            cfg_m = re.search(r"CFG scale:\s*([\d.]+)", raw_uc, re.IGNORECASE)
            if cfg_m:
                cfg = cfg_m.group(1)

            # Seed
            seed_m = re.search(r"Seed:\s*(\d+)", raw_uc)
            if seed_m:
                seed = seed_m.group(1)

            # ModelName
            model_m = re.search(r'"modelName":"([^"]+)"', raw_uc)
            if model_m:
                ckpt = model_m.group(1)
                
            pos = decode_surrogate_pair(pos)
            neg = decode_surrogate_pair(neg)
            ckpt = decode_surrogate_pair(ckpt)

    except Exception as e:
        pos = f"Error: {e}"

    # 11 elemű tuple, VAE/Lora nélkül
    return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, "-", "-", "-")
        
def extract_prompts_jpg(image_path):
    try:
        # 1) exiftool meghívása JSON kimenettel
        result = subprocess.run(
            ["exiftool", "-j", "-UserComment", image_path],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if data and "UserComment" in data[0]:
                raw_uc = data[0]["UserComment"]

                # --- itt hívjuk meg a helper függvényt ---
                parsed = extract_from_usercomment(raw_uc)
                if parsed:
                    return parsed

        # ha nincs értelmezhető adat
        return ("N/A", "N/A", "-", "-", "-", "-", "-", "-")

    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-")
        
def extract_params_png(text):
    try:
        # Pozitív prompt: mindent a "Steps:" előtt
        match = re.search(r'(.*?)(?:Steps:|$)', text, re.DOTALL)
        pos = match.group(1).strip() if match else "-"

        # Seed
        seed = re.search(r'Seed:\s*(\d+)', text)
        seed = seed.group(1) if seed else "-"

        # Steps
        steps = re.search(r'Steps:\s*(\d+)', text)
        steps = steps.group(1) if steps else "-"

        # Sampler
        sampler = re.search(r'Sampler:\s*([^,]+)', text)
        sampler = sampler.group(1) if sampler else "-"

        # CFG
        cfg = re.search(r'CFG scale:\s*([\d.]+)', text)
        cfg = cfg.group(1) if cfg else "-"

        # Neg prompt: ha van "Negative prompt:" tag
        neg = re.search(r'Negative prompt:\s*(.*?)(?:, \w+:|$)', text)
        neg = neg.group(1).strip() if neg else "-"

        return pos, neg, "-", sampler, "-", steps, cfg, seed, "-", "-", "-"
    except Exception:
        return "-", "-", "-", "-", "-", "-", "-", "-"        
        
def extract_prompts_png(image_path):
    try:
        img = Image.open(image_path)
        metadata = img.info

        # gyakori kulcsok, ahol a prompt/params előfordulhat
        raw_prompt = metadata.get("prompt") or metadata.get("parameters") or metadata.get("Description") or metadata.get("comment") or None
        if not raw_prompt:
            return ("N/A", "N/A", "-", "-", "-", "-", "-", "-")

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

        return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed)

    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-")

def extract_prompts(fname):
    ext = os.path.splitext(fname)[1].lower()
    
    if ext == ".png":
        from PIL import Image
        import re, json

        img = Image.open(fname)
        metadata = img.info

        if "prompt" in metadata:
            return extract_prompts_png(fname)  # meglévő JSON feldolgozás
        elif "parameters" in metadata:
            raw = metadata["parameters"]

            pos = re.search(r'^(.*?)\s*,?\s*Negative prompt:', raw, re.DOTALL)
            neg = re.search(r'Negative prompt:\s*(.*?)\s*,?\s*Steps:', raw)
            sampler = re.search(r'Sampler:\s*(.*?)(?=,|$)', raw)
            cfg = re.search(r'CFG scale:\s*(.*?)(?=,|$)', raw)
            step = re.search(r'Steps:\s*(.*?)(?=,|$)', raw)
            seed = re.search(r'Seed:\s*(.*?)(?=,|$)', raw)
            ckpt = re.search(r'Model:\s*(.*?)(?=,|$)', raw)

            return (
                pos.group(1).replace("\n", " ") if pos else "-",
                neg.group(1).replace("\n", " ") if neg else "-",
                ckpt.group(1) if ckpt else "-",
                sampler.group(1) if sampler else "-",
                "-",  # scheduler nincs a Parameters stringben
                step.group(1) if step else "-",
                cfg.group(1) if cfg else "-",
                seed.group(1) if seed else "-",
            )
        else:
            return ("N/A", "N/A", "-", "-", "-", "-", "-", "-")

    elif ext in (".jpg", ".jpeg"):
        return extract_prompts_jpg(fname)
    else:
        return ("N/A", "N/A", "-", "-", "-", "-", "-", "-")

# ---------- Main viewer ----------
class ImageViewer(QWidget): 
    def __init__(self):
        super().__init__()
        QShortcut(QKeySequence("Right"), self, self.show_next)
        QShortcut(QKeySequence("Left"), self, self.show_prev)
        QShortcut(QKeySequence("Down"), self, self.show_next)
        QShortcut(QKeySequence("Up"), self, self.show_prev)
        self.setWindowTitle("MaPic - ImageView + AIMeta")

        self.image_files = []
        self.current_index = -1
        self.current_pixmap = None

        main_layout = QVBoxLayout(self)

        # Splitter: alapértelmezés: függőleges (kép fent, meta lent)
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)

        # kép
        self.image_label = QLabel("No image loaded")
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
        self.splitter.setSizes([700, 150])
        main_layout.addWidget(self.splitter)

        # gombok + toggle
        btn_layout = QHBoxLayout()
        self.btn_open = QPushButton("Open folder")
        self.btn_open.clicked.connect(self.open_folder)
        btn_layout.addWidget(self.btn_open)

        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.clicked.connect(self.show_prev)
        btn_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self.show_next)
        btn_layout.addWidget(self.btn_next)

        # toggle orientation gomb
        self.btn_toggle = QPushButton("↔ / ↕")
        self.btn_toggle.clicked.connect(self.toggle_orientation)
        btn_layout.addWidget(self.btn_toggle)

        # save the metadata
        self.btn_save = QPushButton("Save .txt")
        self.btn_save.clicked.connect(self.save_meta)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

        # --- Automatikus mappa betöltés indításkor ---
        self.load_current_folder()

    def load_current_folder(self):
        folder = os.getcwd()  # aktuális mappa
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
        self.image_files = sorted(
            [os.path.join(folder, f) for f in os.listdir(folder)
             if f.lower().endswith(exts)]
        )
        self.current_index = 0
        if self.image_files:
            self.show_image(self.image_files[self.current_index])

    # ---------- Save Metadata ----------
    def save_meta(self):
        if not self.image_files or not (0 <= self.current_index < len(self.image_files)):
            return

        fname = self.image_files[self.current_index]
        result = extract_prompts(fname)

        # sortörések kezelése
        pos = " ".join(str(result[0]).split())
        neg = " ".join(str(result[1]).split())

        text_content = (
            f"✅ Prompt: {pos}\n"
            f"🚫 Negative Prompt: {neg}\n"
            f"📦 Checkpoint: {result[2]}\n"
            f"🔁 Sampler: {result[3]}\n"
            f"📈 Scheduler: {result[4]}\n"
            f"📏 Steps: {result[5]}\n"
            f"🎯 CFG scale: {result[6]}\n"
            f"🎲 Seed: {result[7]}\n"
        )

        txt_file = os.path.splitext(fname)[0] + ".txt"
        try:
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(text_content)
            print(f"Metadata saved: {txt_file}")
        except Exception as e:
            print(f"Error while saving: {e}")
    # mappa betöltése
    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select a folder")
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
            self.image_label.setText("Failed to load image")
            self.meta_text.setPlainText(f"Failed to load: {fname}")
            self.current_pixmap = None
            return

        self.current_pixmap = pix
        self._update_image_label()

        # AI metaadatok
        result = extract_prompts(fname)
        pos = " ".join(str(result[0]).split())  # sortörés eltávolítása
        neg = " ".join(str(result[1]).split())

        # --- HTML stílus létrehozása ---
        style = """
        <style>
        .key1 { font-weight: bold; color: green;}
        .key2 { font-weight: bold; color: red;}
        .key3 { font-weight: bold; color: navy;}
        .key4 { font-weight: bold; color: blue;}
        .key5 { font-weight: bold; }
        .center { text-align: center; display: block; font-weight: bold; color: navy; }
        </style>
        """
        meta_info = f"""
        {style}
        <div class="center">{os.path.basename(fname)}</div><br>
        <span class="key1">✅ Prompt:</span> {pos}<br>
        <span class="key2">🚫 Negative Prompt:</span> {neg}<br>
        <span class="key1">📦 Checkpoint: </span><span class="key5">{result[2]}</span><br>
        <span class="key3">🔁 Sampler:</span> {result[3]} &nbsp;&nbsp;&nbsp;&nbsp;
        <span class="key3">📈 Scheduler:</span> {result[4]} &nbsp;&nbsp;&nbsp;&nbsp;
        <span class="key3">📏 Steps:</span> {result[5]}<br>
        <span class="key3">🎯 CFG scale:</span> {result[6]} &nbsp;&nbsp;&nbsp;&nbsp;
        <span class="key3">🎲 Seed:</span> {result[7]} &nbsp;&nbsp;&nbsp;&nbsp;
        """

        # HTML kiírás a QTextBrowser-be
        self.meta_text.setHtml(meta_info)

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
    w.resize(1000, 850)
    w.show()
    sys.exit(app.exec())

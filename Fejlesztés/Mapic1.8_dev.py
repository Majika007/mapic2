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
    QSizePolicy, QScrollArea, QGridLayout, QStackedWidget, QTextBrowser
)
from PyQt6.QtGui import QPixmap, QShortcut, QKeySequence, QPalette, QColor
from PyQt6.QtCore import Qt, QTimer
from PIL import Image
from threading import Thread
from PyQt6.QtCore import pyqtSignal
import time

DEBUG = True                            ##########################################################################x

def debug_log(*args):
    if DEBUG:
        print("[DEBUG]", *args)          ##################################################
        

# --- HTML/CSS stílus definíció ---
STYLE_LIGHT = """
<style>
.key1 { font-weight: bold; color: green;}
.key2 { font-weight: bold; color: red;}
.key3 { font-weight: bold; color: navy;}
.key4 { font-weight: bold; color: blue;}
.key5 { font-weight: bold; color: black;}
.center { text-align: center; display: block; font-weight: bold; color: navy;}
body { background-color: white; color: black; }
</style>
"""

STYLE_DARK = """
<style>
.key1 { font-weight: bold; color: lightgreen;}
.key2 { font-weight: bold; color: salmon;}
.key3 { font-weight: bold; color: lightskyblue;}
.key4 { font-weight: bold; color: deepskyblue;}
.key5 { font-weight: bold; color: white;}
.center { text-align: center; display: block; font-weight: bold; color: lightblue;}
body { background-color: #121212; color: white; }
</style>
"""

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
    pos, neg, ckpt, sampler, scheduler, step, cfg, seed, denoise, vae, lora = "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"
#    debug_log("extract_from_usercomment", raw_uc)                                    ##########################################
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
                denoise = str(extra.get("denoise", "-"))
                vae = str(extra.get("vae", "-"))
                lora = str(extra.get("lora", "-"))
            
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
                    denoise = str(v["inputs"].get("denoise", seed))
                    vae = str(v["inputs"].get("vae", seed))
                    lora = str(v["inputs"].get("lora", seed))

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

            # Denoise
            denoise_m = re.search(r"Denoise:\s*(\d+)", raw_uc)
            if denoise_m:
                denoise = denoise_m.group(1)

            # Vae
            vae_m = re.search(r"Vae:\s*(\d+)", raw_uc)
            if vae_m:
                vae = vae_m.group(1)

            # Lora
            lora_m = re.search(r"Lora:\s*(\d+)", raw_uc)
            if lora_m:
                lora = lora_m.group(1)

            # ModelName
            model_m = re.search(r'"modelName":"([^"]+)"', raw_uc)
            if model_m:
                ckpt = model_m.group(1)
                
            pos = decode_surrogate_pair(pos)
            neg = decode_surrogate_pair(neg)
            ckpt = decode_surrogate_pair(ckpt)

    except Exception as e:
        pos = f"Error: {e}"

    # 11 elemű tuple
    return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, "-", "-", lora)
        
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
        return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")
        
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

        # Denoise
        denoise = re.search(r'Denoise:\s*([\d.]+)', text)
        denoise = denoise.group(1) if denoise else "-"

        # Vae
        vae = re.search(r'Vae:\s*([\d.]+)', text)
        vae = vae.group(1) if denoise else "-"

        # Lora
        lora = re.search(r'Lora:\s*([\d.]+)', text)
        lora = lora.group(1) if lora else "-"

        # Neg prompt: ha van "Negative prompt:" tag
        neg = re.search(r'Negative prompt:\s*(.*?)(?:, \w+:|$)', text)
        neg = neg.group(1).strip() if neg else "-"

        return pos, neg, ckpt, sampler, "-", steps, cfg, seed, "-", "-", lora
    except Exception:
        return "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"       
        
def extract_prompts_png(image_path):
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
            return (text_all, "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-" "-")

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
        denoise     = find_key(prompt_json, "denoise") or "-"
        vae     = find_key(prompt_json, "vae") or "-"
        lora     = find_key(prompt_json, "lora") or "-"

        return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, "-", "-", lora)

    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

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
            denoise = re.search(r'Denoise:\s*(.*?)(?=,|$)', raw)
            vae = re.search(r'Vae:\s*(.*?)(?=,|$)', raw)
            lora = re.search(r'Lora:\s*(.*?)(?=,|$)', raw)

            return (
                pos.group(1).replace("\n", " ") if pos else "-",
                neg.group(1).replace("\n", " ") if neg else "-",
                ckpt.group(1) if ckpt else "-",
                sampler.group(1) if sampler else "-",
                "-",  # scheduler nincs a Parameters stringben
                step.group(1) if step else "-",
                cfg.group(1) if cfg else "-",
                seed.group(1) if seed else "-",
                denoise.group(1) if denoise else "-",
                vae.group(1) if vae else "-",
                lora.group(1) if lora else "-",
            )
        else:
            return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

    elif ext in (".jpg", ".jpeg"):
        return extract_prompts_jpg(fname)
    else:
        return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

def is_system_dark():
    palette = QApplication.palette()
    bg_color = palette.color(QPalette.ColorRole.Window)
    text_color = palette.color(QPalette.ColorRole.WindowText)
    # ha a háttér sötétebb mint a szöveg → dark mode
    return bg_color.lightness() < text_color.lightness()
    
# ---------- Main viewer ----------
class ImageViewer(QWidget):
    cache_progress = pyqtSignal(int, int)  # current, total
    
    def __init__(self):
        super().__init__()

#        self.thumbnail_cache_done = False
        # Ha van globális is_system_dark függvény, használjuk, különben False
        try:
            self.dark_mode = is_system_dark()
        except Exception:
            self.dark_mode = False

        # shortcuts (QShortcut import a QtGui-ból)
        QShortcut(QKeySequence("Right"), self, self.show_next)
        QShortcut(QKeySequence("Left"), self, self.show_prev)
        QShortcut(QKeySequence("Down"), self, self.show_next)
        QShortcut(QKeySequence("Up"), self, self.show_prev)

        self.setWindowTitle("MaPic - ImageView + AIMeta")

        # state
        self.image_files = []
        self.current_index = -1
        self.current_pixmap = None
        self.thumb_cache = {}
        self.aspect_ratio = Qt.AspectRatioMode.KeepAspectRatio
        self.smooth = Qt.TransformationMode.SmoothTransformation

        # main layout
        main_layout = QVBoxLayout(self)

        # ---------- build the existing image+meta splitter first ----------
        self.splitter = QSplitter(Qt.Orientation.Vertical, self)

        # image label (large view)
        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(200, 200)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.splitter.addWidget(self.image_label)

        # meta text area (use QTextBrowser to support HTML)
        self.meta_text = QTextBrowser()
        self.meta_text.setReadOnly(True)
        self.meta_text.setMinimumSize(120, 120)
        self.splitter.addWidget(self.meta_text)
        # most, hogy mindkét widget bent van:
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

        self.splitter.setSizes([700, 150])

        # ---------- Stacked widget: image view and thumbnail view ----------
        self.stack = QStackedWidget(self)
        # image view widget (contains the splitter)
        self.image_view_widget = QWidget()
        iv_layout = QVBoxLayout(self.image_view_widget)
        iv_layout.addWidget(self.splitter)
        self.stack.addWidget(self.image_view_widget)

        # thumbnail view (scrollable)
        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setWidgetResizable(True)
        self.thumb_container = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setHorizontalSpacing(12)
#        self.thumb_grid.setVerticalSpacing(12)
#        self.thumb_grid.setContentsMargins(8, 8, 8, 8)
#        self.thumb_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.first_width = 960
        self.thumb_scroll.setWidget(self.thumb_container)
        self.stack.addWidget(self.thumb_scroll)
        
        # thumbnail cache progress bar
        self.cache_label = QLabel("Thumbnail cache: 0 / 0")
        self.cache_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.cache_label)     
        self.cache_progress.connect(self.update_cache_label)   

        # show image view by default
        main_layout.addWidget(self.stack)
        self.stack.setCurrentWidget(self.image_view_widget)

        # ---------- control buttons ----------
        btn_layout = QHBoxLayout()
        # orientation toggle (kept)
        self.btn_toggle = QPushButton("↔ / ↕")
        self.btn_toggle.clicked.connect(self.toggle_orientation)
        btn_layout.addWidget(self.btn_toggle)

        # theme toggle
        self.btn_toggle_theme = QPushButton("☯")
        self.btn_toggle_theme.clicked.connect(self.toggle_theme)
        btn_layout.addWidget(self.btn_toggle_theme)

        # open folder
        self.btn_open = QPushButton("Open folder")
        self.btn_open.clicked.connect(self.open_folder)
        btn_layout.addWidget(self.btn_open)

        # prev / next
        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.clicked.connect(self.show_prev)
        btn_layout.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self.show_next)
        btn_layout.addWidget(self.btn_next)

        # save metadata
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save_meta)
        btn_layout.addWidget(self.btn_save)
        

        main_layout.addLayout(btn_layout)

        # ---------- interactions ----------
        # single-click the large image -> open thumbnails
        # assign inside __init__ (self exists here)
        self.image_label.mousePressEvent = self.show_thumbnails

        # ensure we have a small startup load (keeps the previous behavior)
        try:
            self.load_current_folder()
        except Exception:
            # if you don't have load_current_folder, it's OK; nothing loaded
            pass

        QTimer.singleShot(20, self._update_image_label)
        

    # ---------------- helper: get a thumbnail (with cache) ----------------
    
    def start_thumbnail_cache(self):
        if hasattr(self, "_cache_thread_started") and self._cache_thread_started:
            return
        self._cache_thread_started = True
        thread = Thread(target=self.preload_thumbnails, daemon=True)
        thread.start()

    def preload_thumbnails(self):
        w, h = 160, 120  # thumbnail méret
        for i, path in enumerate(self.image_files, start=1):
            pix = QPixmap(path)
            if pix.isNull():
                # üres thumbnail, ha valami hiba
                thumb = QPixmap(w, h)
                thumb.fill(Qt.GlobalColor.transparent)
            else:
                thumb = pix.scaled(w, h, self.aspect_ratio, self.smooth)
                self.thumb_cache[path] = thumb
                self.cache_progress.emit(i, len(self.image_files))  # frissítjük a progress jelzést
#            self.cache_progress.emit(i, total)  # frissítjük a progress jelzést
            
    # ---------------- show thumbnails grid ----------------
#    def resizeEvent(self, event):
#        super().resizeEvent(event)
#        if hasattr(self, 'thumb_grid') and hasattr(self, 'image_files'):
#            self.show_thumbnails()

    def update_cache_label(self, current, total):
        self.cache_label.setText(f"Thumbnail cache: {current} / {total}")

    def show_thumbnails(self, event=None):
        if not self.image_files:
            return
        # thumbnail méret + spacing
        thumb_w, thumb_h = 160, 120
        spacing = self.thumb_grid.horizontalSpacing() or 12

        container_width = self.first_width
        sys.stdout.flush()    
        # számoljuk, hány fér el vízszintesen
        cols = max(1, container_width // (thumb_w + spacing))
        
        # clear existing grid widgets
        for i in reversed(range(self.thumb_grid.count())):
            widget_item = self.thumb_grid.itemAt(i)
            if widget_item:
                w = widget_item.widget()
                if w:
                    w.setParent(None)

        for i, path in enumerate(self.image_files):
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = self.thumb_cache.get(path, QPixmap(thumb_w, thumb_h))
            lbl.setPixmap(pixmap)
            lbl.setToolTip(os.path.basename(path))
            lbl.mousePressEvent = lambda e, idx=i: self.open_image_from_thumb(idx)
            row, col = divmod(i, cols)
            self.thumb_grid.addWidget(lbl, row, col)

        # mutassuk a thumb scrollt
        self.stack.setCurrentWidget(self.thumb_scroll)
        self.first_width = self.thumb_scroll.viewport().width()

    # ---------------- open image from thumbnail click ----------------
    def open_image_from_thumb(self, index):
        if not (0 <= index < len(self.image_files)):
            return
        self.current_index = index
        self.show_image(self.image_files[self.current_index])
        # switch back to primary image view
        self.stack.setCurrentWidget(self.image_view_widget)

    # ---------------- safe image rescale from cached pixmap ----------------    #
    def _update_image_label(self):
        if not self.current_pixmap or self.current_pixmap.isNull():
            self.image_label.setText("No image loaded")
            return
        w = max(50, self.image_label.width())
        h = max(50, self.image_label.height())
        scaled = self.current_pixmap.scaled(w, h, self.aspect_ratio, self.smooth)
        self.image_label.setPixmap(scaled)
        

    # ---------------- show a single image + meta ----------------
    def show_image(self, fname):
        pix = QPixmap(fname)
        if pix.isNull():
            self.image_label.setText("Failed to load image")
            self.meta_text.setPlainText(f"Failed to load: {fname}")
            self.current_pixmap = None
            return

        self.current_pixmap = pix
        # update label from cache pixmap
        self._update_image_label()

        # keep current_index in sync
        if fname in self.image_files:
            self.current_index = self.image_files.index(fname)

        # AI meta extraction (uses your existing extract_prompts function)
        try:
            result = extract_prompts(fname)
        except Exception as e:
            result = (f"Error: {e}",) + tuple(["N/A"] * 10)

        pos = " ".join(str(result[0]).split()) if result and result[0] else "N/A"
        neg = " ".join(str(result[1]).split()) if result and result[1] else "N/A"
        img_width = pix.width()
        img_height = pix.height()

        # build HTML using your get_style() method if exists, else fallback
        try:
            style_block = self.get_style()
        except Exception:
            # fallback: try global styles
            style_block = (globals().get("STYLE_DARK") if self.dark_mode else globals().get("STYLE_LIGHT", ""))

        meta_html = f"""
        {style_block}
        <div class="center">{os.path.basename(fname)} </div>&nbsp;&nbsp;({img_width} x {img_height} px)<br>
        <span class="key1">✅ Prompt:</span> {pos}<br>
        <span class="key2">🚫 Negative Prompt:</span> {neg}<br>
        <span class="key1">📦 Checkpoint: </span><span class="key5">{result[2]}</span><br>
        <span class="key3">🔁 Sampler:</span> {result[3]} &nbsp;&nbsp;&nbsp;&nbsp;
        <span class="key3">📈 Scheduler:</span> {result[4]} &nbsp;&nbsp;&nbsp;&nbsp;
        <span class="key3">📏 Steps:</span> {result[5]}<br>
        <span class="key3">🎯 CFG scale:</span> {result[6]} &nbsp;&nbsp;&nbsp;&nbsp;
        <span class="key3">🎲 Seed:</span> {result[7]} &nbsp;&nbsp;&nbsp;&nbsp;
        <!--<span class="key">🌀 Denoise:</span> {result[8]}<br>
        <span class="key">🧠 VAE:</span> {result[9]}<br>-->
        <span class="key">✨ LoRA:</span> {result[10]}
        """

        self.meta_text.setHtml(meta_html)
        # ensure we are in the image view
        self.stack.setCurrentWidget(self.image_view_widget)
        
#        if not self.thumbnail_cache_done:
#            self.start_thumbnail_cache()
#            self.thumbnail_cache_done = True

    # ---------------- get_style method (uses your global STYLE_* constants) ----------------
    def get_style(self):
        # prefer an internal dark_mode flag; STYLE_LIGHT/STYLE_DARK expected global
        return globals().get("STYLE_DARK") if self.dark_mode else globals().get("STYLE_LIGHT", "")

    # ---------------- toggle theme ----------------
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        # refresh meta display / style
        if self.image_files and 0 <= self.current_index < len(self.image_files):
            self.show_image(self.image_files[self.current_index])
        else:
            # just update style block in the meta area
            self.meta_text.setHtml(self.get_style())

    # ---------------- next / prev image ----------------
    def show_next(self):
        if self.image_files and self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_image(self.image_files[self.current_index])

    def show_prev(self):
        if self.image_files and self.current_index > 0:
            self.current_index -= 1
            self.show_image(self.image_files[self.current_index])

    # ---------------- open folder (clears thumbnail cache) ----------------
    def open_folder(self): 
        folder = QFileDialog.getExistingDirectory(self, "Select folder") 
        if not folder: 
            return 
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp") 
        self.image_files = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)]) 
        self.current_index = 0 if self.image_files else -1 
        self._cache_thread_started = False
        self.thumb_cache.clear() # clear old thumbs 
        self.cache_total = 0
        self.cache_current = 0
        if self.image_files: 
            self.show_image(self.image_files[self.current_index]) 
        QTimer.singleShot(100, self.start_thumbnail_cache)

    # ---------------- load current folder at startup ----------------
    def load_current_folder(self):
        folder = os.getcwd()
        exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")
        self.image_files = sorted([os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)])
        self.current_index = 0 if self.image_files else -1
        self.thumb_cache.clear()
        if self.image_files:
            self.show_image(self.image_files[self.current_index])
        QTimer.singleShot(100, self.start_thumbnail_cache)

    # ---------------- toggle splitter orientation ----------------
    def toggle_orientation(self):
        s = self.splitter
        old_sizes = s.sizes()
        total_old = sum(old_sizes) if sum(old_sizes) > 0 else 1
        ratios = [float(x) / total_old for x in old_sizes]
        # set minimums so nothing collapses
        for i in range(s.count()):
            w = s.widget(i)
            if w:
                w.setMinimumSize(50, 50)
        # toggle orientation
        if s.orientation() == Qt.Orientation.Vertical:
            s.setOrientation(Qt.Orientation.Horizontal)
        else:
            s.setOrientation(Qt.Orientation.Vertical)
        # apply sizes based on new geometry after layout settles
        s.setSizes([max(50, int(r * (s.width() if s.orientation()==Qt.Orientation.Horizontal else s.height()))) for r in ratios])
        # update image scale
        self._update_image_label()

    # ---------------- save metadata to txt ----------------
    def save_meta(self):
        if not (self.image_files and 0 <= self.current_index < len(self.image_files)):
            return
        fname = self.image_files[self.current_index]
        try:
            result = extract_prompts(fname)
        except Exception as e:
            result = (f"Error: {e}",) + tuple(["N/A"] * 10)
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
            f"🌀 Denoise: {result[8]}\n"
            f"🧠 VAE: {result[9]}\n"
            f"✨ LoRA: {result[10]}\n"
        )
        txt_file = os.path.splitext(fname)[0] + ".txt"
        try:
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(text_content)
        except Exception as e:
            print("Save error:", e)

    # ---------------- handle resize -> rescale current pixmap ----------------
#    def resizeEvent(self, event):
#        super().resizeEvent(event)
#        # use a slight delay to allow layout updates, then rescale
#        self._update_image_label()

    # ---------------- optional: keyPressEvent fallback ----------------
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

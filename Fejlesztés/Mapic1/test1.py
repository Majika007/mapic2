import os
import json
from PIL import Image
import exifread

def extract_prompts_png(image_path):
    """AI metaadatok beolvasása PNG képből"""
    try:
        img = Image.open(image_path)
        metadata = img.info
        raw_prompt = metadata.get("prompt", None)
        if not raw_prompt:
            return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

        prompt_json = json.loads(raw_prompt)
        # első "text" pozitív, második negatív
        texts = [v.get("text", "-") for k, v in prompt_json.items() if isinstance(v, dict)]
        pos = texts[0] if len(texts) > 0 else "-"
        neg = texts[1] if len(texts) > 1 else "-"
        # további mezők
        ckpt = next((v.get("ckpt_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "ckpt_name" in v), "-")
        sampler = next((v.get("sampler_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "sampler_name" in v), "-")
        scheduler = next((v.get("scheduler", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "scheduler" in v), "-")
        step = next((v.get("steps", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "steps" in v), "-")
        cfg = next((v.get("cfg", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "cfg" in v), "-")
        seed = next((v.get("seed", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "seed" in v), "-")
        denoise = next((v.get("denoise", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "denoise" in v), "-")
        vae = next((v.get("vae_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "vae_name" in v), "-")
        lora = next((v.get("lora_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "lora_name" in v), "-")

        return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, denoise, vae, lora)
    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

def extract_prompts_jpg(image_path):
    """AI metaadatok beolvasása JPG képből (UserComment EXIF)"""
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            user_comment = None
            # keressük a UserComment-et
            for k, v in tags.items():
                if "UserComment" in k:
                    user_comment = v.values
                    break

            if not user_comment:
                return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

            # byte / string kezelés
            if isinstance(user_comment, bytes):
                try:
                    raw = user_comment.decode("utf-8")
                except UnicodeDecodeError:
                    try:
                        raw = user_comment.decode("utf-16")
                    except:
                        raw = user_comment.decode("latin1", errors="ignore")
            else:
                raw = str(user_comment)

            # prefix levágása, pl. ASCII
            if raw.startswith("ASCII\0"):
                raw = raw[6:]

            prompt_json = json.loads(raw)

            texts = [v.get("text", "-") for k, v in prompt_json.items() if isinstance(v, dict)]
            pos = texts[0] if len(texts) > 0 else "-"
            neg = texts[1] if len(texts) > 1 else "-"
            ckpt = next((v.get("ckpt_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "ckpt_name" in v), "-")
            sampler = next((v.get("sampler_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "sampler_name" in v), "-")
            scheduler = next((v.get("scheduler", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "scheduler" in v), "-")
            step = next((v.get("steps", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "steps" in v), "-")
            cfg = next((v.get("cfg", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "cfg" in v), "-")
            seed = next((v.get("seed", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "seed" in v), "-")
            denoise = next((v.get("denoise", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "denoise" in v), "-")
            vae = next((v.get("vae_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "vae_name" in v), "-")
            lora = next((v.get("lora_name", "-") for k, v in prompt_json.items() if isinstance(v, dict) and "lora_name" in v), "-")

            return (pos, neg, ckpt, sampler, scheduler, step, cfg, seed, denoise, vae, lora)

    except Exception as e:
        return (f"Error: {e}", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

def extract_prompts(fname):
    """Függvény, ami a kiterjesztés alapján hívja a megfelelő beolvasót"""
    ext = os.path.splitext(fname)[1].lower()
    if ext == ".png":
        return extract_prompts_png(fname)
    elif ext in (".jpg", ".jpeg"):
        return extract_prompts_jpg(fname)
    else:
        return ("N/A", "N/A", "-", "-", "-", "-", "-", "-", "-", "-", "-")

# --- Teszt futtatás ---
if __name__ == "__main__":
    folder = os.getcwd()  # aktuális mappa
    exts = (".png", ".jpg", ".jpeg")
    images = sorted([f for f in os.listdir(folder) if f.lower().endswith(exts)])

    if not images:
        print("Nincs PNG vagy JPG a mappában!")
    else:
        for img in images:
            result = extract_prompts(img)
            print(f"\n--- {img} ---")
            labels = ["✅ Prompt", "🚫 Negative Prompt", "📦 Checkpoint", "🔁 Sampler",
                      "📈 Scheduler", "📏 Steps", "🎯 CFG scale", "🎲 Seed",
                      "🌀 Denoise", "🧠 VAE", "✨ LoRA"]
            for label, val in zip(labels, result):
                print(f"{label}: {val}")

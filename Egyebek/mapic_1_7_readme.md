# MaPic 1.8

## AI Image Viewer

MaPic is a lightweight image viewer designed for AI-generated images. It displays images along with essential metadata such as prompts, samplers, checkpoints, (LoRAs - later), and image dimensions.

### Features
- Display AI-generated image metadata alongside the image
- Shows image dimensions (width × height)
- Dark/Light mode, automatically detects system theme
- Easy navigation with buttons and arrow keys
- Save metadata to TXT files
I decided to add a thumbnail mode!

## Installation & Running

You need Python 3.9+.

1. First, install the required Python packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

2. Then run:

```bash
python Mapic.py
```

### Additional Requirement for JPEG Metadata

For reading metadata from JPEG files, the program relies on **ExifTool**. Make sure it is installed on your system:

- **Linux (Debian/Ubuntu):**
  ```bash
  sudo apt install exiftool
  ```
- **Windows:** Download from [https://exiftool.org](https://exiftool.org) and add it to your system PATH.
- **macOS:**
  ```bash
  brew install exiftool
  ```

## requirements.txt

```
PyQt6
Pillow
```

### Notes
- The Dark/Light mode can be toggled anytime with the ☯ button.
- The viewer is optimized for checking multiple AI-generated images and comparing outputs.
- Feedback and suggestions for future features are welcome.
- Now, when you click on any image, the viewer switches into a thumbnail grid, showing all the images in that folder at once. You can select any image to jump back into full view instantly.

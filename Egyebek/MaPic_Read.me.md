# MaPic – Image Viewer and AI Metadata Reader

## Description
MaPic is a lightweight python program for viewing images and inspecting AI generation metadata.  
It is especially useful for AI-generated images where prompts, sampler, seed, and other parameters are stored inside the image metadata.  
Supports both PNG and JPEG/JPG formats.  
The program displays the image alongside its metadata, and also provides an option to save the metadata into a TXT file.
I add a thumbnail mode!

## Features
- Browse images with Previous / Next buttons or arrow keys.
- View AI metadata: Prompt, Negative Prompt, Checkpoint, Sampler, Scheduler, Steps, CFG scale, Seed, Denoise, (VAE, LoRA. - later)
- Metadata is shown in a colored, easy-to-read format.
- Save metadata to a `.txt` file with the Save button (overwrites if the file already exists).
- Automatically loads images from the current folder on startup.
- Supported formats: PNG, JPG, JPEG.
- Now, when you click on any image, the viewer switches into a thumbnail grid, showing all the images in that folder at once. You can select any image to jump back into full view instantly.
On startup, the app caches thumbnails automatically — this can take a few seconds if you have hundreds of images, but you’ll see a small progress indicator in the top-right corner while it’s working.

## Usage
1. Start the program:
   ```bash
   python Mapic1.8.py
   ```
2. The program automatically loads all images from the current folder.  
3. Use arrow keys or the ◀ / ▶ buttons to navigate between images.  
4. Use the **Save** button to export metadata into a `.txt` file.  
5. Thumbnail Mode – You can now switch to a grid view by clicking on any displayed image.
Thumbnail Cache – When opening a folder, Mapic builds a thumbnail cache for fast loading on subsequent runs.

## Layout & Resizing
- Image and metadata panels are separated by a resizable splitter.  
- The splitter can be dragged to change relative sizes.  
- Metadata panel is scrollable and supports automatic line wrapping.  
- When resizing the window, images keep their aspect ratio.  
- Metadata headers (Prompt, Checkpoint, etc.) are colored and bold for readability.  

## Important Notes
- The program has been tested with PNG and JPEG formats.  
- Metadata formats are not always consistent across files, so in some cases fields may not be perfectly separated.  
- Accuracy is not guaranteed to be 100%.  

## Installation & Running

You need Python 3.9+.

1. First, install the required Python packages from `requirements.txt`:

```bash
pip install -r requirements.txt
```

2. Then run:

```bash
python Mapic1.8.py
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
exifread
```

### Notes
- The Dark/Light mode can be toggled anytime with the ☯ button. (only colors in the text)
- The viewer is optimized for checking multiple AI-generated images and comparing outputs.
- Feedback and suggestions for future features are welcome.

## Author
Developed by **Majika77** with assistance from *ChatGPT (OpenAI GPT-5)*  

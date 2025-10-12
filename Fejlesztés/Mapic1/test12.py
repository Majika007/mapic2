import exifread, subprocess, json, codecs
f = "0nyuszis.jpeg"
with open(f,'rb') as fh:
    tags = exifread.process_file(fh, details=False)
    uc = tags.get("EXIF UserComment") or tags.get("UserComment")
    print("exifread UserComment repr:", repr(uc.values) if uc else "None")

p = subprocess.run(['exiftool','-j','-G1','-a',f], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
print("exiftool returncode:", p.returncode)
print("exiftool stdout (first 1000 chars):", p.stdout[:1000])
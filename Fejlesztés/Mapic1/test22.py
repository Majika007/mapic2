from PIL import Image, ExifTags

img = Image.open("111df8e2.jpeg")
exif = img.getexif()
for tag_id, value in exif.items():
    tag = ExifTags.TAGS.get(tag_id, tag_id)
    print(f"{tag:25}: {value}")
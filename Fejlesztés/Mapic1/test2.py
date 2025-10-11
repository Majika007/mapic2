import exifread

with open("111df8e2.jpeg", "rb") as f:
    tags = exifread.process_file(f, details=False)

for k, v in tags.items():
    print(k, "=", v)
    
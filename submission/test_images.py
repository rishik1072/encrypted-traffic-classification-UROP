from pathlib import Path
from PIL import Image

assets_dir = Path('UROP_Report/Assets')
for img_path in assets_dir.glob('*.png'):
    im = Image.open(img_path)
    print(f'{img_path.name}: {im.size} (aspect {im.size[0]/im.size[1]:.2f})')

import xml.etree.ElementTree as ET
import os
import random

VOC_ROOT = r'E:\fire-smoke-detect-yolov4\VOC2020'
CLASSES = ['fire', 'smoke']  # nc=2

def convert_label(size, box):
    dw = 1. / size[0]
    dh = 1. / size[1]
    x = (box[0] + box[1]) / 2.0 - 1
    y = (box[2] + box[3]) / 2.0 - 1
    w = box[1] - box[0]
    h = box[3] - box[2]
    return (x * dw, y * dh, w * dw, h * dh)

def convert_annotation(img_id):
    in_path = f'{VOC_ROOT}/Annotations/{img_id}.xml'
    out_path = f'{VOC_ROOT}/labels/{img_id}.txt'
    tree = ET.parse(in_path)
    root = tree.getroot()
    size = root.find('size')
    w = int(size.find('width').text)
    h = int(size.find('height').text)
    lines = []
    for obj in root.iter('object'):
        cls = obj.find('name').text
        if cls not in CLASSES:
            continue
        cls_id = CLASSES.index(cls)
        box = obj.find('bndbox')
        b = (float(box.find('xmin').text), float(box.find('xmax').text),
             float(box.find('ymin').text), float(box.find('ymax').text))
        bb = convert_label((w, h), b)
        lines.append(f"{cls_id} {' '.join(f'{x:.6f}' for x in bb)}")
    with open(out_path, 'w') as f:
        f.write('\n'.join(lines))

# Create labels directory
os.makedirs(f'{VOC_ROOT}/labels', exist_ok=True)

# Generate train/val split from ImageSets
split_file = f'{VOC_ROOT}/ImageSets/Main/train.txt'
with open(split_file) as f:
    train_ids = [line.strip() for line in f if line.strip()]

all_ids = [os.path.splitext(f)[0] for f in os.listdir(f'{VOC_ROOT}/Annotations') if f.endswith('.xml')]
val_ids = [f for f in all_ids if f not in train_ids]
if not val_ids:
    random.shuffle(all_ids)
    split = int(len(all_ids) * 0.8)
    train_ids = all_ids[:split]
    val_ids = all_ids[split:]

# Convert labels
for img_id in train_ids + val_ids:
    convert_annotation(img_id)

# Write train.txt and val.txt
with open(f'{VOC_ROOT}/train.txt', 'w') as f:
    for img_id in train_ids:
        f.write(f'{VOC_ROOT}/JPEGImages/{img_id}.jpg\n')

with open(f'{VOC_ROOT}/val.txt', 'w') as f:
    for img_id in val_ids:
        f.write(f'{VOC_ROOT}/JPEGImages/{img_id}.jpg\n')

print(f'Done: {len(train_ids)} train, {len(val_ids)} val')

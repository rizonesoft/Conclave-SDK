import json
import os
import sys
import tempfile

from PIL import Image, ImageDraw


def create_validation_image(page_number, fields_json_path, input_path, output_path):
    with open(fields_json_path, "r") as f:
        data = json.load(f)

    out_abs = os.path.abspath(output_path)
    out_dir = os.path.dirname(out_abs) or "."
    os.makedirs(out_dir, exist_ok=True)
    suffix = os.path.splitext(out_abs)[1] or ".png"

    with Image.open(input_path) as src_img:
        img = src_img.copy()

    tmp_path = None
    try:
        draw = ImageDraw.Draw(img)
        num_boxes = 0

        for field in data["form_fields"]:
            if field["page_number"] == page_number:
                entry_box = field["entry_bounding_box"]
                label_box = field["label_bounding_box"]
                draw.rectangle(entry_box, outline="red", width=2)
                draw.rectangle(label_box, outline="blue", width=2)
                num_boxes += 2

        fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(out_abs) + ".tmp.",
            suffix=suffix,
            dir=out_dir,
        )
        os.close(fd)
        img.save(tmp_path)
        os.replace(tmp_path, out_abs)
        tmp_path = None
    except BaseException:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    finally:
        img.close()

    print(f"Created validation image at {output_path} with {num_boxes} bounding boxes")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: create_validation_image.py [page number] [fields.json file] [input image path] [output image path]")
        sys.exit(1)
    page_number = int(sys.argv[1])
    fields_json_path = sys.argv[2]
    input_image_path = sys.argv[3]
    output_image_path = sys.argv[4]
    create_validation_image(page_number, fields_json_path, input_image_path, output_image_path)

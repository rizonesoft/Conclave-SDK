import os
import sys
import tempfile

from pdf2image import convert_from_path, pdfinfo_from_path


BATCH_SIZE = 10


def convert(pdf_path, output_dir, max_dim=1000, batch_size=BATCH_SIZE):
    os.makedirs(output_dir, exist_ok=True)
    info = pdfinfo_from_path(pdf_path)
    total_pages = int(info.get("Pages", 0))
    converted_count = 0

    for start_page in range(1, total_pages + 1, batch_size):
        end_page = min(start_page + batch_size - 1, total_pages)
        images = convert_from_path(
            pdf_path,
            dpi=200,
            first_page=start_page,
            last_page=end_page,
            size=max_dim if max_dim else None,
        )
        for offset, image in enumerate(images):
            page_num = start_page + offset
            image_path = os.path.join(output_dir, f"page_{page_num}.png")
            tmp_path = None
            try:
                width, height = image.size
                if max_dim and (width > max_dim or height > max_dim):
                    scale_factor = min(max_dim / width, max_dim / height)
                    new_width = max(1, int(width * scale_factor))
                    new_height = max(1, int(height * scale_factor))
                    resized = image.resize((new_width, new_height))
                    image.close()
                    image = resized

                fd, tmp_path = tempfile.mkstemp(
                    prefix=f"page_{page_num}.png.",
                    suffix=".tmp",
                    dir=output_dir,
                )
                os.close(fd)
                image.save(tmp_path, format="PNG")
                os.replace(tmp_path, image_path)
                tmp_path = None
                final_size = image.size
            except BaseException:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
            finally:
                image.close()

            print(f"Saved page {page_num} as {image_path} (size: {final_size})")
            converted_count += 1

    print(f"Converted {converted_count} pages to PNG images")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: convert_pdf_to_images.py [input pdf] [output directory]")
        sys.exit(1)
    pdf_path = sys.argv[1]
    output_directory = sys.argv[2]
    convert(pdf_path, output_directory)

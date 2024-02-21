from pathlib import Path
from typing import Union
from tqdm import tqdm
import fitz_new as fitz


class ExtractRentalPdf:
    def __init__(self, pdf: Union[Path, bytes]):
        if isinstance(pdf, bytes):
            self._pdf_open = fitz.open(stream=pdf)
            return

        self._pdf_open = fitz.open(pdf)

    def extract_img(self):
        images = []
        prev_images = None
        for page_index in tqdm(reversed(range(len(self._pdf_open))), desc="pdf_pages"):
            current_images = self._pdf_open.get_page_images(page_index)
            if prev_images == current_images:
                print(f"found duplicate {len(images)}")
                return images
            prev_images = None if current_images == [] else current_images

            for index, img in enumerate(current_images):
                pix = fitz.Pixmap(self._pdf_open, img[0])
                images.append(pix.tobytes())
                #pix.save(Path(output_path, f"{page_index}-{index}.jpg"))

        return images

    def extract_tables(self):
        tables_out = {}
        for page in self._pdf_open:
            for table in page.find_tables():
                for key, value in table.extract():
                    tables_out[key.lower()] = value.lower()

        return tables_out

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._pdf_open.close()

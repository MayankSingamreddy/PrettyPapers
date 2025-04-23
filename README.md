# PrettyPapers
![PrettyPapers Example](./Readmeimage.png)

Make research papers more fun to read by adding a stylized background image!

This script takes a source PDF and a background image, then generates a new PDF where:

*   Each page features the provided background image, resized, blurred, and with added film grain.
*   The original text, vector drawings, and raster images from the source PDF are overlaid on the background.
*   Black or near-black text is automatically converted to white for better readability against potentially dark backgrounds. Other text colors are preserved.
*   The general layout and formatting (including font styles like bold/italic and text rotation) are maintained.

## Requirements

*   Python 3
*   PyMuPDF (`pip install pymupdf`)
*   Pillow (`pip install Pillow`)
*   NumPy (`pip install numpy`)

## Usage

1.  **Modify the script:** Open `addimage.py` and change the `pdf_path`, `bg_path`, and `out_path` variables at the bottom of the file to point to your input PDF, desired background image, and the desired output file name.

    ```python
    # ---------- run ----------
    stylise_pdf(
        pdf_path="YOUR_PAPER.pdf",      # Input PDF path
        bg_path="YOUR_BACKGROUND.jpg", # Background image path
        out_path="OUTPUT_STYLED.pdf",  # Output PDF path
    )
    ```

2.  **Run the script:**

    ```bash
    python addimage.py
    ```

This will create the stylized PDF at the specified `out_path`.

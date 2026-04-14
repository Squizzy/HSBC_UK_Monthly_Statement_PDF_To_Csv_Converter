import PyPDF2 # type: ignore
from os import path
# from typing import List

class PdfDocument:
    def __init__(self, filename: str, file_path: str):
        self.filename = filename
        self.file_path = file_path
        self.text_content = ""

    def load_pdf(self):
        with open(self.file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num in range(len(pdf_reader.pages)):
                self.text_content += pdf_reader.pages[page_num].extract_text()

class PdfLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_pdf(self) -> PdfDocument:
        filename = path.basename(self.file_path)
        pdf_doc = PdfDocument(filename, self.file_path)
        pdf_doc.load_pdf()
        return pdf_doc

if __name__ == "__main__":
    # Specify the path to your PDF file
    pdf_file_path = 'path_to_your_pdf.pdf'

    loader = PdfLoader(pdf_file_path)
    doc = loader.load_pdf()

    print("PDF Document Text:")
    for page_num, text in enumerate(doc.text_content.split('\n')):
        print(f"Page {page_num+1}:")
        print(text)
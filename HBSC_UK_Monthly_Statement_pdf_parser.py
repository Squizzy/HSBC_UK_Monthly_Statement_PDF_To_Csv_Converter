""" Python application to convert HSBC UK Consumer Monthly Statement PDF 
into CSV files for import into Excel or money managers"""

__author__ = "Squizzy"
__copyright__ = "Copyright 2024, Squizzy"
__credits__ = ""
__license__ = "GPL"
__version__ = "0.2"
__maintainer__ = "Squizzy"

import pypdf
import re
import csv
import os
from datetime import datetime

# from pprint import pprint

# Modify INPUT_FILE below to point to the PDF you want to process.
# for example, if the file is called file.pdf in the same folder as this .py file, use :  INPUT_FILE = 'file.pdf
# INPUT_FILE = ''
# Now obsolete

# This is the raw data output, it was mostly useful for development
# OUTPUT_FILE_RAW = 'output.txt'
# Now obsolete

# This is the filenme that is created from the PDF.
# This filename cane be changed if desired, of course.
# In Excel, the file can be imported by:
#   - Create a blank xls sheet
#   - Go to Data tab, then select "from text". Find the output.cvs file that this file has created.
#   - On the window that opens, select 'Delimited' and also add a tick to 'My data has headers' Click Next
#   - Under Delimiters, select Tab, click Next
#   - Under Data Column Format for the first column, it is possible to select "Date". Click Finish.
#   - select OK
# OUTPUT_FILE_CVS = 'output.csv'
# Now obsolete

# DATE:
# word boundary | 2 digits | space | 2 or 3 chars | space | 2 digits | word boundary
REGEX_date = r"^(\b\d{2}\s\w{3,4}\s\d{2}\b)?"

# PRESENTATIONAL SPACING:
# 0 or more spaces
REGEX_space1 = r"(?:\s*)"

# TRANSACTION TYPE:
# 2 or 3 upper case letters CR, SO, ... or ))) (supposedly, contactless payment)
# REGEX_type = r'([A-Z\)]{2,3})?'
# One of the choices of DD, CD, SO, VIS, BP, ATM, \\\ - if any needs to be added, they can be separated with OR ( '|' )
REGEX_type = r"(?:\s(DD|\)\)\)|CR|SO|VIS|BP|ATM)\s)?"

# PRESENTATIONAL SPACING:
# 0 or more spaces
REGEX_space2 = r"(?:\s+)"

# TRANSACTION DETAIL:
# word boundary | one or more of a-z, A-Z, /, ., *, - | word boundary | (Optional, repeated 0 or more times: space|word boundary | one or more of a-z, A-Z, /, ., *, - | word boundary | Optional End of String)
REGEX_detail = r"(\b[a-zA-Z0-9\/\.\*\-\@\:]+\b(?:\s{1,5}\b[a-zA-Z0-9\/\.\*\-\@\:]+\b)*)"

# PRESENTATIONAL SPACING:
# (Optional: 0 or more spaces)
REGEX_space3 = r"(?:\s+)?"

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_paid_out = r"((?:\d+,)?\d+[\.]?\d*)?"

# PRESENTATIONAL SPACING:
# (Optional: 0 or more spaces)
REGEX_space4 = r"(?:\s*)?"

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_paid_in = r"((?:\d+,)?\d+[\.]?\d*)?"

# PRESENTATIONAL SPACING:
# (Optional: 0 or more spaces)
REGEX_space5 = r"(?:\s*)?"

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_balance = r"((?:\d+,)?\d+[\.]?\d*)?"


LINE_DETAILS_EXTRACTION_REGEX = (
    REGEX_date
    + REGEX_space1
    + REGEX_type
    + REGEX_space2
    + REGEX_detail
    + REGEX_space3
    + REGEX_paid_out
    + REGEX_space4
    + REGEX_paid_in
    + REGEX_space5
    + REGEX_balance
)


def log(text: str) -> None:
    print(text)


# open a popup to find and select the file to process
def acquire_filename() -> str:
    log("Selecting the file")
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="select file", initialdir=".", filetypes=[("PDF files", "*.pdf")]
    )

    return file_path


def load_pdf_pages(input_file) -> list[list[str]]:
    log("Loading PDF pages into a list of strings")
    lines_list: list[list[str]] = []

    with open(input_file, "rb") as file:
        pdf_file = pypdf.PdfReader(file)
        pages = pdf_file.pages

        for page in pages:
            lines: str = page.extract_text(
                extraction_mode="layout",
                layout_mode_space_vertically=False,
                layout_mode_scale_weight=0.98,
            )
            lines_list.append(lines.split("\n"))

    return lines_list


def cleanout_useless_lines_from_pdf_import(all_lines: list[list[str]],) -> list[list[str]]:
    log("Removing the lines which can't be used by money managers")
    kept_lines_list: list[list[str]] = []

    for lines_list in all_lines:
        kept_lines = []
        keep_line = False

        for line in lines_list:
            if "BALANCE CARRIED FORWARD" in line:
                keep_line = False
            if keep_line:
                kept_lines.append(line)
            if "BALANCE BROUGHT FORWARD" in line:
                keep_line = True
        kept_lines_list.append(kept_lines)
        keep_line = False

    return kept_lines_list


def extract_line_info_into_dict(all_lines) -> list[dict[str, str]]:
    log("Extracting each line into a dictionary")

    extracted_lines: list[dict[str, str]] = []

    # Extract the relevant info from the lines into a list of lists of strings
    for lines_list in all_lines:
        for line in lines_list:
            extracted_info = re.findall(LINE_DETAILS_EXTRACTION_REGEX, line)[0]
            ei = {
                "date": extracted_info[0],
                "type": extracted_info[1],
                "detail": extracted_info[2],
                "paid out": extracted_info[3],
                "paid in": extracted_info[4],
                "balance": extracted_info[5],
            }
            extracted_lines.append(ei)
    return extracted_lines


def combine_split_lines(extracted_lines: list[dict[str, str]]) -> list[dict[str, str]]:
    log("Combining lines split over two lines")
    # Sometimes HSBC PDF present a statement over two lines. the amounts are on the second one.
    # For a decent output, we need to combine these two lines into one.
    # It seems the difference is that one line has the transaction type and the begining of the transaction detail.
    # The second line has the remainder of the transaction detail, and the amount(s)

    combined_split_lines: list[dict[str, str]] = []
    
    # n = 0
    
    for i in range(len(extracted_lines) - 1):

        # print (f'{i=}\t t = {extracted_lines[i]["type"]}\t po = {extracted_lines[i]["type"]}')
        # print (f'{i+1=}\t t = {extracted_lines[i+1]["type"]}\t po = {extracted_lines[i+1]["type"]}')

        # 1) If the transation type and the first amount are found, the line is complete, copy over
        if extracted_lines[i]["type"] and extracted_lines[i]["paid out"]:
            combined_split_lines.append(extracted_lines[i])

        # 2) If the transaction type is found but no amount is found,
        # confirm that the next line has no transaction type but an amount.
        # In this case, combine
        elif extracted_lines[i]["type"] and not extracted_lines[i]["paid out"]:
            if (
                not extracted_lines[i + 1]["type"]
                and extracted_lines[i + 1]["paid out"]
            ):
                combined_line = {
                    "date": extracted_lines[i]["date"],  # date from current line
                    "type": extracted_lines[i]["type"],  # type from current line
                    "detail": extracted_lines[i]["detail"]
                    + " "
                    + extracted_lines[i + 1][
                        "detail"
                    ],  # detail from current and next lines
                    "paid out": extracted_lines[i + 1][
                        "paid out"
                    ],  # first amount from the next line
                    "paid in": extracted_lines[i + 1][
                        "paid in"
                    ],  # second amount from the next line
                    "balance": extracted_lines[i + 1][
                        "balance"
                    ],  # third amount from the next line - should be empty
                }
                combined_split_lines.append(combined_line)
                # n = n + 1
                # print("Combine line:", combined_line)

        # If we reach here, we're on the next line that has been processed in the second round
        # so we have no processing to do
        else:
            continue
        
    # print(f"Number of lines combined: {n}")
    return combined_split_lines


def fix_amount_column_position(combined_split_lines) -> list[dict[str, str]]:
    log(
        """Correcting the positioning of the amount, 
          depending on whether it is a Credit (paid in) or a Debit (paid out), 
          and the balance"""
    )
    
    # 3) Now the amounts need to be moved to the correct column, ie position in the field
    # On a normal complete line, the information should contain
    # extracted_info[0]  # Date
    # extracted_info[1]  # Type
    # extracted_info[2]  # Detail
    # extracted_info[3]  # First number found on the line (should have been "paid out" but isn't). Will be either paid in or paid out value
    # extracted_info[4]  # Second number found on the line if any (should have been "paid in, but isn't"). Should always be the balance in reality
    # extracted_info[5]  # Empty. if first and second number are present, then this is the second

    # so now we need to reorganise the information as such:
    # ei_date =     extracted_info[0]
    # ei_type =     extracted_info[1]
    # ei_detail =   extracted_info[2]
    # ei_paid_out = extracted_info[3] if ei_type != 'CR' else ''
    # ei_paid_in =  extracted_info[3] if ei_type == 'CR' else ''
    # ei_balance =  extracted_info[4]

    lines_with_amt_adjusted_columns: list[dict[str, str]] = []

    for ei in combined_split_lines:
        temp_final_line = {
            "date": ei["date"],  # Date - no change
            "type": ei["type"],  # Type - no change
            "detail": ei["detail"],  # Detail - no change
            "paid out": (
                ei["paid out"] if ei["type"] != "CR" else ""
            ),  # Paid Out (ie not credited)
            "paid in": ei["paid out"] if ei["type"] == "CR" else "",  # Paid In
            "balance": ei["balance"],  # Balance
        }
        lines_with_amt_adjusted_columns.append(temp_final_line)

    return lines_with_amt_adjusted_columns


def include_date_on_every_line(lines_with_amt_adjusted_columns: list[dict[str, str]]) -> list[dict[str, str]]:
    log("Inserting the missing dates")

    previous_date = ""

    for line in lines_with_amt_adjusted_columns:
        if not line["date"]:
            line["date"] = previous_date
        previous_date = line["date"]

    return lines_with_amt_adjusted_columns


def combine_paid_in_and_paid_out(list_with_dates_on_every_line: list[dict[str, str]]) -> list[dict[str, str]]:
    log("Combining the amounts paid in and out")

    for line in list_with_dates_on_every_line:
        if line["paid out"]:
            line["paid out"] = str(0 - float(line["paid out"].replace(",", "")))

        if line["paid in"]:
            line["paid out"] = line["paid in"]
            line["paid in"] = ""

        # Modify the dictionary to
        # change the "paid out" key name into "Amount" and
        # remove the "paid in" column
        line["amount"] = line.pop("paid out")
        line.pop("paid in")

    return list_with_dates_on_every_line


def save_raw_text_to_file(text: list[dict[str, str]], output_file) -> None:
    print("Saving extracted data to txt")

    with open(output_file, "w") as file:
        for lines_list in text:
            for line in lines_list:
                file.write(line + "\n")


def save_extracted_list_to_csv(text: list[dict[str, str]], output_file) -> None:
    print("Saving CSV as tab separated")

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter="\t")

        # Write Header
        writer.writerow(
            [
                "Date",
                "Transaction Type",
                "Transaction Detail",
                "Paid Out",
                "Paid In",
                "Balance",
            ]
        )

        # Write content
        for ll in text:
            writer.writerow(
                [
                    ll["date"],
                    ll["type"],
                    ll["detail"],
                    ll["paid out"],
                    ll["paid in"],
                    ll["balance"],
                ]
            )


def save_list_to_MemoryManagerEx_csv(text: list[dict[str, str]], output_file) -> None:
    print("Saving as tab separated MoneyManagerEx CSV")

    # to import:
    # File > Import > as CSV
    # - Column "date", select "Date"
    # - Column "type", select "Don't Care"
    # - Column "amount", select "Amount"
    # - Column "detail", select "Payee"
    # - Date format: select "DD Mon YY"
    # - CSV delimiter: type "\t" (without the "")
    # - Amount: select "Positive values are deposits"
    # - Decimal Char: select "."
    # - rows to ignore: from start: None, from end: None
    # - then you can save the persent (3rd line from the top)
    #     - give it a memorable name like "from HBSC_UK_Monthly_Statement_pdf_parser"
    #     - This can then be recalled for the next import

    with open(output_file, "w", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter="\t")

        # writer.writerow(["Date", "Transaction Type", "Transaction Detail", "Paid Out", "Paid In", "Balance"])

        for ll in text:
            writer.writerow(
                [
                    ll["date"],
                    ll["type"],
                    ll["detail"],
                    float(ll["amount"].replace(",", "")),
                ]
            )


def save_list_to_qif(text: list[dict[str, str]], output_file) -> None:
    print("Saving data as QIF")

    qif_data: list[str] = ["!Type:Bank"]

    for row in text:
        date = datetime.strptime(row["date"], "%d %b %y").strftime("%d/%m/%y")
        qif_data.extend(
            [
                f"D{date}",
                f"M{row['type']}",  # HSBC Type saved as memo
                f"T{row['amount']}",
                f"P{row['detail']}",
                "^",
            ]
        )

    with open(output_file, "w", newline="") as qif_file:
        for line in qif_data:
            qif_file.write(line + "\n")


def main():

    # if INPUT_FILE == '':
    #     print ('Please modify the value of "INPUT_FILE" in this python file to point to the file you want to process')
    #     print ('A future version of this app might help you point to the file')
    #     exit(1)

    SELECT_FILE = acquire_filename()

    FILE_BASE_PATH = os.path.dirname(SELECT_FILE)
    FILE_BASE_NAME = os.path.basename(SELECT_FILE).split(".")[0]
    # FILE_BASE_EXTENSION = os.path.basename(SELECT_FILE).split('.')[1]

    INPUT_FILE = SELECT_FILE

    FILE_EXTENSION_RAW = ".txt"
    FILE_EXTENSION_CSV = ".csv"
    FILE_EXTENSION_MMX = "-mmx.csv"  # for MemoryManagerEx
    FILE_EXTENSION_QIF = ".qif"
    
    OUTPUT_FILE_RAW = FILE_BASE_PATH + "\\" + FILE_BASE_NAME + FILE_EXTENSION_RAW
    OUTPUT_FILE_CSV = FILE_BASE_PATH + "\\" + FILE_BASE_NAME + FILE_EXTENSION_CSV
    OUTPUT_FILE_MMX = FILE_BASE_PATH + "\\" + FILE_BASE_NAME + FILE_EXTENSION_MMX
    OUTPUT_FILE_QIF = FILE_BASE_PATH + "\\" + FILE_BASE_NAME + FILE_EXTENSION_QIF

    all_lines = load_pdf_pages(INPUT_FILE)
    cleaned_list = cleanout_useless_lines_from_pdf_import(all_lines)

    # To save the raw data into text file, make this True:
    save_raw_file = False
    if save_raw_file:
        save_raw_text_to_file(cleaned_list, OUTPUT_FILE_RAW)

    list_extracted_as_dict = extract_line_info_into_dict(cleaned_list)
    list_with_combined_split_lines = combine_split_lines(list_extracted_as_dict)
    list_with_amount_in_correct_column = fix_amount_column_position(list_with_combined_split_lines)
    list_with_date_in_every_line = include_date_on_every_line(list_with_amount_in_correct_column)

    # To save the data into a CSV with separate column for paid in and paid out, make this True:
    save_base_csv_file = True
    if save_base_csv_file:
        save_extracted_list_to_csv(list_with_date_in_every_line, OUTPUT_FILE_CSV)

    # Dictionary is change here so section separated
    list_with_combined_amounts = combine_paid_in_and_paid_out(list_with_date_in_every_line)

    # Saving a CSV for importing into MemoryManagerEx
    save_list_to_MemoryManagerEx_csv(list_with_combined_amounts, OUTPUT_FILE_MMX)
    
    # Saving QIF file
    save_list_to_qif(list_with_combined_amounts, OUTPUT_FILE_QIF)
    return 0


if __name__ in "__main__":
    main()

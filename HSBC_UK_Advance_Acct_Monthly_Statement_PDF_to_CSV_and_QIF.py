""" Python application to convert HSBC UK Consumer Monthly Statement PDF 
into CSV files for import into Excel or money managers"""

__author__ = "Squizzy"
__copyright__ = "Copyright 2024, Squizzy"
__credits__ = ""
__license__ = "GPL"
__version__ = "1.0"
__maintainer__ = "Squizzy"

import pypdf
import re
import csv
import os
from datetime import datetime
from typing import Callable

# from pprint import pprint

#####
# Constants

INPUT_FOLDER = "Downloaded_PDF"

OUTPUT_FOLDER_GENERIC = "Converted_Files"

OUTPUT_FOLDER_RAW = OUTPUT_FOLDER_GENERIC + "\\RAW"
OUTPUT_EXTENSION_RAW = ".txt"
OUTPUT_FILENAME_RAW_COMBINED = "HSBC_raw_transactions_combined.txt"

OUTPUT_FOLDER_CSV = OUTPUT_FOLDER_GENERIC + "\\CSV"
OUTPUT_EXTENSION_CSV = ".csv"
OUTPUT_FILENAME_CSV_COMBINED = "HSBC_transactions_combined.csv"

OUTPUT_FOLDER_MMX = OUTPUT_FOLDER_GENERIC + "\\MMX_CSV"
OUTPUT_EXTENSION_MMX = "-mmx.csv"
OUTPUT_FILENAME_MMX_COMBINED = "HSBC_transactions_combined.mmx"

OUTPUT_FOLDER_QIF = OUTPUT_FOLDER_GENERIC + "\\QIF"
OUTPUT_EXTENSION_QIF = ".qif"
OUTPUT_FILENAME_QIF_COMBINED = "HSBC_transactions_combined.qif"

SHOW_LOG = True

#####
# Switches
# User controlled - modified by input box
output_generic_csv = True                   # Generate a CSV file of all the transactions                           
output_mmx = False                          # Generate a CSV file of all the transactions, MoneyManagerEx compliant 
output_qif = False                          # Generate a QIF file of all the transactions                           
use_mmx_header = True                       # if False, do not include header in the output CSV for MMX             
combine_all_output_statements = False       # In folder selection mode, generate a file combining all transactions  
cancel = False                              # cancel the execution of the program by the user                       

# Application specific
csv_writer_combined_header_present = False  # In a combined CSV file, do not re-add header every time a new file is added
mmx_writer_combined_header_present = False  # In a combined CSV file, do not re-add header every time a new file is added

# Debug specific
output_raw = False                                  # Generate a raw text file of all the transactions                      
output_spaces_in_csv = False                        # In Generic CSV, include columns with the spacing between details      
file_generation_log_entry_already_displayed = False # if True, the log entry are output to terminal (verbose)


#####
# Regex patterns for the useful line process

# DATE:
# word boundary | 2 digits | space | 2 or 3 chars | space | 2 digits | word boundary
REGEX_date = r"^(?P<date>\b\d{2}\s\w{3,4}\s\d{2}\b){0,10}"

# PRESENTATIONAL SPACING:
# 0 or more spaces
REGEX_space1 = r"(?P<space1>\s{1,28})?"

# TRANSACTION TYPE:
# 2 or 3 upper case letters CR, SO, ... or ))) (supposedly, contactless payment)
# REGEX_type = r'([A-Z\)]{2,3})?'
# One of the choices of ATM, BP, CR, DD, DR, SO, VIS, \\\ - if any needs to be added, they can be separated with OR ( '|' )
REGEX_type = r"(?P<type>ATM|BP|CR|DD|DR|SO|VIS|\)\)\))?"

# PRESENTATIONAL SPACING:
# 0 or more spaces
REGEX_space2 = r"(?P<space2>\s{0,20})"

# TRANSACTION DETAIL:
# Description: word boundary | one or more of a-z, A-Z, /, ., *, - | word boundary | (Optional, repeated 0 or more times: space|word boundary | one or more of a-z, A-Z, /, ., *, - | word boundary | Optional End of String)
REGEX_detail = r"(?P<detail>(?:[a-zA-Z0-9\/\.\*\-\@\:]+(?:\s{0,5}))+)"

# OPTIONAL END OF STRING
# Description: if the line ends right after the "detail" part, the end of the detail might not be caught if details has space in it
# This is no longer a problem if we make the end optional so not even a space is expected after the detail
REGEX_optional_start = r"(?:"


# PRESENTATIONAL SPACING:
# (Optional 0 or more spaces)
# Recorded as its amount of spaces should dictate whether an amount is a paid out or paid in
# If a max size is specified, and the number is way further, the paid_out column will be skipped. 
# Trial and error said 100 appears to works
REGEX_space3 = r"(?P<space3>\s{1,100})"

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
# Again a max size helps allowing the paid_in amount to be reached. 50 selected as the position moves a lot depending on the lines
REGEX_paid_out = r"(?P<paid_out>(?:\d+,)*\d+[\.]?\d{0,2}){0,50}"

# PRESENTATIONAL SPACING:
# (Optional: 0 or more spaces)
# If more than 120 char, then it is probably a paid in amount
# Again the max size helps allowing the paid_in amount to be reached
REGEX_space4 = r"(?P<space4>\s{0,40})"

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_paid_in = r"(?P<paid_in>(?:\d+,)*\d+[\.]?\d{0,2})?"

# PRESENTATIONAL SPACING:
# (Optional: 0 or more spaces)
# Again max size to allow to reach the balance column
REGEX_space5 = r"(?P<space5>\s{0,30})"

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_balance = r"(?P<balance>(?:\d+,)*\d+[\.]?\d{0,2})?"

# OPTIONAL END OF STRING
# Description: if the line ends right after the "detail" part, the end of the detail might not be caught if details has space in it
# This is no longer a problem if we make the end optional so not even a space is expected after the detail
REGEX_optional_end = r")?"

#####
# Combined regex to process a whole line in one go

LINE_DETAILS_EXTRACTION_REGEX = (
      REGEX_date
    + REGEX_space1
    + REGEX_type
    + REGEX_space2
    + REGEX_detail
    + REGEX_optional_start
    + REGEX_space3
    + REGEX_paid_out
    + REGEX_space4
    + REGEX_paid_in
    + REGEX_space5
    + REGEX_balance
    + REGEX_optional_end
)


# def log(func_name: str, mesage: str) -> None:
def log(message: str) -> None:
    if SHOW_LOG:
        logtime = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        print(f"[{logtime}] {message}")

def log_wrapper(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        log(f"-- FUNCTION STARTED: {func_name}")
        result = func(*args, **kwargs)
        log(f"-- FUNCTION ENDED: {func_name}\n")
        return result
    return wrapper

#####
# Preparation steps functions

# open a popup to find and select the file to process
@log_wrapper
def select_input_file_or_folder() -> tuple[str, str]:
    log("Selecting a file or a folder")
    import tkinter as tk
    from tkinter import filedialog
    
    global output_generic_csv
    global output_mmx
    global output_qif
    global combine_all_output_statements
    global use_mmx_header
    
    file_path:str = ""
    file_name:str = ""
    
    def acquire_folder() -> None:
        nonlocal file_path
        nonlocal file_name
        file_path = filedialog.askdirectory()
        file_name = ""
        root.quit()

    def acquire_file() -> None:
        nonlocal file_path
        nonlocal file_name
        file_selected = filedialog.askopenfilename(
            title="select file", initialdir=".", filetypes=[("PDF files", "*.pdf")]
        )
        file_path = os.path.dirname(file_selected)
        file_name = os.path.basename(file_selected)
        root.quit()


    root = tk.Tk()
    root.title("Select a file or a folder")
    
    # chk_output_raw = tk.IntVar()
    chk_output_csv = tk.IntVar()
    chk_output_mmx = tk.IntVar()
    chk_output_qif = tk.IntVar()
    chk_output_all_statements_combined = tk.IntVar()
    chk_use_mmx_headers = tk.IntVar()
    
    # chk_output_raw.set(output_raw)
    chk_output_csv.set(output_generic_csv)
    chk_output_mmx.set(output_mmx)
    chk_output_qif.set(output_qif)
    chk_output_all_statements_combined.set(combine_all_output_statements)
    chk_use_mmx_headers.set(use_mmx_header)

    frm_output_options = tk.Frame(root, relief=tk.RIDGE, borderwidth=1)
    tk.Checkbutton(frm_output_options, text="Create CSV - Generic", variable=chk_output_csv).grid(row=1, column=0, sticky=tk.W)
    tk.Checkbutton(frm_output_options, text="Create CSV - MoneyManagerEx specific", variable=chk_output_mmx).grid(row=2, column=0, sticky=tk.W)
    tk.Checkbutton(frm_output_options, text="Include headers in MMX CSV", variable=chk_use_mmx_headers).grid(row=2, column=1, sticky=tk.W)
    tk.Checkbutton(frm_output_options, text="Create QIF", variable=chk_output_qif).grid(row=3, column=0, sticky=tk.W)
    frm_output_options.pack(fill=tk.X, padx=5, pady=5, expand=True)
    
    frm_actions = tk.Frame(root, relief=tk.RIDGE, borderwidth=1)
    _ = tk.Label(frm_actions, text="Select a file or a folder").grid(row=0, column=0, columnspan=2, sticky=tk.W)
    _ = tk.Button(frm_actions, text="Select file", command=acquire_file).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
    _ = tk.Button(frm_actions, text="Select folder", command=acquire_folder).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
    tk.Checkbutton(frm_actions, text="With folder selection,\ncreate files combining all statements", variable=chk_output_all_statements_combined).grid(row=2, column=1, columnspan=2, sticky=tk.W)
    _ = tk.Button(frm_actions, text="Cancel", command=root.quit).grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.EW)
    frm_actions.pack(fill=tk.X, padx=5, pady=5, expand=True)
    
    root.mainloop()
    
    # Button has been clicked, window won't be used any more so ready the user selections
    output_generic_csv = chk_output_csv.get() == 1 
    output_mmx = chk_output_mmx.get() == 1 
    output_qif = chk_output_qif.get() == 1
    combine_all_output_statements = chk_output_all_statements_combined.get() == 1
    use_mmx_header = chk_use_mmx_headers.get() == 1
    
    return file_path, file_name

# check if user cancelled the process
@log_wrapper
def user_cancelled(selected_path: str) -> bool:
    log("Checking if user cancelled")
    if not selected_path:
        log("User has cancelled")
        return True
    return False
        
# create output folders
@log_wrapper
def create_output_folders() -> None:
    log("Creating required output folders")
    
    if not os.path.exists(OUTPUT_FOLDER_GENERIC):
        os.makedirs(OUTPUT_FOLDER_GENERIC)
        
    if not os.path.exists(OUTPUT_FOLDER_RAW) and output_raw:
        os.makedirs(OUTPUT_FOLDER_RAW)
        
    if not os.path.exists(OUTPUT_FOLDER_CSV) and output_generic_csv:
        os.makedirs(OUTPUT_FOLDER_CSV)
        
    if not os.path.exists(OUTPUT_FOLDER_MMX) and output_mmx:
        os.makedirs(OUTPUT_FOLDER_MMX)
        
    if not os.path.exists(OUTPUT_FOLDER_QIF) and output_qif:
        os.makedirs(OUTPUT_FOLDER_QIF)


#####
# Extraction steps functions
# load PDF pages into a list (of pages) containing a list of (pages lines) strings
@log_wrapper
def load_lines_from_all_pages_from_PDF(PDF_filename: str) -> list[list[str]]:
    log("Loading PDF pages into a list of strings")
    PDF_pages_lines_list: list[list[str]] = []

    with open(PDF_filename, "rb") as file:
        PDF_file = pypdf.PdfReader(file)
        PDF_pages = PDF_file.pages

        for PDF_page in PDF_pages:
            PDF_lines: str = PDF_page.extract_text(
                extraction_mode="layout",
                layout_mode_space_vertically=False,
                layout_mode_scale_weight=0.98,
            )
            PDF_pages_lines_list.append(PDF_lines.split("\n"))

    return PDF_pages_lines_list

# Separate the lines containing transaction information from the non-transaction lines
@log_wrapper
def extract_transaction_specific_lines_from_pdf_import(all_lines_from_pdf: list[list[str]],) -> tuple[list[list[str]], list[list[str]]]:
    log("Separating the lines with transaction information from the non-transaction lines")
    transaction_lines_list: list[list[str]] = []
    non_transaction_lines_list: list[list[str]] = []

    for PDF_page in all_lines_from_pdf:
        transaction_lines = []
        transaction_section = False # Assuming that the first line of all lines is not a transaction yet
        non_transaction_lines = []

        for PDF_line in PDF_page:
            # If the below text is discovered in a line, then we are at the END of a section containing transaction lines
            if "BALANCE CARRIED FORWARD" in PDF_line:
                transaction_section = False
            
            # If in a transaction section, add the line to the transaction list
            if transaction_section:
                transaction_lines.append(PDF_line)
            # If not in a transaction section, record the line into the non-transaction list
            else:
                non_transaction_lines.append(PDF_line)
                
            # If the below text is discovered in a line, then we are at the START of a transaction section
            if "BALANCE BROUGHT FORWARD" in PDF_line:
                transaction_section = True
        
        # Add the page's transactions line to the transaction pages list
        transaction_lines_list.append(transaction_lines)
        # and the non-transaction lines to the non-transaction pages list
        non_transaction_lines_list.append(non_transaction_lines)
        
        # Could be about to start a new page so reset the transaction section indicator
        transaction_section = False

    return transaction_lines_list, non_transaction_lines_list

# extract and categorise the relevant info from the lines
@log_wrapper
def convert_transaction_details_per_line_into_a_dictionary(all_transaction_lines_from_PDF: list[list[str]]) -> list[dict[str, str]]:
    log("Extracting each line into a dictionary")

    PDF_transaction_lines_detailed: list[dict[str, str]] = []

    # Extract the relevant info from the lines into a list of lists of strings
    for PDF_Page in all_transaction_lines_from_PDF:
        
        for PDF_transaction_line in PDF_Page:
            
            # The crucial regex to extract the relevant info from the line
            # Hopefully mostly working now
            for match in re.finditer(LINE_DETAILS_EXTRACTION_REGEX, PDF_transaction_line):
                
                # extract the dictionary from the regex search
                transaction_details = match.groupdict()
            
                # Put the transaction details in an dictionary
                transaction_details_dictionary = {
                    'date': transaction_details['date'],
                    'space1': transaction_details['space1'],
                    'type': transaction_details['type'],
                    'space2': transaction_details['space2'],
                    'detail': transaction_details['detail'],
                    'space3': transaction_details['space3'],
                    'paid out': transaction_details['paid_out'],
                    'space4': transaction_details['space4'],
                    'paid in': transaction_details['paid_in'],
                    'space5': transaction_details['space5'],
                    'balance': transaction_details['balance'],
                    }

                # Store the dictionary in the list
                PDF_transaction_lines_detailed.append(transaction_details_dictionary)

    return PDF_transaction_lines_detailed

# Some lines are split over two or more lines. Combine them into one
@log_wrapper
def recombine_transaction_info_split_over_several_lines(PDF_transactions_extracted_and_converted: list[dict[str, str]]) -> list[dict[str, str]]:
    log("Combining lines split over two lines")
    # Sometimes HSBC PDF present a statement over two lines. the amounts are on the second one.
    # For a decent output, we need to combine these two lines into one.
    # It seems the difference is that one line has the transaction type and the begining of the transaction detail.
    # The second line has the remainder of the transaction detail, and the amount(s)
    # Thankfully there is no line with a transaction 'type' and 'balance' without an amount

    PDF_transactions_with_split_transaction_info_recombined: list[dict[str, str]] = []
    
    
    for i in range(len(PDF_transactions_extracted_and_converted) - 1):

        # 1) If the transation 'type' and the first 'amount' are found, the line is complete, copy over
        if PDF_transactions_extracted_and_converted[i]["type"] and (
                PDF_transactions_extracted_and_converted[i]["paid out"] 
                or PDF_transactions_extracted_and_converted[i]["paid in"]):
            PDF_transactions_with_split_transaction_info_recombined.append(PDF_transactions_extracted_and_converted[i])

        # 2) If the transaction type is found but no amount is found on the line,
        # confirm that the next line has no transaction type but an amount.
        # In this case, combine
        elif PDF_transactions_extracted_and_converted[i]["type"] and (
                        not PDF_transactions_extracted_and_converted[i]["paid out"] and 
                        not PDF_transactions_extracted_and_converted[i]["paid in"]):
            temp_transaction_detail = PDF_transactions_extracted_and_converted[i]["detail"]
            j = 1
            
            # Check if the next line has no transaction type and no amount
            # in this case, combine the details
            # otherwise, carry on
            while not PDF_transactions_extracted_and_converted[i + j]["type"] and not (
                            PDF_transactions_extracted_and_converted[i + j]["paid out"] or 
                            PDF_transactions_extracted_and_converted[i + j]["paid in"]):
                temp_transaction_detail = temp_transaction_detail + " " + PDF_transactions_extracted_and_converted[i + j]["detail"]
                j = j + 1
                if i == 33 and j == 2:
                    break
            
            # if the current studied line i+j had either a type or a paid out, it reached here.
            # Normally, it should be a paid out, meaning it is the end of the combining
            # So combine this detail
            if not PDF_transactions_extracted_and_converted[i + j]["type"] and (
                                PDF_transactions_extracted_and_converted[i + j]["paid out"] or 
                                PDF_transactions_extracted_and_converted[i + j]["paid in"]):
                temp_transaction_detail = temp_transaction_detail + " " + PDF_transactions_extracted_and_converted[i + j]["detail"]

                # Recreate the transaction
                transaction_line_with_combined_detail = {
                    "date": PDF_transactions_extracted_and_converted[i]["date"],  # date from current line
                    "space1": PDF_transactions_extracted_and_converted[i]["space1"],
                    "type": PDF_transactions_extracted_and_converted[i]["type"],  # type from current line
                    "space2": PDF_transactions_extracted_and_converted[i]["space2"],
                    "detail": temp_transaction_detail,
                    "space3": PDF_transactions_extracted_and_converted[i+j]["space3"],
                    "paid out": PDF_transactions_extracted_and_converted[i + j]["paid out"],  # first amount from the next line
                    "space4": PDF_transactions_extracted_and_converted[i + j]["space4"],
                    "paid in": PDF_transactions_extracted_and_converted[i + j]["paid in"],  # second amount from the next line
                    "space5": PDF_transactions_extracted_and_converted[i + j]["space5"],
                    "balance": PDF_transactions_extracted_and_converted[i + j]["balance"],  # third amount from the next line - should be empty
                }
                PDF_transactions_with_split_transaction_info_recombined.append(transaction_line_with_combined_detail)

        # If we reach here, we're on the next line that has been processed in the second round
        # so we have no processing to do
        else:
            continue
        
    return PDF_transactions_with_split_transaction_info_recombined

# The amount is currently always in the paid_out column although always positive. Move the credit ones to the paid_in column
# Hurray - now obsolete as the REGEX seems to about work now
@log_wrapper
def place_amount_in_the_credit_or_debit_column(PDF_transactions_with_recombined_lines: list[dict[str, str]]) -> list[dict[str, str]]:
   
    """Correcting the positioning of the amount, 
        depending on whether it is a Credit (paid in) or a Debit (paid out), 
        and the balance"""
    log("Correcting payment column (credit or debit)")

    PDF_transactions_with_amount_in_correct_column: list[dict[str, str]] = []

    for PDF_transaction_line in PDF_transactions_with_recombined_lines:
        
        PDF_transaction_line_with_amount_in_correct_column = {
            "date": PDF_transaction_line["date"],
            "space1": PDF_transaction_line["space1"],
            "type": PDF_transaction_line["type"],
            "space2": PDF_transaction_line["space2"],
            "detail": PDF_transaction_line["detail"], 
            "space3": PDF_transaction_line["space3"], 
            
            "paid out": 
                # VIS can be either paid in or paid out
                # if 103 spaces before the VIS value, then it is a paid out
                PDF_transaction_line["paid out"] if PDF_transaction_line["type"] == "VIS" 
                                                 and PDF_transaction_line["paid out"] 
                                                 and len(PDF_transaction_line["space3"]) < 103
                    # but if more than 103 spaces, then it is a paid in
                    else "" if PDF_transaction_line["type"] == "VIS" 
                            and PDF_transaction_line["paid out"] 
                            and len(PDF_transaction_line["space3"]) >= 103
                        # all those not CR are paid out
                        else PDF_transaction_line["paid out"] if PDF_transaction_line["type"] != "CR" 
                            # CR will always be paid in, so nothing in this case
                            else "", 
                            
            "space4": PDF_transaction_line["space4"], 
            
            "paid in": 
                # VIS can be paid in if more than 103 spaces before the VIS value
                PDF_transaction_line["paid out"] if PDF_transaction_line["type"] == "VIS" 
                                                 and PDF_transaction_line["paid out"] 
                                                 and len(PDF_transaction_line["space3"]) >= 103
                    # CR are paid in
                    else PDF_transaction_line["paid out"] if PDF_transaction_line["type"] == "CR" 
                        # Otherwise, it was a paid out, so nothing
                        else "",
                        
            "space5": PDF_transaction_line["space5"],
            "balance": PDF_transaction_line["balance"], 
        }
        
        PDF_transactions_with_amount_in_correct_column.append(PDF_transaction_line_with_amount_in_correct_column)

    return PDF_transactions_with_amount_in_correct_column

# Date for all transactions that day is only provided once in the PDF. Associates each transaction with its happening date
@log_wrapper
def set_correct_date_for_each_transaction(PDF_transactions_with_amount_in_correct_column: list[dict[str, str]]) -> list[dict[str, str]]:
    # This assumes that the transaction lines in the dictionary will be read in the order from the PDF
    # This should work fine with python 3.10+
    log("Inserting the missing dates")

    previous_transaction_date = ""

    for transaction_line in PDF_transactions_with_amount_in_correct_column:
        # If no date, use the previous_transaction_date date. 
        # The first transaction will always have a date so no need to do anything to it
        # This is processing the dictionary provided, not creating a new one
        if not transaction_line["date"]:
            transaction_line["date"] = previous_transaction_date
        
        # set the previous date to the current line's. Either an old one repeated, or a new one if it already had a date
        previous_transaction_date = transaction_line["date"]

    return PDF_transactions_with_amount_in_correct_column

# QIF and memory manager ex requires that transaction are in the same column with a +/-. do this.
@log_wrapper
def change_amounts_to_one_column_with_pos_or_neg_values(list_with_dates_on_every_line: list[dict[str, str]]) -> list[dict[str, str]]:
    log("Combining the amounts paid in and out")

    for line in list_with_dates_on_every_line:
        # If there is an amount in "paid_out colum, then make it to negative"
        if line["paid out"]:
            line["paid out"] = str(0 - float(line["paid out"].replace(",", "")))

        # If there is an amount in "paid_in column, then move it to "paid out" column and nullify the paid_in
        if line["paid in"]:
            line["paid out"] = line["paid in"]
            line["paid in"] = ""

        # Modify the dictionary to
        # change the "paid out" key name into "Amount" and
        # remove the "paid in" column
        line["amount"] = line.pop("paid out")
        line.pop("paid in")

    return list_with_dates_on_every_line


#####
# PDF to Data conversion
@log_wrapper
def get_raw_text_transactions_from_PDF(PDF_file: str) -> list[list[str]]:
    
    log("Extracting data from PDF into a list of text lines in a list of pages")
    
    #step1:
    step1: list[list[str]] = load_lines_from_all_pages_from_PDF(PDF_file)
    
    # step2:
    PDF_transactions_in_raw_text_format: list[list[str]]
    PDF_transactions_in_raw_text_format, _ = extract_transaction_specific_lines_from_pdf_import(step1) # Ignore the second argument with "_" as it is the non-transaction lines
    
    return PDF_transactions_in_raw_text_format

@log_wrapper
def get_usable_dictionary_from_PDF(PDF_transactions_raw_text_pages: list[list[str]]) -> list[dict[str, str]]:
    # follows on from get_raw_text_transactions_from_PDF
    
    log("Extracting data from PDF into a dict")

    step3 = convert_transaction_details_per_line_into_a_dictionary(PDF_transactions_raw_text_pages)
    step4 = recombine_transaction_info_split_over_several_lines(step3)
    # step5 = place_amount_in_the_credit_or_debit_column(step4)
    # step6
    PDF_transactions_in_usable_dictionary_format = set_correct_date_for_each_transaction(step4)

    return PDF_transactions_in_usable_dictionary_format


#####
# File saving functions
# Save a list of dict[str|str] to a TXT file
@log_wrapper
def Save_PDF_transactions_in_raw_TXT_format_file(PDF_transactions_raw_text_pages: list[list[str]], output_file) -> None:
    log("Saving data to raw TXT file")

    # Write the individual text file
    with open(output_file, "w") as file:
        for PDF_transaction_row_text_page in PDF_transactions_raw_text_pages:
            for PDF_transaction_row_text in PDF_transaction_row_text_page:
                file.write(PDF_transaction_row_text + "\n")
    
    # Write the combined text file            
    if combine_all_output_statements:
        output_raw_combined_filename = OUTPUT_FOLDER_RAW + "\\" + OUTPUT_FILENAME_RAW_COMBINED
        with open(output_raw_combined_filename, "a") as file:
            for PDF_transaction_row_text_page in PDF_transactions_raw_text_pages:
                for PDF_transaction_row_text in PDF_transaction_row_text_page:
                    file.write(PDF_transaction_row_text + "\n")

# Save a list of dict[str|str] to a CSV file
@log_wrapper
def save_PDF_transactions_in_generic_CSV_format_file(PDF_transactions_in_dict_pages: list[dict[str, str]], output_file) -> None:
    log("Saving data to generic CSV file as tab separated")
    
    global csv_writer_combined_header_present

    with open(output_file, "w", newline="") as csvfile:
        csv_writer = csv.writer(csvfile, delimiter="\t")
        
        if output_spaces_in_csv: # should be mainly be for debugging
                        
            # Write Header for generic CSV file
            csv_writer.writerow(
                [
                    "Date",
                    "space1",
                    "Transaction Type",
                    "space2",
                    "Transaction Detail",
                    "space3",
                    "Paid Out",
                    "space4",
                    "Paid In",
                    "space5",
                    "Balance",
                ]
            )

            # Write data for generic CSV file
            for transaction in PDF_transactions_in_dict_pages:               
                csv_writer.writerow(
                [
                    transaction["date"],
                    transaction["space1"],
                    transaction["type"],
                    transaction["space2"],
                    transaction["detail"],
                    transaction["space3"],
                    transaction["paid out"],
                    transaction["space4"],
                    transaction["paid in"],
                    transaction["space5"],
                    transaction["balance"],
                ]
            )

        else:
            # Write Header for generic CSV file
            csv_writer.writerow(
                [
                    "Date",
                    "Transaction Type",
                    "Transaction Detail",
                    "Paid Out",
                    "Paid In",
                    "Balance",
                ]
            )
            
            # Write data for generic CSV file
            for transaction in PDF_transactions_in_dict_pages:
                csv_writer.writerow(
                        [
                            transaction["date"],
                            transaction["type"],
                            transaction["detail"],
                            transaction["paid out"],
                            transaction["paid in"],
                            transaction["balance"],
                        ]
                    )


        if combine_all_output_statements:
            output_csv_combined_filename = OUTPUT_FOLDER_CSV + "\\" + OUTPUT_FILENAME_CSV_COMBINED
            with open(output_csv_combined_filename, "a", newline="") as csvfile_combined:
                csv_writer_combined = csv.writer(csvfile_combined, delimiter="\t")


                if output_spaces_in_csv: # should be mainly be for debugging
                
                    # Write header for combined CSV file if new file
                    if not csv_writer_combined_header_present:
                        csv_writer_combined.writerow(
                            [
                                "Date",
                                "space1",
                                "Transaction Type",
                                "space2",
                                "Transaction Detail",
                                "space3",
                                "Paid Out",
                                "space4",
                                "Paid In",
                                "space5",
                                "Balance",
                            ]
                        )
                        csv_writer_combined_header_present = True
                    
                    # Write data for combined CSV file
                    for transaction in PDF_transactions_in_dict_pages:
                        csv_writer_combined.writerow(
                                [
                                    transaction["date"],
                                    transaction["space1"],
                                    transaction["type"],
                                    transaction["space2"],
                                    transaction["detail"],
                                    transaction["space3"],
                                    transaction["paid out"],
                                    transaction["space4"],
                                    transaction["paid in"],
                                    transaction["space5"],
                                    transaction["balance"],
                                ]
                            )
                    
                else:
                    # Write header for combined CSV file
                    if not csv_writer_combined_header_present:
                        csv_writer_combined.writerow(
                            [
                                "Date",
                                "Transaction Type",
                                "Transaction Detail",
                                "Paid Out",
                                "Paid In",
                                "Balance",
                            ]
                        )
                        csv_writer_combined_header_present = True
                    
                    # Write data for combined CSV file
                    for transaction in PDF_transactions_in_dict_pages:
                        csv_writer_combined.writerow(
                            [
                                transaction["date"],
                                transaction["type"],
                                transaction["detail"],
                                transaction["paid out"],
                                transaction["paid in"],
                                transaction["balance"],
                            ]
                        )
                    
# Save PDF transactions in MoneyManagerE CSV format
@log_wrapper
def save_PDF_transactions_in_mmx_CSV_format_file(PDF_transactions_in_dict_form_with_one_amounts_column: list[dict[str, str]], output_file) -> None:
    log("Saving MoneyManagerEx CSV file as tab separated")

    # to import:
    # File > Import > as CSV
    # - Column "Date", select "Date"
    # - Column "type", select "Notes"
    # - Column "Amount", select "Amount"
    # - Column "Payee", select "Payee"
    #
    # Other MMX parameters to adjust
    # - Date format: select "DD Mon YY"
    # - CSV delimiter: type "\t" (without the "")
    # - Amount: select "Positive values are deposits"
    # - Decimal Char: select "."
    # - rows to ignore: from start: 1, from end: 0 (to remove the header)
    # - then you can save the preset (3rd line from the top)
    #     - give it a memorable name like "from HSBC_UK_Advance_Acct_Monthly_Statement_PDF_to_CSV_and_QIF"
    #     - This can then be recalled for the next import

    global mmx_writer_combined_header_present

    with open(output_file, "w", newline="") as mmxfile:
        mmx_writer = csv.writer(mmxfile, delimiter="\t")

        # Write Header to MemoryManagerEx CSV file
        if use_mmx_header:
            mmx_writer.writerow(
                [
                    "Date",
                    "Notes",
                    "Payee",
                    "Amount",
                ]
            )

        # Write transactions to MemoryManagerEx CSV file
        for transaction in PDF_transactions_in_dict_form_with_one_amounts_column:
            mmx_writer.writerow(
                [
                    transaction["date"],
                    transaction["type"],
                    transaction["detail"],
                    float(transaction["amount"].replace(",", "")),
                ]
            )

        if combine_all_output_statements:
            output_mmx_combined_filename = OUTPUT_FOLDER_MMX + "\\" + OUTPUT_FILENAME_MMX_COMBINED
            with open(output_mmx_combined_filename, "a", newline="") as mmxfile_combined:
                mmx_writer_combined = csv.writer(mmxfile_combined, delimiter="\t")

                # Write Header for MemoryManagerEx CSV combined file, if new
                if use_mmx_header:
                    if not mmx_writer_combined_header_present:
                        mmx_writer_combined.writerow(
                            [
                                "Date",
                                "Notes",
                                "Payee",
                                "Amount",
                            ]
                        )
                        mmx_writer_combined_header_present = True

                # Write transactions to MemoryManagerEx CSV combined file
                for transaction in PDF_transactions_in_dict_form_with_one_amounts_column:
                    mmx_writer_combined.writerow(
                        [
                            transaction["date"],
                            transaction["type"],
                            transaction["detail"],
                            float(transaction["amount"].replace(",", "")),
                        ]
                    )

# Save PDF transactions in QIF format
@log_wrapper
def save_PDF_transactions_in_QIF_format_file(PDF_transactions_in_dict_form_with_one_amounts_column: list[dict[str, str]], output_file) -> None:
    log("Saving data to QIF file")

    qif_data: list[str] = ["!Type:Bank"]

    for transaction in PDF_transactions_in_dict_form_with_one_amounts_column:
        # Transform the date to the required format for QIF
        date = datetime.strptime(transaction["date"], "%d %b %y").strftime("%d/%m/%y")
        
        qif_data.extend(
            [
                f"D{date}",
                f"M{transaction['type']}",  # HSBC Type saved as memo
                f"T{transaction['amount']}",
                f"P{transaction['detail']}",
                "^",                            
            ]
        )

    with open(output_file, "w", newline="") as qif_file:
        # QIF requires one information per line
        for line in qif_data:
            qif_file.write(line + "\n")
            
        if combine_all_output_statements:
            output_qif_combined_filename = OUTPUT_FOLDER_QIF + "\\" + OUTPUT_FILENAME_QIF_COMBINED
            with open(output_qif_combined_filename, "a", newline="") as qif_file_combined:
                for line in qif_data:
                    qif_file_combined.write(line + "\n")


#####
# File generation functions
# Extract info and generate files from individual PDF
@log_wrapper
def generate_requested_files_from_PDF(SelectedPath: str, SelectedFile: str) -> None:
    
    # The global variable will be modified so we must allow the function to do this
    global file_generation_log_entry_already_displayed
    
    output_types = "RAW" if output_raw else ""
    output_types += "CSV" if output_generic_csv and not output_types else ", CSV" if output_generic_csv and output_types else ""
    output_types += "MMX" if output_mmx and not output_types else ", MMX" if output_mmx and output_types else ""
    output_types += "QIF" if output_qif and not output_types else ", QIF" if output_qif and output_types else ""
    
    if not combine_all_output_statements and not file_generation_log_entry_already_displayed:
        log("\033[41m" + f"Extracting info and generating requested {output_types} files from PDF" + "\033[0m")
        
    elif not file_generation_log_entry_already_displayed:
        log("\033[41m" + f"Generating requested {output_types} and combined files from PDF" + "\033[0m")
        file_generation_log_entry_already_displayed = True
        
    else:
        ... #display no log or it would be overly verbose

    # Identify the source PDF file
    PDF_file = SelectedPath + "\\" + SelectedFile
    
    # Extract the base name to use with the output requested
    BASE_FILENAME = os.path.basename(SelectedFile).split(".")[0]
    
    
    # Get the data in raw text format
    PDF_transactions_in_text_raw_format = get_raw_text_transactions_from_PDF(PDF_file)
    
    # if opted to save the raw data (generally for debugging), do it
    if output_raw:
        output_raw_filename = OUTPUT_FOLDER_RAW + "\\" + BASE_FILENAME + OUTPUT_EXTENSION_RAW
        Save_PDF_transactions_in_raw_TXT_format_file(PDF_transactions_in_text_raw_format, output_raw_filename)
    
    
    # If more than raw requested, adjust the PDF transactions in a dictionary usable for generating the CSV and QIF files
    if output_generic_csv or output_mmx or output_qif:
        PDF_transactions_in_dictionary_format = get_usable_dictionary_from_PDF(PDF_transactions_in_text_raw_format)
    
    if output_generic_csv:
        output_generic_csv_filename = OUTPUT_FOLDER_CSV + "\\" + BASE_FILENAME + OUTPUT_EXTENSION_CSV
        save_PDF_transactions_in_generic_CSV_format_file(PDF_transactions_in_dictionary_format, output_generic_csv_filename)
    
    
    # If mmx CSV or QIF requested, adjust amounts so that they are pos/neg in one column instead of one col for in and one for out
    if output_mmx or output_qif:
        PDF_transactions_in_dictionary_format_with_one_amounts_column = change_amounts_to_one_column_with_pos_or_neg_values(PDF_transactions_in_dictionary_format)
    
    if output_mmx:
        output_mmx_filename = OUTPUT_FOLDER_MMX + "\\" + BASE_FILENAME + OUTPUT_EXTENSION_MMX
        save_PDF_transactions_in_mmx_CSV_format_file(PDF_transactions_in_dictionary_format_with_one_amounts_column, output_mmx_filename)
    
    if output_qif:
        output_qif_filename = OUTPUT_FOLDER_QIF + "\\" + BASE_FILENAME + OUTPUT_EXTENSION_QIF
        save_PDF_transactions_in_QIF_format_file(PDF_transactions_in_dictionary_format_with_one_amounts_column, output_qif_filename)

        

def main() -> int:

    # Get the file/folder selection with a dialog window
    SelectedPath, SelectedFile = select_input_file_or_folder()

    # Check if the user cancelled
    if user_cancelled(SelectedPath):
        return 0
    
    # Present confirmation of the selection:
    log(f"Selected file: {SelectedPath}/{SelectedFile}.pdf" if SelectedFile else f"Selected path: {SelectedPath}")

    # Create the required output folders
    create_output_folders()
    
    
    # if a specific file had been selected
    if SelectedFile:
        generate_requested_files_from_PDF(SelectedPath, SelectedFile)

        return 0

    # if a folder had been selected
    else:
        # identify all the pdf under SelectedPath
        # hopefully only the proper HSBC monthly statements PDF are present or the app will crash
        pdf_files = [f for f in os.listdir(SelectedPath) if f.endswith(".pdf")]
        
        # if the combined file already exists, and is about to be regenerated, delete the old one
        if combine_all_output_statements:
            if output_generic_csv:
                csv_combined = OUTPUT_FOLDER_CSV + "\\" + OUTPUT_FILENAME_CSV_COMBINED
                if os.path.exists(csv_combined):
                    os.remove(csv_combined)
                    
            if output_mmx:
                mmx_combined = OUTPUT_FOLDER_MMX + "\\" + OUTPUT_FILENAME_MMX_COMBINED
                if os.path.exists(mmx_combined):
                    os.remove(mmx_combined)
        
            if output_qif:      
                qif_combined = OUTPUT_FOLDER_QIF + "\\" + OUTPUT_FILENAME_QIF_COMBINED
                if os.path.exists(qif_combined):
                    os.remove(qif_combined)
                
        for pdf_file in pdf_files:
            generate_requested_files_from_PDF(SelectedPath, pdf_file)
        
        return 0


if __name__ in "__main__":
    main()

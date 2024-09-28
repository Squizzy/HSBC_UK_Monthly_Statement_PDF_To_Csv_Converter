""" Python application to convert HSBC UK Consumer Monthly Statement PDF into CSV files for import into Excel or money managers"""
__author__ = "Squizzy"
__copyright__ = "Copyright 2024, Squizzy"
__credits__ = ""
__license__ = "GPL"
__version__ = "0.1"
__maintainer__ = "Squizzy"

import pypdf
import re
import csv
# from pprint import pprint

# Modify INPUT_FILE below to point to the PDF you want to process. 
# for example, if the file is called file.pdf in the same folder as this .py file, use :  INPUT_FILE = 'file.pdf
INPUT_FILE = ''

# This is the raw data output, it was mostly useful for development
OUTPUT_FILE_RAW = 'output.txt'

# This is the filenme that is created from the PDF.
# This filename cane be changed if desired, of course.
# In Excel, the file can be imported by:
#   - Create a blank xls sheet
#   - Go to Data tab, then select "from text". Find the output.cvs file that this file has created.
#   - On the window that opens, select 'Delimited' and also add a tick to 'My data has headers' Click Next
#   - Under Delimiters, select Tab, click Next
#   - Under Data Column Format for the first column, it is possible to select "Date". Click Finish.
#   - select OK
OUTPUT_FILE_CVS = 'output.csv'


# DATE: 
# word boundary | 2 digits | space | 2 or 3 chars | space | 2 digits | word boundary
REGEX_date = r'^(\b\d{2}\s\w{3,4}\s\d{2}\b)?'  

# PRESENTATIONAL SPACING: 
# 0 or more spaces
REGEX_space1 = r'(?:\s*)'

# TRANSACTION TYPE: 
# 2 or 3 upper case letters CR, SO, ... or ))) (supposedly, contactless payment)
REGEX_type = r'([A-Z\)]{2,3})?'  
# One of the choices of DD, CD, SO, VIS, BP, ATM, \\\ - if any needs to be added, they can be separated with OR ( '|' )
REGEX_type = r'(?:\s(DD|\)\)\)|CR|SO|VIS|BP|ATM)\s)?'

# PRESENTATIONAL SPACING: 
# 0 or more spaces
REGEX_space2 = r'(?:\s+)'

# TRANSACTION DETAIL: 
# word boundary | one or more of a-z, A-Z, /, ., *, - | word boundary | (Optional, repeated 0 or more times: space|word boundary | one or more of a-z, A-Z, /, ., *, - | word boundary | Optional End of String)
REGEX_detail = r'(\b[a-zA-Z0-9\/\.\*\-\@\:]+\b(?:\s{1,5}\b[a-zA-Z0-9\/\.\*\-\@\:]+\b)*)'

# PRESENTATIONAL SPACING: 
# (Optional: 0 or more spaces)
REGEX_space3 = r'(?:\s+)?'

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_paid_out = r'((?:\d+,)?\d+[\.]?\d*)?'

# PRESENTATIONAL SPACING: 
# (Optional: 0 or more spaces)
REGEX_space4 = r'(?:\s*)?'

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_paid_in = r'((?:\d+,)?\d+[\.]?\d*)?'

# PRESENTATIONAL SPACING: 
# (Optional: 0 or more spaces)
REGEX_space5 = r'(?:\s*)?'

# FIRST NUMBER ENCOUNTERED (can't get PAID_OUT as position on the line is not guaranteed:
# (Optional: One or more digit followed by a comma) | One or more digits | (optional: full stop) | 0 or more digits - the whole thing happening 0 or once only
REGEX_balance = r'((?:\d+,)?\d+[\.]?\d*)?'


LINE_DETAILS_EXTRACTION_REGEX = REGEX_date + REGEX_space1 + REGEX_type + REGEX_space2 + REGEX_detail + REGEX_space3 + REGEX_paid_out + REGEX_space4 + REGEX_paid_in + REGEX_space5 + REGEX_balance


def load_pdf_pages(input_file) -> list[list[str]]:
    print("Loading PDF")
    lines_list:list[list[str]] = []
    
    with open(input_file, 'rb') as file:
        pdf_file = pypdf.PdfReader(file)
        pages = pdf_file.pages
        
        for page in pages:
            lines: str = page.extract_text(extraction_mode="layout", layout_mode_space_vertically=False, layout_mode_scale_weight=0.98)
            lines_list.append(lines.split("\n"))
            
    return lines_list        


def cleanup_useful_lines(all_lines: list[list[str]]) -> list[list[str]]:
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

def extract_line_info_into_dict(all_lines) -> list[list[str]]:
    extracted_lines: list[list[str]] = []
    
    # Extract the relevant info from the lines into a list of lists of strings
    for lines_list in all_lines:
        for line in lines_list:
            extracted_info = re.findall(LINE_DETAILS_EXTRACTION_REGEX, line)[0]
            ei = [
                extracted_info[0],
                extracted_info[1],
                extracted_info[2],
                extracted_info[3],
                extracted_info[4],
                extracted_info[5],
                ]
            extracted_lines.append(ei)
            
    # Sometimes HSBC PDF present a statement over two lines. the amounts are on the second one.
    # For a decent output, we need to combine these two lines into one.
    # It seems the difference is that one line has the transaction type and the begining of the transaction detail.
    # The second line has the remainder of the transaction detail, and the amount(s)
    
    combined_extracted_lines = []
    for i in range(len(extracted_lines) - 1):
        
        # 1) If the transation type and the first amount are found, the line is complete, copy over
        if extracted_lines[i][1] and extracted_lines[i][3]:
            combined_extracted_lines.append(extracted_lines[i])
            
        # 2) If the transaction type is found but no amount is found, 
        # confirm that the next line has no transaction type but an amount.
        # In this case, combine
        elif extracted_lines[i][1] and not extracted_lines[i][3]:
            if not extracted_lines[i+1][1] and extracted_lines[i+1][3]:
                combined_line = [
                    extracted_lines[i][0], # date from current line
                    extracted_lines[i][1], # type from current line
                    extracted_lines[i][2] + " " + extracted_lines[i+1][2], # detail from current and next lines
                    extracted_lines[i+1][3], # first amount from the next line
                    extracted_lines[i+1][4], # second amount from the next line
                    extracted_lines[i+1][5]  # third amount from the next line - should be empty
                    ]
                combined_extracted_lines.append(combined_line)
                
        # If we reach here, we're on the next line that has been processed in the second round 
        # so we have no processing to do
        else:
            continue
        
        
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
        
        final_lines = []
        
        for ei in combined_extracted_lines:
            temp_final_line = [
                ei[0], # Date - no change
                ei[1], # Type - no change
                ei[2], # Detail - no change
                ei[3] if ei[1] != 'CR' else '', # Paid Out (ie not credited)
                ei[3] if ei[1] == 'CR' else '', # Paid In
                ei[4], # Balance
            ]    
            final_lines.append(temp_final_line)
            
            

    return final_lines
            

def save_extracted_list_to_csv(text: list[list[str]], output_file):
    print("Saving CSV as tab separated")

    with open(output_file, "w", newline="") as csvfile:
        writer  = csv.writer(csvfile, delimiter="\t")
        
        writer.writerow(["Date", "Transaction Type", "Transaction Detail", "Paid Out", "Paid In", "Balance"])

        for ll in text:
            writer.writerow([ll[0], ll[1], ll[2], ll[3], ll[4], ll[5]])
        
        
def save_raw_text_to_file(text: list[list[str]], output_file):
    print("Saving extracted data to txt")
    
    with open(output_file, "w") as file:
        for lines_list in text:
            for line in lines_list:
                file.write(line + "\n")
        
    
def main():
    if INPUT_FILE == '':
        print ('Please modify the value of "INPUT_FILE" in this python file to point to the file you want to process')
        print ('A future version of this app might help you point to the file')
        exit(1)
    all_lines  = load_pdf_pages(INPUT_FILE)
    cleaned_list = cleanup_useful_lines(all_lines)
    save_raw_text_to_file(cleaned_list, OUTPUT_FILE_RAW)
    extracted_list = extract_line_info_into_dict(cleaned_list)
    save_extracted_list_to_csv(extracted_list, OUTPUT_FILE_CVS)
    return 0


if __name__ in "__main__":
    main()
# Python script to convert HSBC UK pdf consumers monthly statement into money managers files.
The file created is a .csv file, (with tab delimiters) which can be imported into Excel and some money management software

# How to use:
- change the 'INPUT_FILE' value in the .py file to point to the PDF file you want to process using any text editor like Notepad
- run ```python HSBC_Statement_pdf_parser.py``` (requires python 3)
- this generates a file 'output.csv'

# How to use the output file:
This filename can be changed if desired, of course.
In Excel, the file can be imported by:
  - Create a blank xls sheet
  - Go to Data tab, then select "from text". Find the output.cvs file that this file has created.
  - On the window that opens, select 'Delimited' and also add a tick to 'My data has headers' Click Next
  - Under Delimiters, select Tab, click Next
  - Under Data Column Format for the first column, it is possible to select "Date". Click Finish.
  - select OK

For other software, similar process will need to be followed. Your turn to find out.

# Notes:
- python script released under GPL v2 license. Reuse/modify/improve/fork at your own volition
- Feel free to notify of any possible issue, improvement or features or propose modifications using the "issues" section
- This is not endorsed or supported by HSBC. There is no guarantee that this works correctly always. Use at your own risk. But if you notice issues, let's try to solve them.
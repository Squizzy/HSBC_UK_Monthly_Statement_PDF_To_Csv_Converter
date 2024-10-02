# Python script to convert HSBC UK pdf consumers monthly statement into money managers files.
The file created is .csv files, (with tab delimiters) which can be imported into Excel and some money management software.
Also create a .qif which should import into most Money managers (like homebank)

# How to use:
- run, using python 3:  
  ```python HSBC_Statement_pdf_parser.py```
- select the HSBC Personal Monthly Statemtn PDF you want to process
- The script will then generate 3 files:
  - one with extension ".qif"
  - one with extension ".csv" with lines as in the PDF.
    - Can be imported into Excel
  - one with extension "-mmx.csv" with amount (paid in, paid out) combined in one line
    - Can be imported into MemoryManagerEx

# How to use the output files:
## Excel
Go to a blank excel worksheet
  - Go to Data tab in the excel ribbon, then select "from text". 
    - Find the cvs file that this file was created. (either will work)
  - On the window that opens
    - Select 'Delimited' and 
    - Tick to 'My data has headers'
    - Click Next
  - Under Delimiters
    - Select Tab
    - Click Next
  - Data Column Format for the first column, it is possible to select "Date". 
    - Click Finish.
  - Select OK

## MoneyManagerEx
File > Import > as CSV
  - Column "date", select "Date"
  - Column "type", select "Don't Care"
  - Column "amount", select "Amount"
  - Column "detail", select "Payee"
  - Date format: select "DD Mon YY"
  - CSV delimiter: type "\t" (without the "")
  - Amount: select "Positive values are deposits"
  - Decimal Char: select "."
  - rows to ignore: from start: None, from end: None
  - then you can save the persent (3rd line from the top)
    - give it a memorable name like "from HBSC_UK_Monthly_Statement_pdf_parser"
    - This can then be recalled for the next import
  - after import, the .csv files can be deleted

## QIF file
This should import into most money managers as it is standard

For other software, similar process will need to be followed. Your turn to find out.

# Credits:
For QIF:
- https://github.com/fabrizionastri/csv2qif-py/tree/master

# Notes:
- python script released under GPL v2 license. 
- Script is not endorsed or supported by HSBC. 
- Use at your own risk. 
  - There is no guarantee that it will always works correctly. 
- If you notice issues, let's try to solve them.
  - Feel free to notify of any possible issue, improvement or features or propose modifications using the "issues" section of github
- Reuse/modify/improve/fork at your own volition
  - If you notify, I will look at including the improvements here

# Versions:
- v0.2: Added interactive file selection, generation of MemoryManagerEx CSV, and generation of QIF
- v0.1: first release, generates basic CSV
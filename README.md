# Ticker
Python code to provide a stock ticker.

Stock prices from yahoo finance using yahooquery module (https://yahooquery.dpguthrie.com/).  Uses Tkinter gui (https://docs.python.org/3/library/tkinter.html).

List of stocks and positions should be placed in a csv file names "stockscroll.csv" in the directory where the program is run.  If you use Schwab, you can  download your positions by going to the Positions page and selecting Export in the top right.  Rename the downloaded file to "schwab.csv" and place it in the directory where the program is run.  It currently doesn't handle options so those will likely need to be deleted from the csv file (to-do: deal with options).  If you start the program with no .csv file, it will generate a default csv file with a few stocks.

If you click on your Total Account Value or individual stocks in the display, the program will bring up a plot.  For Total Account Value plots, it assumes you had the same amount of cash and stock positions (e.g., it doesn't allow for changing positions or cash).

Current To-Do List:
1.  Deal with options or other data types in schwab.csv.
2.  Stress tests to deal with a small number of stocks and csv errors.
3.  Snap to points and display data values when hovering over plots.

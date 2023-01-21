from tkinter import *
from tkinter import messagebox
import sqlite3
from yahooquery import Ticker
import utility as util
import csv
import threading
import os

class MainWindow():
    def __init__(self, root, callback):  # callback(message, data)
        self.dbfile = 'stockscroll.sqlite'
        self.root = root

        # Update stock list from latest schwab download
        self.parsecsv()

        # Get quotes and update database
        self.priceindex = 0
        self.callback = callback
        self.symbols = self.getSymbolList()
        self.checkprice()


    def checkprice(self):
        pricedelay = 3 * 1000
        numquotes = 10
        symbols = self.symbols[self.priceindex:self.priceindex + numquotes]
        if not self.callback is None:
            self.callback('quote', f'Getting Quotes: {symbols}')
        
        pricedict = self.getQuotes(symbols)
        for k, v in pricedict.items():
            pp, _ = self.getPrice(k)
            if abs(v['price'] - pp) > 0.001:
                self.updatePrice(k, v['price'], v['pclose'])
                
        self.priceindex += numquotes
        if self.priceindex >= len(self.symbols):
            self.priceindex = 0
            self.callback('done with first round', None)

        if not self.anyNone() and len(pricedict) > 0 and v['state'] == 'CLOSED' and pp > 0.1:
            pricedelay = 60 * 5 * 1000
            self.callback('quote', 'Getting Quotes: Markets Closed')
        self.root.after(pricedelay, self.checkprice)


    def getSymbolList(self, idDict=False):
        '''Returns list of symbols or dict (sym is key, id is value)'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        cur.execute('SELECT name, id FROM StockList')
        stocks = cur.fetchall()
        if stocks is None or len(stocks)==0:
            print(f'Error retrieving data from {self.dbfile}')
        if  idDict:
            return {s[0]:s[1] for s in stocks if s[0] != 'CASH'}
        else:
            return [s[0] for s in stocks if s[0] != 'CASH'] 


    def parsecsv(self):
        filename_schwab = 'schwab.csv'
        file_csv = 'stockscroll.csv'
        start = False
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        stockdict = {}
        schwab = False

        try:
            f = open(filename_schwab, 'r')
            schwab_type = True
            quancol = 2
            basiscol = 9
            cashcol = 6
        except:
            try:
                f = open(file_csv, 'r')
                quancol = 2
                basiscol = 3
                cashcol = 2
            except:
                f = None

        if f is None:
            stockdict = {'CASH':('', 0, 0), '^SPX':('S&P 500', 0, 0), 'SPY':('SPDR S&P 500 ETF', 0, 0), 'AAPL':('Apple Inc', 0, 0), 'QQQ': ('Invesco QQQ', 0, 0)}
            fn = self.writecsv(stockdict)
            messagebox.showwarning('No CSV File', f'Unable to open schwab.csv or stockscroll.csv.  Using default stock list.  To change stock list, edit:\n{fn}')
        else:
            with f:
                csv_file = csv.reader(f)
                for row in csv_file:
                    if not start and 'symbol' in row[0].lower():
                        start = True
                        continue
                    if not start: continue
                    if 'cash' in row[0].lower():
                        if self.exists(cur, 'CASH'):
                            cur.execute('UPDATE StockList SET shares=? WHERE name=?', (row[cashcol], 'CASH',))
                        else:
                            cur.execute('INSERT INTO StockList (name,shares) VALUES (?,?)', ('CASH', row[cashcol]))
                        continue
                    if schwab_type and 'Account' in row[0]:
                        break
                    _, shares, basis = stockdict.get(row[0], ('',0,0))
                    shares += util.tryFloat(row[quancol])
                    basis = util.tryFloat(row[basiscol])
                    if row[0].upper() == 'BRK/B': 
                        sym = 'BRK-B'
                    else: 
                        sym = row[0].upper()
                    stockdict[sym] = (row[1], shares, basis)
        
        if not '^SPX' in stockdict.keys():
            stockdict['^SPX'] = ('S&P 500', 0, 0)
        for k, v in stockdict.items():
            if self.exists(cur, k):
                cur.execute('UPDATE StockList SET description=?,Shares=?,Basis=? WHERE name=?',(v[0], v[1], v[2], k))
            else:
                cur.execute('INSERT INTO StockList (name,description,Shares,Basis) VALUES (?,?,?,?)', (k, v[0], v[1], v[2]))

        cur.execute('SELECT name FROM StockList')
        data = cur.fetchall()
        stocklist = [d[0] for d in data if d[0] != 'CASH' and d[0] != '^SPX']
        mystocks = stockdict.keys()
        deletelist = [stock for stock in stocklist if not stock in mystocks]
        for stock in deletelist:
            cur.execute('DELETE FROM StockList WHERE name=?', (stock,))

        conn.commit()

    def writecsv(self, stockdict):
        file_csv = 'stockscroll.csv'
        f = open(file_csv, 'w', newline='')
        writer = csv.writer(f)
        writer.writerow(['Symbol','Description','Quantity','Basis'])
        for k,v in stockdict.items():
            writer.writerow([k, v[0], f'{v[1]}', f'{v[2]}'])
        filename = os.path.realpath(f.name)
        f.close()
        return filename


    def exists(self, cur, name):
        cur.execute('SELECT id FROM StockList WHERE name=?', (name,))
        data = cur.fetchall()
        if data is None or len(data) == 0:
            return False
        else:
            return True

    def getQuotes(self, symbols):
        '''Reteurns (Current Price, Previous Close, Market State)'''
        quote = Ticker(symbols).price
        quoteDict = {}
        for k, v in quote.items():
            sym = k
            if v['marketState'] == 'PRE' and (not v.get('preMarketPrice', None) is None):
               quoteDict[sym] = {'price': v['preMarketPrice'], 'pclose': v['regularMarketPrice'], 'state': v['marketState']}
            elif v['marketState'] == 'POST' and (not v.get('postMarketPrice', None) is None):
                quoteDict[sym] = {'price': v['postMarketPrice'], 'pclose': v['regularMarketPreviousClose'], 'state': v['marketState']} 
            else:
                price =  v.get('regularMarketPrice', 0.0)
                pclose = v.get('regularMarketPreviousClose', 0.0)
                state = v.get('marketState', 'NA')
                quoteDict[sym] = {'price': price, 'pclose': pclose, 'state': state}
        
        return quoteDict

    def getAllQuotes(self, symbols):
        '''Updates the price and previous close for [symbols] (or one symbol)'''
        if not type(symbols) is list: symbols = [symbols]
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        data = self.getQuote(symbols)
        for symbol in symbols:
            (price, prevClose, state) = self.getQuote(symbol)
            cur.execute('UPDATE StockList SET Price=?, PreviousClose=? WHERE name=?', (price, prevClose,symbol))
        conn.commit()

    def getPrice(self, sym):
        '''Returns the currently stored price for a symbol'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        cur.execute('SELECT Price, PreviousClose FROM StockList WHERE name=?', (sym,))
        data = cur.fetchone()
        if data is None or len(data) == 0:
            return 0.0
        if data[0] is None: rval = 0.0
        else: rval = data[0]
        if data[1] is None: pclose = 1.0
        else: pclose = data[1]
        return rval, pclose

    def updatePrice(self,symbol,price,pclose):
        '''Update price and previous close for symbol'''
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        cur.execute('UPDATE StockList SET Price=?, PreviousClose=? WHERE name=?', (price, pclose,symbol))
        conn.commit()

    def anyNone(self):
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        cur.execute('SELECT name, Price, PreviousClose FROM StockList')
        data = cur.fetchall()
        if data is None or len(data) == 0:
            return False
        data = [d for d in data if d[0] != 'CASH' and d[0] != 'VTS']
        if any([d[1] is None or d[2] is None for d in data]):
            return True
        else:
            return False

#root = Tk()
#main = MainWindow(root)
#root.mainloop()
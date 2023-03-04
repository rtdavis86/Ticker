from tkinter import *
from tkinter import font
from tkinter.font import Font
import sqlite3
from yahooquery import Ticker
import getquotes
import time
import utility as util
import portplot

class MainWindow():
    def __init__(self, root):
        self.root = root
        self.setup() # Options: 0-name, 1-scroll_delay, 2-port_delay, 3-win_x, 4-win_y, 5-win_dx, 6-win_dy
        root.geometry('%dx%d+%d+%d' % (self.options[5], self.options[6], self.options[3], self.options[4]))
        self.root.title('StockScroll')
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(size=16)
        self.sortPercent = True
        self.scroll_delay = self.options[1]
        self.port_delay = self.options[2]
        self.compare_symbol = self.options[7]
        self.loop_count = 0
        self.loop_time = 0
        self.show_leadlag = False
        self.leadlagshow = 5
        root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.plot = portplot.MainWindow(root, self.compare_symbol)
        self.after = [None, None]
        
        # Setup Labels for 2 lines of text: 0-info message, 1-tick changes
        self.setupLabels()

        # Start getting quotes
        self.quote = getquotes.MainWindow(root,self.quote_callback)

        self.symbols = self.getSymbolList()
        self.loop()
        self.updatePort()

    
    def on_closing(self):
        after_list = self.root.tk.call('after', 'info')
        for item in after_list:
            self.root.after_cancel(item)
        self.root.destroy()

    def click_label(self, data):
        if type(data) is str:
            if data == 'S&P500': sym = '^SPX'
            else: sym = data
        else:
            sym = data.cget('text')
            crem = '0123456789.()% -'
            sym = ''.join([c for c in sym if not c in crem])
            if sym == 'BRKB': sym = 'BRK-B'
        self.plot.addfig(sym)

    def quote_callback(self, msg, data):
        if not self.show_leadlag and 'quote' in msg:
            self.leadlaglabels[0].configure(text=data)
        elif 'done' in msg:
            self.show_leadlag = True

    def setup(self):
        self.dbfile = 'stockscroll.sqlite'
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        create_options = '''CREATE TABLE IF NOT EXISTS "Options" (
            "name"              TEXT,
	        "scroll_delay"	    INTEGER,
	        "port_delay"	    INTEGER,
	        "win_x"	            INTEGER,
	        "win_y"	            INTEGER,
	        "win_dx"	        INTEGER,
	        "win_dy"	        INTEGER
            "compare_symbol"    TEXT);'''
        cur.execute(create_options)
        cur.execute('SELECT name, scroll_delay, port_delay, win_x, win_y, win_dx, win_dy, compare_symbol FROM Options')
        data = cur.fetchall()
        defv = ('default',500, 5000, 27, 654, 1500, 130, 'SPY')
        if data is None or len(data) == 0 or not 'default' in [d[0] for d in data]:
            insert_default = '''INSERT INTO Options (name, scroll_delay, port_delay, win_x, win_y, win_dx, win_dy, compare_symbol)
                VALUES(?,?,?,?,?,?,?,?)'''
            cur.execute(insert_default, defv)
        if 'user' in [d[0] for d in data]:
            self.options = [d for d in data if d[0]=='user']
            self.options = [d for d in self.options[0]]
        else:
            self.options = [d for d in defv]

        create_options = '''CREATE TABLE IF NOT EXISTS "StockList" (
	        "id"	INTEGER NOT NULL UNIQUE,
	        "name"	TEXT NOT NULL UNIQUE,
	        "description"	TEXT,
	        "Price"	REAL,
	        "PreviousClose"	REAL,
	        "DateTime"	INTEGER,
	        "Shares"	REAL,
	        "Basis"	INTEGER,
	        PRIMARY KEY("id" AUTOINCREMENT));'''
        cur.execute(create_options)
        conn.commit()

        cur.execute('SELECT id FROM StockList')
        data = cur.fetchall()
        if len(data) == 0:
            stockdict = {'CASH':('', 0, 0), '^SPX':('S&P 500', 0, 0), 'SPY':('SPDR S&P 500 ETF', 0, 0), 'AAPL':('Apple Inc', 0, 0), 'QQQ': ('Invesco QQQ', 0, 0), 'VXF': ('VANGUARD EXTENDED MARKETETF', 0, 0), 'AMZN': ('AMAZON.COM INC',0,0)}
            for k,v in stockdict.items():
                cur.execute('INSERT INTO StockList (name,description,Shares,Basis) VALUES (?,?,?,?)', (k, v[0], v[1], v[2]))
        conn.commit()

    def loop(self):
        start = time.time()
        self.updateScroll()
        self.loop_count += 1
        self.loop_time += time.time()-start
        self.after[0] = self.root.after(self.scroll_delay, self.loop)

    def portValue(self):
        '''Returns (Total Value, Day Change, All Change)'''
        data = self.getSymbolPrices()
        total = 0.0
        daychange = 0.0
        allchange = 0.0
        for sym, price, pclose, shares, basis in data:
            if sym == 'CASH':
                total += util.tryFloat(shares)
            else:
                if price is None: continue
                total += price * shares
                if not (sym == 'QRFT' or sym == 'SWPPX'):
                    daychange += (price-pclose) * shares
                delta = price*shares - basis
                allchange += delta
        return (total, daychange, allchange)

    def updateScroll(self):
        data = self.getSymbolPrices()
        data = [d for d in data if d[0] != 'CASH']
        if self.sortPercent:
            data = sorted(data, key=lambda d: d[1]/d[2] if not d[1] is None and not d[2] is None else 0, reverse=True)
        else:
            data = sorted(data, key = lambda d: d[0])
   
        for count, item in enumerate(self.tickitems):
            index = self.stockindex + count
            while index >= len(data): 
                index = index - len(data)
            sym, price, pp, _, _ = data[index]
            if price is None or pp is None:
                price = 0.0
                pp = 1.0
            msg = sym + ' ' + util.strfloat(price,2) + ' (' + util.strfloat(100.0*(price/pp-1.0),1) + '%) '
            if count == 0:
                if self.pos >= len(msg):
                    self.stockindex += 1
                    if self.stockindex >= len(data): self.stockindex=0
                    self.pos = 0
                    index = self.stockindex + count
                    while index >= len(data): 
                        index = index - len(data)
                    sym, price, pp, _, _ = data[index]
                    if price is None or pp is None:
                        price = 0.0
                        pp = 1.0
                    msg = sym + ' ' + util.strfloat(price,2) + ' (' + util.strfloat(100.0*(price/pp-1.0),1) + '%) '
                msg = msg[self.pos:]
            if price < pp:
                item.configure(text=msg, fg='red')
            elif price > pp:
                item.configure(text=msg, fg='green')
            else:
                item.configure(text=msg, fg='black')
        self.pos += 1


    def updatePort(self):
        total, daychange, allchange = self.portValue()
        status = self.getMarketStatus()
        self.labelitems[0].configure(text=status[0])
        self.labelitems[1].configure(text=f'{util.strfloat(total,0)}')
        if total == 0.0: divideby = 1.0
        else: divideby = total-allchange
        self.labelitems[2].configure(text=f'{util.strfloat(allchange,0)} ({util.strfloat(100*allchange/divideby,1)}%)')
        if allchange >= 0.0: 
            self.labelitems[2].configure(fg='green')
        else: 
            self.labelitems[2].configure(fg='red')
        if total == 0.0: divideby = 1.0
        else: divideby = total-daychange
        self.labelitems[3].configure(text=f'{util.strfloat(daychange,0)} ({util.strfloat(100*daychange/divideby,1)}%)')
        if daychange >= 0.0: 
            self.labelitems[3].configure(fg='green')
        else: 
            self.labelitems[3].configure(fg='red')
        spx_price, spx_pp = self.getPrice('^SPX')
        if  spx_pp > 2.0:
            spx_delta = 100*(spx_price/spx_pp-1)
        else:
            spx_delta = 0.0
        self.labelitems[4].configure(text=f'{util.strfloat(spx_price,0)} ({util.strfloat(spx_delta, 1)}%)')
        if spx_price >= spx_pp: 
            self.labelitems[4].configure(fg='green')
        else: 
            self.labelitems[4].configure(fg='red')

        if self.show_leadlag:  # Need to deal with having < 10 symbols in list
            data = self.getSymbolPrices()
            data = [d for d in data if d[0] != 'CASH']
            data = sorted(data, key=lambda d: d[1]/d[2] if not d[1] is None and not d[2] is None else 0, reverse=True)
            lead_lag = data[:self.leadlagshow] + data[-self.leadlagshow:]
            self.leadlaglabels[0].configure(text='Lead: ')
            self.leadlaglabels[self.leadlagshow+1].configure(text='Lag: ')
            msg = 'Lead: '
            add_pos = 1
            for i, item  in enumerate(lead_lag):
                sym, price, pp, _, _ = item
                if pp == 0.0: pp = 1.0
                if i == self.leadlagshow: 
                    add_pos = 2
                pos = i + add_pos
                msg = f'{sym} {100.0*(price/pp-1):.2f}%'
                if price > pp:
                    self.leadlaglabels[pos].configure(text=msg, fg='green')
                elif price < pp:
                    self.leadlaglabels[pos].configure(text=msg, fg='red')
                else:
                    self.leadlaglabels[pos].configure(text=msg, fg='black')
        
        self.after[1] = self.root.after(self.port_delay, self.updatePort)


    def changeSort(self):
        self.sortPercent = not self.sortPercent
        if self.sortPercent:
            self.sortbutton.configure(text='Sort A-Z')
        else:
            self.sortbutton.configure(text='Sort %')

    def moveforward(self):
        self.stockindex += 5
        self.pos = 0
        self.updateScroll()

    def moveback(self):
        self.stockindex -= 5
        self.pos = 0
        self.updateScroll()


    def config(self): # Options: 0-name, 1-scroll_delay, 2-port_delay, 3-win_x, 4-win_y, 5-win_dx, 6-win_dy, 7-compare_symbol
        self.configwin = Toplevel()
        row1 = Frame(self.configwin)
        row1.pack(side=TOP, fill=X, padx=5, pady=5)
        Label(row1, width=35, text='Scroll delay in seconds (0.2-5.0):', anchor='w').pack(padx=2, side=LEFT)
        self.sdelayent = Entry(row1)
        self.sdelayent.insert(0, f'{self.options[1]/1000.0}')
        self.sdelayent.pack(side=RIGHT, expand=YES, fill=X, padx=2)

        row2 = Frame(self.configwin)
        row2.pack(side=TOP, fill=X, padx=5, pady=5)
        Label(row2, width=35, text='Portfolio update in seconds (2.0-10.0):', anchor='w').pack(padx=2, side=LEFT)
        self.pdelayent = Entry(row2)
        self.pdelayent.insert(0, f'{self.options[2]/1000.0}')
        self.pdelayent.pack(side=RIGHT, expand=YES, fill=X, padx=2)

        row3 = Frame(self.configwin)
        row3.pack(side=TOP, fill=X, padx=5, pady=5)
        Label(row3, width=35, text='Compare Symbol:', anchor='w').pack(padx=2, side=LEFT)
        sel_options = self.symbols.copy()
        sel_options.insert(0, 'None')
        self.config_compare = StringVar()
        if self.options[7] in sel_options:
            self.config_compare.set(self.options[7])
        else:
            self.config_compare.set(sel_options[0])
        OptionMenu(row3 , self.config_compare , *sel_options ).pack(side=RIGHT, padx=2)

        self.winpos = []
        self.geomlabel = Label(self.configwin, text=f'Win Geometry: x={self.options[3]:.0f}, y={self.options[4]:.0f}, dx={self.options[5]:.0f}, dy={self.options[6]:.0f}', anchor='w')
        self.geomlabel.pack(side=TOP, fill=X, padx=5, pady=5)
        Button(self.configwin, text='Use Current Geometry', command=self.locconfig).pack(side=TOP, padx=5, pady=5)
        Button(self.configwin, text='Save', command=self.saveconfig).pack(padx=5, pady=5, side=RIGHT)
        Button(self.configwin, text='Update', command=self.fetchconfig).pack(side=RIGHT, padx=5, pady=5)
        Button(self.configwin, text='Cancel', command=self.configwin.destroy).pack(side=RIGHT, padx=5, pady=5)

    def locconfig(self):
        geom = self.root.geometry()
        split1 = geom.split('+')
        split2 = split1[0].split('x')
        self.winpos = [util.tryFloat(split1[1]), util.tryFloat(split1[2]), util.tryFloat(split2[0]), util.tryFloat(split2[1])]
        self.geomlabel.configure(text=f'Win Geometry: x={self.winpos[0]:.0f}, y={self.winpos[1]:.0f}, dx={self.winpos[2]:.0f}, dy={self.winpos[3]:.0f}')

    def saveconfig(self):
        self.fetchconfig()
        self.options[0] = 'user'
        self.options[1] = int(self.opt1)
        self.options[2] = int(self.opt2)
        if len(self.winpos) > 0:
            for i in range(4):
                self.options[i+3] = self.winpos[i]
        self.options[7] = self.opt3
        self.plot.compare_symbol = self.options[7]
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        cur.execute('SELECT name FROM Options WHERE name = ?', ('user',))
        data = cur.fetchone()
        if data is None or len(data) == 0:
            insert_values = '''INSERT INTO Options (name, scroll_delay, port_delay, win_x, win_y, win_dx, win_dy, compare_symbol)
                VALUES(?,?,?,?,?,?,?,?)'''
            cur.execute(insert_values, tuple(self.options))
        else:
            update_values = '''UPDATE Options SET name=?, scroll_delay=?,port_delay=?,win_x=?,win_y=?,win_dx=?,win_dy=?,compare_symbol=? WHERE name="user"'''
            cur.execute(update_values, tuple(self.options))
        conn.commit()
        self.scroll_delay = self.options[1]
        self.port_delay = self.options[2]
        self.compare_symbol = self.options[7]
        self.configwin.destroy()


    def fetchconfig(self):
        sdelay = util.tryFloat(self.sdelayent.get())
        if not sdelay is None and sdelay >= 0.2 and sdelay <= 5.0:
            self.opt1 = sdelay * 1000.0
        else:
            self.opt1 = self.options[1]
        self.sdelayent.delete(0, END)
        self.sdelayent.insert(0, f'{self.opt1/1000.0}')

        pdelay = util.tryFloat(self.pdelayent.get())
        if not pdelay is None and pdelay >= 2.0 and pdelay <= 10.0:
            self.opt2 = pdelay * 1000.0
        else:
            self.opt2 = self.options[2]
        self.pdelayent.delete(0, END)
        self.pdelayent.insert(0, f'{self.opt2/1000.0}')
        self.opt3 = self.config_compare.get()

    def setupLabels(self):
        self.tickitems = []
        self.labelitems = []
        self.pos = 0
        self.stockindex = 0
        
        self.labelFrame = Frame(self.root)
        self.labelFrame.pack(fill='both')
        alabel = Label(self.labelFrame, text='Markets: ')
        alabel.pack(side=LEFT)
        alabel.bind("<Button-1>", lambda e:self.click_label('TAV'))
        self.labelitems.append(Label(self.labelFrame, text='CLOSED'))
        self.labelitems[-1].pack(side=LEFT)
        alabel = Label(self.labelFrame,text='  Total Account Value: ')
        alabel.pack(side=LEFT)
        alabel.bind("<Button-1>", lambda e:self.click_label('TAV'))
        self.labelitems.append(Label(self.labelFrame, text='72000'))
        self.labelitems[-1].pack(side=LEFT)
        alabel = Label(self.labelFrame, text='  Unrealized P&L: ')
        alabel.pack(side=LEFT)
        alabel.bind("<Button-1>", lambda e:self.click_label('TAV'))
        self.labelitems.append(Label(self.labelFrame, text='P&L (%P&L)'))
        self.labelitems[-1].pack(side=LEFT)
        alabel = Label(self.labelFrame, text='  Day P&L: ')
        alabel.pack(side=LEFT)
        alabel.bind("<Button-1>", lambda e:self.click_label('TAV'))
        self.labelitems.append(Label(self.labelFrame, text='P&L (%P&L)'))
        self.labelitems[-1].pack(side=LEFT)
        alabel = Label(self.labelFrame, text='  S&P500: ')
        alabel.pack(side=LEFT)
        alabel.bind("<Button-1>", lambda e:self.click_label('S&P500'))
        self.labelitems.append(Label(self.labelFrame, text='4000 (0.5%)'))
        self.labelitems[-1].pack(side=LEFT)
        buttonfont = Font(size=12)
        self.sortbutton = Button(self.labelFrame, text='Sort A-Z', command=self.changeSort, font=buttonfont)
        self.sortbutton.pack(side=LEFT, padx=3)
        Button(self.labelFrame, text='<', font=buttonfont, command=self.moveback).pack(side=LEFT, padx=3)
        Button(self.labelFrame, text='>', font=buttonfont, command=self.moveforward).pack(side=LEFT, padx=3)
        Button(self.labelFrame, text='Config', command=self.config, font=buttonfont).pack(side=LEFT, padx=3)
        Button(self.labelFrame, text='Plot Update', command=lambda: self.plot.getQuoteHistory(force_update=True), font=buttonfont).pack(side=LEFT, padx=3)
        
        self.tickFrame = Frame(self.root)
        self.tickFrame.pack(fill=BOTH)
        for i in range(11):
            item = Label(self.tickFrame, text=f"XXX{i}: 145.0 (2.0%)", fg='green', padx=1, anchor='w')
            item.pack(side=LEFT)
            self.tickitems.append(item)

        self.leadlaglabels = []
        for i in range(self.leadlagshow*2 + 2):
            self.leadlaglabels.append(Label(self.root, text=' ', anchor='w'))
            self.leadlaglabels[-1].pack(side=LEFT)

        for i, list in enumerate([self.labelitems[:-1], self.tickitems, self.leadlaglabels]):
            if i == 0: msg = 'TAV'
            for label in list:
                if i > 0: msg = label
                label.bind("<Button-1>", lambda e, msg=msg:self.click_label(msg))
        self.labelitems[-1].bind("<Button-1>", lambda e:self.click_label('S&P500'))
        

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


    def getSymbolPrices(self, sym=None):
        '''Returns [(symbol, Price, PreviousClose, Shares, Basis)]'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        if sym is None:
            cur.execute('SELECT name, price, PreviousClose, Shares, Basis FROM StockList ORDER BY name')
        else:
            cur.execute('SELECT name, price, PreviousClose, Shares, Basis FROM StockList WHERE name=?', (sym,))
        stocks = cur.fetchall()
        if stocks is None or len(stocks)==0:
            print(f'Error retrieving data from {self.dbfile}')
            return None
        stock_data = [(s[0], s[1], s[2], s[3], s[4]) for s in stocks if (not s[1] is None) and (not s[2] is None) or s[0] == 'CASH']
        return stock_data


    def getPrice(self, sym):
        '''Returns the currently stored price for a symbol'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        cur.execute('SELECT Price, PreviousClose FROM StockList WHERE name=?', (sym,))
        data = cur.fetchone()
        if data is None or len(data) == 0:
            return 0.0, 1.0
        if data[0] is None: rval = 0.0
        else: rval = data[0]
        if data[1] is None: pclose = 1.0
        else: pclose = data[1]
        return rval, pclose


    def getMarketStatus(self):
        '''Returns (marketState, marketTime)'''
        quote = Ticker('AAPL').price
        if quote is None:
            return ('Not Available', 'Not Available')
        return (quote['AAPL'].get('marketState', 'Not Available''Not Available'),quote['AAPL'].get('regularMarketTime', 'Not Available'))



root = Tk()
main = MainWindow(root)
root.mainloop()
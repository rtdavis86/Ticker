from tkinter import *
import sqlite3
from yahooquery import Ticker
import utility as util
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date
import numpy as np
from matplotlib.widgets import Button as pltButton
import math
from tkinter import messagebox
from pandas import Timestamp
from dateutil.relativedelta import relativedelta

class MainWindow():
    def __init__(self, root):
        self.root = root
        self.dbfile = 'stockscroll.sqlite'
        self.symbols = None
        self.updateNeeded = False
        self.lockdb = False
        self.figdict = {}  # Items in dict: fig, ax, artlist 

        self.createTables()
        self.getQuoteHistory()
        self.updateHistory()
        self.updatePlot()

    def addfig(self, sym):
        if self.lockdb:
            messagebox.showwarning('Plot Warning', 'Plot not available until quotes finish loading.')
            return
        if sym in self.figdict.keys():
            return
        fig = plt.figure()
        fig.canvas.mpl_connect('close_event', lambda e, sym=sym: self.on_close(e, sym))
        ax = fig.subplots()
        plt.subplots_adjust(bottom=0.08)
        plt.plot()
        mngr = plt.get_current_fig_manager()
        mngr.window.wm_geometry('%dx%d+%d+%d' % (1450, 600, 30, 30))
        plt.ion()
        but_list = self.add_buttons(sym)
        plt.show()
        self.figdict[sym] = {'fig': fig, 'ax': ax, 'artlist': [], 'mode': 'd', 'per': 1, 'but_list': but_list}
        self.plotPort(sym)

    def bringtofront(self):
        print(f'Bring {self.sym} to front')

    def on_close(self, event, sym):
        del self.figdict[sym]

    def add_buttons(self, sym):
        x_start = 0.12
        options = [[1,2,5,10], [1,2,5,10], [1,2,6,12]]
        day_buttons = []
        for i, mode in enumerate(['d', 'w', 'm']):
            bax = plt.axes([x_start, 0.015, 0.04, 0.04])
            bax.axis('off')
            if mode == 'd': ptext = 'Day: '
            elif mode == 'w': ptext = 'Week: '
            elif mode == 'm': ptext = 'Month:'
            bax.text(0.5,0.5,ptext, va='center', ha='center')
            bax_points = [x_start+0.038, 0.015, 0.04, 0.04]
            for opt in options[i]:
                bax = plt.axes(bax_points)
                bax_points[0] += bax_points[1]*2 + 0.01
                day_buttons.append(pltButton(bax, f'{opt}{mode}'))
                day_buttons[-1].on_clicked(lambda e, per=opt, mode=mode, sym=sym: self.press_button(per, mode, sym))
            x_start += (bax_points[1] * 2 + 0.01) * 4 + 0.038
        return day_buttons

    def press_button(self, per, mode, sym):
        if self.figdict[sym]['mode'] != mode:
            self.figdict[sym]['mode']  = mode
            self.getQuoteHistory()
        self.figdict[sym]['per']  = per
        self.figdict[sym]['ax'].clear()
        self.plotPort(sym)

    def updatePlot(self):
        delay = 1000*5
        if self.updateNeeded:
            for sym in self.figdict.keys():
                self.figdict[sym]['ax'].clear()
                self.plotPort(sym)
        self.root.after(delay, self.updatePlot)


    def updateHistory(self):
        delay = 1000*30*1
        if self.lockdb: 
            self.root.after(delay, self.updateHistory)
            return
        if self.getMarketStatus()[0] in ['PRE', 'REGULAR', 'POST']:
            data = self.getSymbolPrices()
            unixtime = int(datetime.now().timestamp())
            conn = sqlite3.connect(self.dbfile, uri=True)
            cur = conn.cursor()
            last_time = []
            for mode in ['d', 'w', 'm']:
                cur.execute(f'SELECT unixtime FROM PlotHistory_{mode} ORDER BY unixtime DESC')
                utdata = cur.fetchone()
                if utdata is None or len(utdata) == 0:
                    last_time.append(0)
                else:
                    last_time.append(utdata[0])
            for sym, price, _, _, _, id in data:
                if sym == 'CASH': continue
                if unixtime >= last_time[0] + 60*5: 
                    cur.execute('INSERT INTO PlotHistory_d (stock_id, price, unixtime) VALUES(?,?,?)', (id,price,unixtime))
                if unixtime >= last_time[1] + 60*60:
                    cur.execute('INSERT INTO PlotHistory_w (stock_id, price, unixtime) VALUES(?,?,?)', (id,price,unixtime))
            self.updateNeeded = True
            conn.commit()
        self.root.after(delay, self.updateHistory)


    def plotPort(self, sym):
        fig = self.figdict[sym]['fig']
        ax = self.figdict[sym]['ax']
        artlist = self.figdict[sym]['artlist']
        mode = self.figdict[sym]['mode']
        per = self.figdict[sym]['per']
        data = self.getSymbolPrices()
        self.symbols = [d[0] for d in data if d[0] != 'CASH']
        total = []
        shareDict = {}
        lastprice = {}
        prevclose = {}
        basis = {}
        for s, price, pclose, shares, b, _ in data:
            if s == 'CASH':
                cash = util.tryFloat(shares)
            else:
                shareDict[s] = shares
                lastprice[s] = price
                prevclose[s] = pclose
                if shares == 0:
                    basis[s] = None
                else:
                    basis[s] = b/shares

        history, histtimes = self.getdbHistory(mode)
        if len(histtimes) == 0:
            self.getQuoteHistory()
            history, histtimes = self.getdbHistory(mode)
        self.last_time = histtimes[-1]

        if mode == 'd':
            days_list = list(set([datetime.fromtimestamp(ut).day for ut in histtimes]))
            dt = datetime.fromtimestamp(self.last_time)
            day_index = 10 - per
            if day_index < 0: day_index = 0
            if day_index >= len(days_list): day_index = len(day_index)-1
            mindate = datetime(dt.year, dt.month, days_list[day_index], 1, 0).timestamp()
        elif mode == 'w':
            dt = datetime.fromtimestamp(self.last_time)
            begin_dt = dt - timedelta(days=per*7)
            begin_dt = begin_dt.replace(hour=1)
            mindate = begin_dt.timestamp()
        elif mode == 'm':
            dt = datetime.fromtimestamp(self.last_time)
            begin_dt = dt - relativedelta(months=per)
            begin_dt = begin_dt.replace(hour=1)
            mindate = begin_dt.timestamp()
        histtimes = [h for h in histtimes if h > mindate]
        for s in history.keys():
            history[s] = history[s][-len(histtimes):]

        basis_line = None
        if sym == 'TAV':
            for step in range(len(histtimes)+1):
                stepTotal = cash
                for s in self.symbols:
                    if step >= len(history[s]):
                        price = lastprice[s]
                    else:
                        price = history[s][step]
                    if price is None: price = 0.0
                    stepTotal +=  price * shareDict[s]
                total.append(stepTotal)
        else:
            total = history[sym]
            if (not basis[sym] is None) and basis[sym] > 0:
                basis_line = basis[sym]

        ptotal = total[0]
        ax.plot(total, color='black')
        if sym == 'TAV':
            msg = 'Total Account Value: '
        else:
            msg = f'{sym}: '
        msg += f'{total[-1]:.2f} ({100.0*(total[-1]/ptotal-1):.2f}%)'
        if not basis_line is None:
            msg += f', Basis: {basis_line:.2f} ({100*(total[-1]/basis_line-1):.2f}%)'
        
        fig.suptitle(msg, fontsize=20)

        # Remove previous lines
        for item in artlist:
            item.remove()

        # Add horizontal lines
        minv_per = 100*(min(total)/ptotal-1)
        maxv_per = 100*(max(total)/ptotal-1)
        delta_per = 0.1
        if (maxv_per-minv_per)/delta_per > 9:
            delta_per = 0.5
        while (maxv_per-minv_per)/delta_per > 9:
            delta_per += 0.5
        artlist = []
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        # Basis line
        if (not basis_line is None) and basis_line > ylim[0] and basis_line < ylim[1]:
            lineitem = ax.axhline(y=basis_line, color='blue', linestyle='-')
            artlist.append(lineitem)
            atext = ax.text(xlim[0], basis_line, f'Basis = {basis_line:.2f}', ha='left', va='bottom')
        if math.floor(minv_per) < 0.0:
            a = np.arange(0.0, math.floor(minv_per), -delta_per)
        else:
            a = []
        if math.ceil(maxv_per) > 0.0:
            b = np.arange(delta_per, math.ceil(maxv_per), delta_per)
        else:
            b = []
        perlist = np.concatenate((a, b), axis=0)
        for percent in perlist:
            yval = ptotal*(1+percent/100.0)
            if yval < ylim[0] or yval > ylim[1]: continue
            if percent < 0.0: color = 'red'
            elif percent > 0.0: color = 'green'
            else: color = 'black'
            lineitem = ax.axhline(y=yval, color=color, linestyle='--')
            artlist.append(lineitem)
            atext = ax.text(xlim[1], yval, f'  {percent:.1f}%', ha='left', va='center')
            artlist.append(atext)

        # Add vertical lines
        ax.get_xaxis().set_ticks([])
        pday = datetime(1972, 1, 1)
        delta = 1
        deltadays = 10
        show_last_close = True
        while (histtimes[-1]-histtimes[0])/(60*60*24*delta) > 16:
            delta += 1
        show_vals = False
        vals = [12,14]
        if (histtimes[-1]-histtimes[0])/(60*60*24*delta) <= 8:
            show_vals = True
        look_for_val = [True, True]
        for pos, utime in enumerate(histtimes):
            dt = datetime.fromtimestamp(utime)
            for i, v in enumerate(vals):
                if show_vals and look_for_val[i]:
                    if dt.hour >= v:
                        look_for_val[i] = False
                        lineitem = ax.axvline(x=pos, color='y', linestyle=(0, (5, 10)))
                        artlist.append(lineitem)
                        if v == 12: hr_text = '12p'
                        elif v == 14: hr_text = '2p'
                        atext = ax.text(pos, ylim[0], hr_text, ha='left', va='bottom')
            if datetime.fromtimestamp(self.last_time).day == dt.day and show_last_close and dt.hour > 16:
                show_last_close = False
                lineitem = ax.axvline(x=pos, color='y', linestyle=(0, (5, 10)))
                artlist.append(lineitem)
                atext = ax.text(pos, ylim[0], '4p', ha='left', va='bottom')
            if (dt-pday).days >= 1:
                deltadays += 1
                pday = dt
            if deltadays >= delta:
                deltadays = 0
                look_for_val = [True, True]
                lineitem = ax.axvline(x=pos, color='b', linestyle='--')
                artlist.append(lineitem)
                atext = ax.text(pos, ylim[0], f' {dt.strftime("%a, %m/%d")}', ha='left', va='bottom')

        self.figdict[sym]['artlist'] = artlist
        plt.draw()
        plt.pause(0.001)

    def getQuoteHistory(self):
        iddict = self.getSymbolList(idDict=True)

        # Convert timestamp to unixsecs: int(timevalues[i].to_pydatetime().timestamp())
        # Convert unixsecs to datetime: datetime.fromtimestamp(unixsecs)
        self.win = None
        for mode in ['d', 'w', 'm']:
            if mode == 'd':
                per = '10d'
                interval = '5m'
            elif mode == 'w':
                per = '3mo'
                interval = '60m'
            elif mode == 'm':
                per = '1y'
                interval = '1d'
            history_AAPL = Ticker('AAPL').history(period=per, interval=interval)
            timevalues = history_AAPL.index.tolist()
            if type(timevalues[0][1]) is Timestamp:
                timevalues = [int(t.to_pydatetime().timestamp()) for sym,t in timevalues]
            else:
                timevalues = [int(datetime.combine(t, datetime.min.time()).timestamp()) for sym,t in timevalues]
            history, histtimes = self.getdbHistory(mode)
            need_update = False
            if len(histtimes) == 0: need_update = True
            elif abs(timevalues[0]-histtimes[0]) > 60 * 60: need_update = True
            elif timevalues[-1] - histtimes[-1] > 60*60*2: need_update = True
            if not need_update:
                continue
            if self.win is None:
                self.win = Toplevel()
            tbox = Text(self.win)
            tbox.pack()
            msg = f'Update Needed for mode {mode}: len(histtimes)={len(histtimes)}\n'
            if len(histtimes) > 0:
                msg += f'Start delta (mins): {abs(timevalues[0]-histtimes[0])/(60*60):.1f}'
                msg += f', End Delta (min): {abs(timevalues[-1]-histtimes[-1])/(60*60):.1f}\n'
            tbox.insert(END, msg)

            self.lockdb = True
            conn = sqlite3.connect(self.dbfile)
            cur = conn.cursor()
            cur.execute(f'DELETE FROM PlotHistory_{mode}')
            conn.commit()
            self.iddict = iddict
            self.symkeys = list(iddict.keys())
            self.sympos = 0
            self.updateoneattime(per, interval, tbox, mode)

    def updateoneattime(self, per, interval, tbox, mode):
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        sym = self.symkeys[self.sympos]
        id = self.iddict[sym]
        history = Ticker(sym).history(period=per, interval=interval)
        tbox.insert(END, sym + ' ')
        if not history.get('close', None) is None:
            timevalues = history.index.tolist()
            values = history['close'].to_list()
            for i, (sym, time) in enumerate(timevalues):
                if type(time) is Timestamp:
                    unixtime = int(time.to_pydatetime().timestamp())
                else:
                    unixtime = int(datetime.combine(time, datetime.min.time()).timestamp())
                cur.execute(f'INSERT INTO PlotHistory_{mode} (stock_id, price, unixtime) VALUES(?,?,?)', (id,values[i],unixtime))
            conn.commit()
        self.sympos += 1
        if self.sympos < len(self.symkeys):
            self.root.after(100, lambda per=per, interval=interval, tbox=tbox, mode=mode: self.updateoneattime(per,interval,tbox,mode))
        else:
            self.lockdb = False
            tbox.insert(END, '\nDone')
            self.win.after(3000, self.win.destroy)

    def getdbHistory(self, mode):
        '''Returns pricedict{[price]}, [unixtime]'''
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        history = {}
        havetimes = False
        if self.symbols is None:
            data = self.getSymbolPrices()
            self.symbols = [d[0] for d in data if d[0] != 'CASH']
        for sym in self.symbols:
            cur.execute(f'SELECT PlotHistory_{mode}.price, unixtime, name FROM PlotHistory_{mode} JOIN StockList ON PlotHistory_{mode}.stock_id = StockList.id WHERE StockList.name=? ORDER BY unixtime', (sym,))
            data = cur.fetchall()
            history[sym] = [d[0] for d in data]
            if not havetimes:
                histtimes = [d[1] for d in data]
                havetimes = True
        return history, histtimes

    def createTables(self):
        mode_options = ['d', 'w', 'm']
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        for mode in mode_options:
            exe_statement = f'CREATE TABLE IF NOT EXISTS "PlotHistory_{mode}" ("stock_id" INTEGER, "price" REAL, "unixtime" INTEGER);'
            cur.execute(exe_statement)
        conn.commit()

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
        '''Returns [(symbol, Price, PreviousClose, Shares, Basis, id)]'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        if sym is None:
            cur.execute('SELECT name, price, PreviousClose, Shares, Basis, id FROM StockList ORDER BY name')
        else:
            cur.execute('SELECT name, price, PreviousClose, Shares, Basis, id FROM StockList WHERE name=?', (sym,))
        stocks = cur.fetchall()
        if stocks is None or len(stocks)==0:
            print(f'Error retrieving data from {self.dbfile}')
        return [(s[0], s[1], s[2], s[3], s[4], s[5]) for s in stocks]


    def getLastDate(self, mode):
        '''Returns unixtime for last data point'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        cur.execute(f'SELECT unixtime FROM PlotHistory_{mode} ORDER BY unixtime DESC LIMIT 1')
        data = cur.fetchall()
        if data is None or len(data) == 0: return 0
        return data[0][0]

    def getMarketStatus(self):
        '''Returns marketState'''
        quote = Ticker('AAPL').price
        unixtime = int(datetime.strptime(quote['AAPL']['regularMarketTime'], '%Y-%m-%d %H:%M:%S').timestamp())
        return (quote['AAPL'].get('marketState', 'Not Available'), unixtime)

# root = Tk()
# main = MainWindow(root)
# root.mainloop()
from tkinter import *
import sqlite3
from yahooquery import Ticker
import utility as util
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np
from matplotlib.widgets import Button as pltButton
import math

class MainWindow():
    def __init__(self, root, sym, callback):
        self.root = root
        self.sym = sym
        self.callback = callback
        self.dbfile = 'stockscroll.sqlite'
        self.symbols = None
        self.updateNeeded = False
        self.artistlist = []
        self.period = 1  # number of days to show, currently up to 7
        self.mode = 'd'
        self.lockdb = False

        self.fig = plt.figure()
        self.fig.canvas.mpl_connect('close_event', self.on_close)
        self.ax = self.fig.subplots()
        plt.subplots_adjust(bottom=0.08)
        plt.plot()
        mngr = plt.get_current_fig_manager()
        mngr.window.wm_geometry('%dx%d+%d+%d' % (1450, 600, 30, 30))
        plt.ion()
        self.add_buttons()
        plt.show()

        self.getQuoteHistory()
        self.plotPort()

        self.updateHistory()
        self.updatePlot()

    def bringtofront(self):
        print(f'Bring {self.sym} to front')

    def on_close(self, event):
        print(event)
        self.callback(self.sym)

    def add_buttons(self):
        x_start = 0.12
        options = [[1,2,5,10], [1,2,5,10]]
        self.day_buttons = []
        for i, mode in enumerate(['d', 'w']):
            bax = plt.axes([x_start, 0.015, 0.04, 0.04])
            bax.axis('off')
            if mode == 'd': ptext = 'Day: '
            elif mode == 'w': ptext = 'Week: '
            bax.text(0.5,0.5,ptext, va='center', ha='center')
            bax_points = [x_start+0.03, 0.015, 0.04, 0.04]
            for opt in options[i]:
                bax = plt.axes(bax_points)
                bax_points[0] += bax_points[1]*2 + 0.01
                self.day_buttons.append(pltButton(bax, f'{opt}{mode}'))
                self.day_buttons[-1].on_clicked(lambda e, per=opt, mode=mode: self.press_button(per, mode))
            x_start += (bax_points[1] * 2 + 0.01) * 4 + 0.03

    def press_button(self, per, mode):
        if self.mode != mode:
            self.mode = mode
            self.getQuoteHistory()
        self.period = per
        self.ax.clear()
        self.plotPort()

    def updatePlot(self):
        delay = 1000*5
        if self.updateNeeded:
            self.ax.clear()
            self.plotPort()
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
            for mode in ['d', 'w']:
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


    def plotPort(self):
        data = self.getSymbolPrices()
        self.symbols = [d[0] for d in data if d[0] != 'CASH']
        total = []
        shareDict = {}
        lastprice = {}
        prevclose = {}
        for sym, price, pclose, shares, _, _ in data:
            if sym == 'CASH':
                cash = util.tryFloat(shares)
            else:
                shareDict[sym] = shares
                lastprice[sym] = price
                prevclose[sym] = pclose

        history, histtimes = self.getdbHistory()
        if len(histtimes) == 0:
            self.getQuoteHistory()
            history, histtimes = self.getdbHistory()
        self.last_time = histtimes[-1]

        if self.period < 10:
            if self.mode == 'd':
                days_list = list(set([datetime.fromtimestamp(ut).day for ut in histtimes]))
                dt = datetime.fromtimestamp(self.last_time)
                day_index = 10 - self.period
                if day_index < 0: day_index = 0
                if day_index >= len(days_list): day_index = len(day_index)-1
                mindate = datetime(dt.year, dt.month, days_list[day_index], 1, 0).timestamp()
            elif self.mode == 'w':
                dt = datetime.fromtimestamp(self.last_time)
                begin_dt = dt - timedelta(days=self.period*7)
                begin_dt = begin_dt.replace(hour=1)
                mindate = begin_dt.timestamp()
            histtimes = [h for h in histtimes if h > mindate]
            for sym in history.keys():
                history[sym] = history[sym][-len(histtimes):]

        # ptotal = cash
        # for sym in self.symbols:
        #     pp = prevclose.get(sym, 0.0)
        #     if pp is None: pp = 0.0
        #     ptotal += pp * shareDict[sym]

        for step in range(len(histtimes)+1):
            stepTotal = cash
            for sym in self.symbols:
                if step >= len(history[sym]):
                    price = lastprice[sym]
                else:
                    price = history[sym][step]
                if price is None: price = 0.0
                stepTotal +=  price * shareDict[sym]
            total.append(stepTotal)

        ptotal = total[0]
        self.ax.plot(total, color='black')
        self.fig.suptitle(f'Total Account Value:{total[-1]:.0f} ({100.0*(total[-1]/ptotal-1):.2f}%)', fontsize=20)

        # Remove previous lines
        for item in self.artistlist:
            item.remove()

        # Add horizontal lines
        minv_per = 100*(min(total)/ptotal-1)
        maxv_per = 100*(max(total)/ptotal-1)
        delta_per = 0.1
        if (maxv_per-minv_per)/delta_per > 9:
            delta_per = 0.5
        while (maxv_per-minv_per)/delta_per > 9:
            delta_per += 0.5
        self.artistlist = []
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        for percent in np.arange(math.floor(minv_per), math.ceil(maxv_per), delta_per):
            yval = ptotal*(1+percent/100.0)
            if yval < ylim[0] or yval > ylim[1]: continue
            if percent < 0.0: color = 'red'
            elif percent > 0.0: color = 'green'
            else: color = 'black'
            lineitem = self.ax.axhline(y=yval, color=color, linestyle='--')
            self.artistlist.append(lineitem)
            atext = self.ax.text(xlim[1], yval, f'  {percent:.1f}%', ha='left', va='center')
            self.artistlist.append(atext)

        # Add vertical lines
        self.ax.get_xaxis().set_ticks([])
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
                        lineitem = self.ax.axvline(x=pos, color='y', linestyle=(0, (5, 10)))
                        self.artistlist.append(lineitem)
                        if v == 12: hr_text = '12p'
                        elif v == 14: hr_text = '2p'
                        atext = self.ax.text(pos, ylim[0], hr_text, ha='left', va='bottom')
            if datetime.fromtimestamp(self.last_time).day == dt.day and show_last_close and dt.hour > 16:
                show_last_close = False
                lineitem = self.ax.axvline(x=pos, color='y', linestyle=(0, (5, 10)))
                self.artistlist.append(lineitem)
                atext = self.ax.text(pos, ylim[0], '4p', ha='left', va='bottom')
            if (dt-pday).days >= 1:
                deltadays += 1
                pday = dt
            if deltadays >= delta:
                deltadays = 0
                look_for_val = [True, True]
                lineitem = self.ax.axvline(x=pos, color='b', linestyle='--')
                self.artistlist.append(lineitem)
                atext = self.ax.text(pos, ylim[0], f' {dt.strftime("%a, %m/%d")}', ha='left', va='bottom')

        plt.draw()
        plt.pause(0.001)

    def getQuoteHistory(self):
        iddict = self.getSymbolList(idDict=True)

        # Convert timestamp to unixsecs: int(timevalues[i].to_pydatetime().timestamp())
        # Convert unixsecs to datetime: datetime.fromtimestamp(unixsecs)
        
        if self.mode == 'd':
            per = '10d'
            interval = '5m'
        elif self.mode == 'w':
            per = '3mo'
            interval = '60m'
        history_AAPL = Ticker('AAPL').history(period=per, interval=interval)
        timevalues = history_AAPL.index.tolist()
        timevalues = [int(t.to_pydatetime().timestamp()) for sym,t in timevalues]
        history, histtimes = self.getdbHistory()
        need_update = False
        if len(histtimes) == 0: need_update = True
        if abs(timevalues[0]-histtimes[0]) > 60 * 60: need_update = True
        if timevalues[-1] - histtimes[-1] > 60*60*2: need_update = True
        if not need_update:
            return
        print(f'len(histtimes)={len(histtimes)}, Start delta (mins): {abs(timevalues[0]-histtimes[0])/(60*60):.1f}, End Delta (hr): {abs(timevalues[-1]-histtimes[-1])/(60*60):.1f}')

        self.lockdb = True
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        cur.execute(f'DELETE FROM PlotHistory_{self.mode}')
        for sym, id in iddict.items():
            history = Ticker(sym).history(period=per, interval=interval)
            print(sym,end=', ')
            if history.get('close', None) is None: continue
            timevalues = history.index.tolist()
            values = history['close'].to_list()
            for i, (sym, time) in enumerate(timevalues):
                unixtime = int(time.to_pydatetime().timestamp())
                cur.execute(f'INSERT INTO PlotHistory_{self.mode} (stock_id, price, unixtime) VALUES(?,?,?)', (id,values[i],unixtime))
            conn.commit()

        conn.commit()
        self.lockdb = False
        print('Done')

    def getdbHistory(self):
        '''Returns pricedict{[price]}, [unixtime]'''
        conn = sqlite3.connect(self.dbfile)
        cur = conn.cursor()
        history = {}
        havetimes = False
        if self.symbols is None:
            data = self.getSymbolPrices()
            self.symbols = [d[0] for d in data if d[0] != 'CASH']
        for sym in self.symbols:
            cur.execute(f'SELECT PlotHistory_{self.mode}.price, unixtime, name FROM PlotHistory_{self.mode} JOIN StockList ON PlotHistory_{self.mode}.stock_id = StockList.id WHERE StockList.name=? ORDER BY unixtime', (sym,))
            data = cur.fetchall()
            history[sym] = [d[0] for d in data]
            if not havetimes:
                histtimes = [d[1] for d in data]
                havetimes = True
        return history, histtimes


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


    def getLastDate(self):
        '''Returns unixtime for last data point'''
        conn = sqlite3.connect(self.dbfile, uri=True)
        cur = conn.cursor()
        cur.execute(f'SELECT unixtime FROM PlotHistory_{self.mode} ORDER BY unixtime DESC LIMIT 1')
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
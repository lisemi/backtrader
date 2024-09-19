import os
import sys
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import tushare as ts

# 由于系统中安装了backtrader包，为了方便调试源码，这里首先是引入当前工程的backtrader源码
# current_dir = os.path.dirname(os.path.abspath(__file__))
# project_package_dir = os.path.abspath(os.path.join(current_dir, '../../'))
# sys.path.insert(0, project_package_dir)
import backtrader as bt


 
def get_data(code='600519',starttime='2017-01-01',endtime='2020-01-01'):
    df = ts.get_k_data(code,start = starttime,end = endtime)
    print(df)
    df.index = pd.to_datetime(df.date)
    df['openinterest'] = 0;
    df = df[['open','high','low','close','volume','openinterest']]
    return df
 
stock_df =get_data()
fromdate = datetime(2017,1,1)
todate = datetime(2020,1,1)
data = bt.feeds.PandasData(dataname=stock_df,fromdate=fromdate,todate=todate)
 
class MyStrategy(bt.Strategy):
    params=(
        ('maperiod',20),
    )
    
    def __init__(self):
        self.order = None
        self.ma = bt.indicators.SimpleMovingAverage(self.datas[0],period=self.params.maperiod)
    def next(self):
        if(self.order):
            return
        if(not self.position):
            if self.datas[0].close[0] > self.ma[0]:
                self.order = self.sell (size=200)
            else:
                if self.datas[0].close[0] < self.ma[0]:
                    self.order = self.buy(size=200)
 
cerebro = bt.Cerebro()
cerebro.adddata(data)
cerebro.addstrategy(MyStrategy)
startcash = 100000
cerebro.broker.setcash(startcash)
cerebro.broker.setcommission(0.0002)
 
s = fromdate.strftime("%Y-%m-%d")
t = todate.strftime("%Y-%m-%d")
print(f"初始资金：{startcash}\n回测时间:{s}-{t}")
cerebro.run()
portval = cerebro.broker.getvalue()
print(f"剩余总资金：{portval}\n回测时间:{s}-{t}")
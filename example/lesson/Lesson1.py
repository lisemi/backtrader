# Lesson1：Backtrader来啦
# link: https://mp.weixin.qq.com/s/7S4AnbUfQy2kCZhuFN1dZw

#%%
import backtrader as bt
import pandas as pd
import datetime

# 实例化 cerebro
cerebro = bt.Cerebro()

# 将指定列解析为日期的方式读取文件内容
daily_price = pd.read_csv("Data/daily_price.csv", parse_dates=['datetime'])  # 510只股票日度行情数据集
trade_info = pd.read_csv("Data/trade_info.csv", parse_dates=['trade_date'])  # 510只股票月末调仓成分股数据集
#%%

# 按股票代码，依次循环传入数据
# 由于回测是多个股票数据，因此需要一个循环把所有股票数据加入到backtrader中。另外这么多股票数据，plot画图也很难
for stock in daily_price['sec_code'].unique():
    # 日期对齐
    data = pd.DataFrame(daily_price['datetime'].unique(), columns=['datetime'])  # 获取回测区间内所有交易日
    df = daily_price.query(f"sec_code=='{stock}'")[
        ['datetime', 'open', 'high', 'low', 'close', 'volume', 'openinterest']]  # 查询股票代码等于stock的股票，并提取括号指定的列
    data_ = pd.merge(data, df, how='left', on='datetime')
    data_ = data_.set_index("datetime")
    # print(data_.dtypes)
    # 缺失值处理：日期对齐时会使得有些交易日的数据为空，所以需要对缺失数据进行填充
    data_.loc[:, ['volume', 'openinterest']] = data_.loc[:, ['volume', 'openinterest']].fillna(0)
    data_.loc[:, ['open', 'high', 'low', 'close']] = data_.loc[:, ['open', 'high', 'low', 'close']].fillna(method='pad')  # 使用前一个有效值来填充 NaN
    data_.loc[:, ['open', 'high', 'low', 'close']] = data_.loc[:, ['open', 'high', 'low', 'close']].fillna(0)
    # 导入数据
    datafeed = bt.feeds.PandasData(dataname=data_, fromdate=datetime.datetime(2019, 1, 2),
                                   todate=datetime.datetime(2021, 1, 28))
    cerebro.adddata(datafeed, name=stock)  # 通过 name 实现数据集与股票的一一对应。因为是多个股票，因此导入时需要对其命名
    print(f"{stock} Done !")

print("All stock Done !")

#%%

# 回测策略
class TestStrategy(bt.Strategy):
    '''选股策略'''
    params = (('maperiod', 15),
              ('printlog', False),)

    def __init__(self):
        self.buy_stock = trade_info  # 保留调仓列表
        # 读取调仓日期，即每月的最后一个交易日，回测时，会在这一天下单，然后在下一个交易日，以开盘价买入
        self.trade_dates = pd.to_datetime(self.buy_stock['trade_date'].unique()).tolist()
        self.order_list = []  # 记录以往订单，方便调仓日对未完成订单做处理
        self.buy_stocks_pre = []  # 记录上一期持仓

    # 判断每个交易日是否为调仓日，如果是调仓日就按调仓权重卖出旧股，买入新股。
    def next(self):
        dt = self.datas[0].datetime.date(0)  # 获取当前的回测时间点
        # 如果是调仓日，则进行调仓操作
        if dt in self.trade_dates:
            print("--------------{} 为调仓日----------".format(dt))
            # 在调仓之前，取消之前所下的没成交也未到期的订单
            if len(self.order_list) > 0:
                for od in self.order_list:
                    self.cancel(od)  # 如果订单未完成，则撤销订单
                self.order_list = []  # 重置订单列表
            # 提取当前调仓日的持仓列表
            buy_stocks_data = self.buy_stock.query(f"trade_date=='{dt}'")
            long_list = buy_stocks_data['sec_code'].tolist()
            print('long_list', long_list)  # 打印持仓列表
            # 对现有持仓中，调仓后不再继续持有的股票进行卖出平仓
            sell_stock = [i for i in self.buy_stocks_pre if i not in long_list]
            print('sell_stock', sell_stock)  # 打印平仓列表
            if len(sell_stock) > 0:
                print("-----------对不再持有的股票进行平仓--------------")
                for stock in sell_stock:
                    data = self.getdatabyname(stock)
                    if self.getposition(data).size > 0:
                        od = self.close(data=data)
                        self.order_list.append(od)  # 记录卖出订单
            # 买入此次调仓的股票：多退少补原则
            print("-----------买入此次调仓期的股票--------------")
            for stock in long_list:
                w = buy_stocks_data.query(f"sec_code=='{stock}'")['weight'].iloc[0]  # 提取持仓权重
                data = self.getdatabyname(stock)
                #  按持仓百分比下单
                order = self.order_target_percent(data=data, target=w * 0.95)  # 为减少可用资金不足的情况，留 5% 的现金做备用
                self.order_list.append(order)

            self.buy_stocks_pre = long_list  # 保存此次调仓的股票列表

        # 交易记录日志（可省略，默认不输出结果）

    def log(self, txt, dt=None, doprint=False):
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()},{txt}')

    # 获得订单状态变化的通知，只要next触发了买卖操作，就会有通知订单消息
    def notify_order(self, order):
        # 未被处理的订单
        if order.status in [order.Submitted, order.Accepted]:
            return
        # 已经处理的订单
        if order.status in [order.Completed, order.Canceled, order.Margin]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, ref:%.0f，Price: %.2f, Cost: %.2f, Comm %.2f, Size: %.2f, Stock: %s' %
                    (order.ref,  # 订单编号
                     order.executed.price,  # 成交价
                     order.executed.value,  # 成交额
                     order.executed.comm,  # 佣金
                     order.executed.size,  # 成交量
                     order.data._name))  # 股票名称
            else:  # Sell
                self.log('SELL EXECUTED, ref:%.0f, Price: %.2f, Cost: %.2f, Comm %.2f, Size: %.2f, Stock: %s' %
                         (order.ref,
                          order.executed.price,
                          order.executed.value,
                          order.executed.comm,
                          order.executed.size,
                          order.data._name))


# 初始资金 100,000,000
cerebro.broker.setcash(100000000.0)
# 佣金，双边各 0.0003
cerebro.broker.setcommission(commission=0.0003)
# 滑点：双边各 0.0001
cerebro.broker.set_slippage_perc(perc=0.005)

# 添加图表设置
cerebro.addobserver(bt.observers.Broker)
cerebro.addobserver(bt.observers.Trades)
cerebro.addobserver(bt.observers.DrawDown)

# 添加分析指标
cerebro.addanalyzer(bt.analyzers.Returns, _name='_Returns')             # 收益率
cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='_TimeReturns')      # 返回收益率时序数据。收益率期间
cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='_AnnualReturn')   # 年化收益率
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='_SharpeRatio',     # 计算年化夏普比率
                    timeframe=bt.TimeFrame.Days,
                    annualize=True, riskfreerate=0)
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='_DrawDown')           # 回撤
cerebro.addanalyzer(bt.analyzers.TimeDrawDown, _name='_TimeDrawDown')   # 期间回撤
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='_TradeAnalyzer') # 交易统计信息，如获胜、失败次数等

# 将编写的策略添加给大脑，别忘了 ！
cerebro.addstrategy(TestStrategy, printlog=True)

# 启动回测
result = cerebro.run()
# 从返回的 result 中提取回测结果
strat = result[0]
# 返回日度收益率序列
daily_return = pd.Series(strat.analyzers._TimeReturns.get_analysis())
# 打印评价指标
print("--------------- 收益期间 -----------------")
print(strat.analyzers._TimeReturns.get_analysis())
print("--------------- 年化收益率 ---------------")
print(strat.analyzers._AnnualReturn.get_analysis())
print("--------------- 最大回撤 -----------------")
print(strat.analyzers._DrawDown.get_analysis())
print('\n')
print('收 益 率: ', strat.analyzers._Returns.get_analysis()['rtot'])
print('夏普比率: ', strat.analyzers._SharpeRatio.get_analysis()['sharperatio'])
print(f'最终资金: {cerebro.broker.getvalue():,.2f} 元')

cerebro.plot(iplot=False, style='candlestick', barup='red', bardown='green', volume=True, volup='red', voldown='green')



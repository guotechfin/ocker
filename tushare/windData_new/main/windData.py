#_*_coding:utf-8_*_
'''
Created on 2015��6��22��

@author: Administrator
'''

import logging
import datetime
import numpy as np
import pandas as pd
from WindPy import w
from datetime import date
from tool import Connection

class StockData():
    '''��ù�Ʊ����'''
    def __init__(self):
        self.initialize()
        self.main()
        
    def initialize(self):
        w.start()
        self.initLogging()
        self.con = Connection().getConnection()
        self.cur = self.con.cursor()
       
       
    def main(self):
        self.historyWindData() # ��ʷ���ݣ����ߺͷ�����
        self.updateWindCode()  # ����A�ɵĴ���
        self.currentWindData() # ÿ�յĸ���
        self.close()
        
#------------------------------------------------------------------------------ init
    def initLogging(self):
        '''��ʼ����־����'''
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)-15s %(lineno)-6d %(funcName)-30s %(message)s',
                            datefmt='%m-%d %H:%M:%S',
                            filename=r'D:\log_windData.txt',
                            filemode='w')
        
#------------------------------------------------------------------------------ historyData
    def historyWindData(self):
        '''�õ���ʷ����'''
        stockCodeList = self.getStockCode() # ��Ʊ����
        fields = {'d':['pre_close','open','high','low','close','volume','amt','pct_chg'],
                  'm':['open','high','low','close','volume','amt','pct_chg']}
        startDate = {'d':'20050101','m':'2014-01-01 09:30:00'}
        endDate   = {'d':datetime.date.today().strftime('%Y%m%d'),'m':datetime.date.today().strftime('%Y-%m-%d')+' 15:00:00'}
        # day
        self.getDayData(stockCodeList,fields['d'],startDate['d'],endDate['d'],option='PriceAdj=F')
        # min
        for period in [5,15,30,60]:
            self.getMinData(stockCodeList,fields['m'],startDate['m'],endDate['m'],period)
        
    def getDayData(self,stockCodeList,fields,startDate,endDate,option):
        '''�����ݵľ���Ļ�ȡ����'''
        for stockCode in stockCodeList:
            print '���������,���a%s' % stockCode
            wsd_data = w.wsd(stockCode,fields,startDate,endDate,option)
            if wsd_data.ErrorCode==0: # ���سɹ�
                stockDate = wsd_data.Times
                dateList = [date.strftime("%Y-%m-%d") for date in stockDate]
                stockDataDict = {'stockCode':stockCode,'date':dateList}
                for i in range(len(fields)):
                    stockDataDict[fields[i]] = wsd_data.Data[i]
                stockData = pd.DataFrame(stockDataDict,columns=['stockCode','date']+fields,index=dateList).dropna() # ֻҪ��ȱʧ�����ݾ�ɾ����һ�У���֤������Ϊ�ɾ�
                stockData['pct_chg'] = stockData['pct_chg'] / 100 # ���Ƿ���Ϊʵ���Ƿ�����ѯ�������ǰٷֱ����ݣ�
                # ���뵽��������
                sql = "insert ignore into stockdata_day values(" + "%s,"*(len(fields)+1)+"%s)" 
                self.cur.executemany(sql,tuple(stockData.values.tolist()))
                self.con.commit()
            else:
                logging.info('ERROR-%s-day�������dʧ�����e�`���a�飺%s' % (stockCode,wsd_data.ErrorCode))
                
                
    def getMinData(self,stockCodeList,fields,startDate,endDate,period):
        '''�����ߵľ���Ļ�ȡ����'''
        option = 'BarSize=%s;PriceAdj=F' % period
        for stockCode in stockCodeList:
            print '���%s ��������,���a%s' % (period,stockCode)
            wsi_data = w.wsi(stockCode,fields,startDate,endDate,option)
            if wsi_data.ErrorCode==0: # ���سɹ�
                stockDate = wsi_data.Times
                timeList = [time.strftime("%Y-%m-%d %H-%M-%S") for time in stockDate]
                stockDataDict = {'stockCode':stockCode,'time':timeList}
                for i in range(len(fields)):
                    stockDataDict[fields[i]] = wsi_data.Data[i]
                stockData = pd.DataFrame(stockDataDict,columns=['stockCode','time']+fields,index=timeList).dropna() # ֻҪ��ȱʧ�����ݾ�ɾ����һ�У���֤������Ϊ�ɾ�
                stockData['pct_chg'] = stockData['pct_chg'] / 100 # ���Ƿ���Ϊʵ���Ƿ�����ѯ�������ǰٷֱ����ݣ�
                # ���뵽��������
                sql = "insert ignore into stockData_%smin" % period + " values("+"%s,"*(len(fields)+1)+"%s)"   
                self.cur.executemany(sql,tuple(stockData.values.tolist()))
                self.con.commit()
            else:
                logging.info('ERROR-%s�vʷ���%smin�������dʧ��' % (stockCode,period))
    
    
    def updateWindCode(self):
        '''���¹�Ʊ����'''
        today = date.today().strftime('%Y%m%d')
        field = 'wind_code,sec_name' # �ֶ�������Ʊ����͹�Ʊ����
        sector = 'ȫ��A��'
        option = 'date=%s;sector=%s;field=%s' % (today,sector,field)
        
        wset_data = w.wset('SectorConstituent',option)
        if wset_data.ErrorCode == 0:
            stockCodeData = zip(wset_data.Data[0],wset_data.Data[1]) # ����ֵdata[0],data[1]�ֱ�Ϊ���������
            sql = "delete from stockCode"
            self.cur.execute(sql)
            self.con.commit()
            print 'ɾ���������'
            # ���뵽���ݿ���
            sql = "insert ignore into stockCode values(%s,%s)"
            self.cur.executemany(sql,tuple(stockCodeData))
            self.con.commit()
        else:
            logging.info('ERROR-��Ʊ������´���')
        print '���´������'
        
#------------------------------------------------------------------------------ currentData
    def currentWindData(self):
        '''��������'''
        stockCodeList = self.getStockCode()
        reRightCode = self.getUpdateCode(stockCodeList)
        self.reRightData(reRightCode) # ��Ȩ����
        self.insertTodayData(stockCodeList) # �����������
        
    def getUpdateCode(self,stockCodeList):
        '''�õ�ֱ�Ӳ���͸�Ȩ�Ĵ���'''
        reRightCode = [] # ��Ҫ�͙�Ĺ�Ʊ
        # �õ����ݿ�������һ������̼�
        closeList = []
        for code in stockCodeList:
            sql = "select close from stockData_day where stockCode = %s order by date desc limit 1" 
            self.cur.execute(sql,code)
            result = self.cur.fetchone()
            if not result:
                closeList.append(0.0)
            else:
                closeList.append(result[0])
        # ���ҽ���Ĕ���
        fields = ['pre_close']
        today = datetime.date.today().strftime('%Y%m%d') #���������
        option = 'showblank=0.0;PriceAdj=F' # Ҫ�M��ǰ�͙�̎��
        wsd_data = w.wsd(stockCodeList,fields,today,today,option)
        if wsd_data.ErrorCode==0: # ���سɹ�
            stockData = wsd_data.Data[0]
            
        ifEqualList = (np.array(stockData) == np.array(closeList))
        for i in range(len(ifEqualList)):
            if not ifEqualList[i]:
                rate = (stockData[i] - closeList[i]) / closeList[i]
                reRightCode.append([stockCodeList[i],rate])
                
        print '��Ҫ��Ȩ������Ϊ'
        print len(reRightCode)
        print '��Ҫ��Ȩ�Ĺ�Ʊ����Ϊ��'
        print reRightCode
        logging.info('��Ҫ��Ȩ�Ĺ�Ʊ����Ϊ��%s' % reRightCode)
        return reRightCode
    
    def reRightData(self,reRightCode):
        '''��Ȩ����'''
        print '��ʼ��Ȩ����'
        code = [record[0] for record in reRightCode]
        rate = [record[1] for record in reRightCode]
        
        paraList = []
        for i in range(len(reRightCode)):
            paraList.append((rate[i],)*6 + (code[i],))
             
        sql = 'update stockData_day set '+\
        'pre_close=pre_close*(1+%s),open=open*(1+%s),high=high*(1+%s),low=low*(1+%s),close=close*(1+%s),amt=amt*(1+%s)' +\
         " where stockCode=%s" 
        self.cur.executemany(sql,paraList)
        self.con.commit()
        print '���߸�Ȩ���'
        
        paraList = []
        for i in range(len(reRightCode)):
            paraList.append((rate[i],)*5 + (code[i],))
            
        for period in [5,15,30,60]:
            sql = 'update stockData_%smin ' % period + \
            'set open=open*(1+%s),high=high*(1+%s),low=low*(1+%s),close=close*(1+%s),amt=amt*(1+%s)' + \
            " where stockCode=%s" 
            self.cur.executemany(sql,paraList)
            self.con.commit()
        print '�����߸�Ȩ���'
        
    
    def insertTodayData(self,stockCodeList):
        '''���뵱�������'''
        fields = {'d':['pre_close','open','high','low','close','volume','amt','pct_chg'],
                  'm':['open','high','low','close','volume','amt','pct_chg']}
        startDate = {'d':datetime.date.today().strftime('%Y%m%d'),'m':datetime.date.today().strftime('%Y-%m-%d')+' 09:30:00'}
        endDate   = {'d':datetime.date.today().strftime('%Y%m%d'),'m':datetime.date.today().strftime('%Y-%m-%d')+' 15:00:00'}
        # day
        self.getDayData(stockCodeList,fields['d'],startDate['d'],endDate['d'],option='PriceAdj=F')
        # min
        for period in [5,15,30,60]:
            self.getMinData(stockCodeList,fields['m'],startDate['m'],endDate['m'],period)
        
        
    def getStockCode(self):
        '''��ù�Ʊ����'''
        sql = 'select distinct stockCode from stockCode'
        self.cur.execute(sql)
        stockCodeList = []
        for code in self.cur.fetchall():
            stockCodeList.append(code[0])
        return stockCodeList
    
    
    def close(self):
        '''�P�]������'''
        self.con.close()
        self.cur.close()
        
if __name__ == '__main__':
    
    stockData = StockData()
    

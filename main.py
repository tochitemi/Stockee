import os
import logging
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from util.sessions import Session
from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import mail

import urllib

# A Model for a User
class User(db.Model):
    account = db.StringProperty()
    password = db.StringProperty()
    name = db.StringProperty()
    email = db.StringProperty()
    created = db.DateTimeProperty(auto_now=True)

# A Model for a Stock
class Stock(db.Model):
    user = db.StringProperty()
    ticker = db.StringProperty()
    shares = db.StringProperty()

class Notification(db.Model):
    enduser = db.StringProperty()
    minval = db.StringProperty()

# A helper to do the rendering and to add the necessary
# variables for the _base.htm template
def doRender(handler, tname = 'index.htm', values = { }):
    temp = os.path.join(os.path.dirname(__file__),'templates/' + tname)
    if not os.path.isfile(temp):
        return False

    # Make a copy of the dictionary and add the path and session
    newval = dict(values)
    newval['path'] = handler.request.path
    if 'username' in session:
        newval['username'] = session['username']

    outstr = template.render(temp, newval)
    handler.response.out.write(outstr)
    return True


def get_price(symbol):
    url = 'http://finance.yahoo.com/d/quotes.csv?s=%s&f=%s' % (symbol, 'l1')
    return urllib.urlopen(url).read().strip().strip('"')

def get_name(symbol):
    url = 'http://finance.yahoo.com/d/quotes.csv?s=%s&f=%s' % (symbol, 'n')
    return urllib.urlopen(url).read().strip().strip('"')

class LoginHandler(webapp.RequestHandler):

    def get(self):
            doRender(self, 'login.html')

    def post(self):
        acct = self.request.get('account')
        pw = self.request.get('password')
        logging.info('Checking account='+acct+' pw='+pw)

        session.delete_item('username')
        session.delete_item('userkey')

        if pw == '' or acct == '':
            doRender(
                    self,
                    'login.html',
                    {'error' : 'Please specify Account and Password'} )
            return

        que = db.Query(User)
        que = que.filter('account =',acct)
        que = que.filter('password = ',pw)

        results = que.fetch(limit=1)

        for each in results:
            useremail = each.email 
    
        if len(results) > 0 :
            user = results[0]
            session['userkey'] = user.key()
            session['username'] = acct
            session['useremail'] = useremail
            doRender(self,'stock.htm',{} )
        else:
            doRender(
                     self,
                     'login.html',
                     {'error' : 'Invalid Credentials'} )

class ApplyHandler(webapp.RequestHandler):

    def get(self):
        doRender(self, 'applyscreen.htm')

    def post(self):
        name = self.request.get('name')
        acct = self.request.get('account')
        pw = self.request.get('password')
        email = self.request.get('email')

        if pw == '' or acct == '' or name == '':
            doRender(
                     self,
                     'applyscreen.htm',
                     {'error' : 'Please fill in all fields'} )
            return

        if email == '':
            doRender(
                     self, 
                     'applyscreen.htm',
                     {'error' : 'Please enter a valid email to receive important account alerts.'} )
            return

        # Check if the user already exists
        que = db.Query(User).filter('account =',acct)
        results = que.fetch(limit=1)

        if len(results) > 0 :
            doRender(
                     self,
                     'applyscreen.htm',
                     {'error' : 'Account Already Exists'} )
            return
          
        # Create the User object and log the user in
        newuser = User(name=name, account=acct, password=pw, email=email);
        pkey = newuser.put();
        session['username'] = acct
        session['userkey'] = pkey
        session['useremail'] = email
        doRender(self,'stock.htm',{ })

class LogoutHandler(webapp.RequestHandler):

    def get(self):
        session.delete_item('username')
        session.delete_item('userkey')
        doRender(self, 'index.htm')

class StockHandler(webapp.RequestHandler):
    def get(self):
        # que = db.Query(Stock)
        # results = que.filter('user = ', session['username']).fetch(limit=3)
        # stockTable = []
        # for eachstk in results:
        #     stockentry = {}
        #     stockentry['name']=get_name(eachstk.ticker)
        #     stockTable.append(stockentry)
        # doRender(self, 'stocklist.htm',{'stock_list':stockTable})
        doRender(self, 'stock.htm',{})

    def post(self):
        stksymbol = self.request.get('ticker')
        numshares = self.request.get('shares')
        price = get_price(stksymbol)
        if price == '0.00':
            self.response.out.write('Stock symbol does not exist')
            return 
        if is_number(numshares):
            numshares=int(float(numshares));
            if numshares == 0:
                self.response.out.write('Please enter a valid number of shares')
                return
        else:
            self.response.out.write('Invalid Input')
            return 
        
        acct = session['username']
        
        que = db.Query(Stock).filter('user =',session['username']).filter('ticker =',stksymbol)
        results = que.fetch(limit=1)
        if len(results) > 0 :
            results[0].shares=str(numshares)
            results[0].put()
            self.response.out.write(' Existing Stock updated')
        else:
            newstock = Stock(user=acct,ticker=stksymbol,shares=str(numshares))
            newstock.put()
            self.response.out.write('New Stock Added to your Portfolio')

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class MinValHandler(webapp.RequestHandler):
    def post(self):
        val = self.request.get('mini')

        if is_number(val):
            val=int(float(val));
            if val <= 0:
                self.response.out.write('Please enter a valid minimum value')
                return
        else:
            self.response.out.write('Invalid Input')
            return 

        acct2 = session['username']
        
        que = db.Query(Notification).filter('enduser =',session['username'])
        results = que.fetch(limit=1)
        if len(results) > 0 :
            results[0].minval=str(val)
            results[0].put()
            self.response.out.write('Minimum Value Updated')
        else:
            newval = Notification(enduser=acct2, minval=str(val))
            newval.put()
            self.response.out.write('Minimum Value Registered')

class DeleteHandler(webapp.RequestHandler):
    def post(self):
        stksymbol = self.request.get('ticker')
        acct = session['username']
        que = db.Query(Stock).filter('user =',session['username']).filter('ticker =',stksymbol)
        results = que.fetch(limit=1)
        if len(results) > 0 :
            # results[0].shares=str(numshares)
            results[0].delete()
            self.response.out.write('Existing Stock Deleted')
        else:
            self.response.out.write('You dont have this stock on your Portfolio')

class StockListHandler(webapp.RequestHandler):
    def get(self):
        que = db.Query(Stock)
        results = que.filter('user = ', session['username']).fetch(limit=3)
        stockTable = []
        for eachstk in results:
            stockentry = {}
            stockentry['ticker']=eachstk.ticker
            stockentry['shares']=eachstk.shares
            stockentry['price']=get_price(eachstk.ticker)
            stockentry['name']=get_name(eachstk.ticker)
            stockTable.append(stockentry)
        doRender(self, 'stocklist.htm',{'stock_list':stockTable})


class OneStockHandler(webapp.RequestHandler):
    def get(self):
        que = db.Query(Stock)
        take = que.filter('user = ', session['username'])
        results = take.fetch(limit=1)
        stockTable = []
        for eachstk in results:
            stockentry = {}
            getoneticker = eachstk.ticker
            stockentry['ticker']=eachstk.ticker
            #stockentry['shares']=eachstk.shares
            #stockentry['price']=get_price(eachstk.ticker)
            stockTable.append(stockentry)
        #doRender(self, 'stock.htm',{'variable':getoneticker})
        self.response.out.write(str(getoneticker))

# class PortfolioHandler(webapp.RequestHandler):
# 	def get(self):
# 		logging.info("get for portfolio")
# 		# email = session['useremail']
# 		que = db.Query(Stock)
# 		results = que.filter('user = ', session['username'])
# 		logging.info("portfolio results:"+str(results))
# 		portTotal = 0.0
# 		for eachstk in results:
# 			price = get_price(eachstk.ticker)
# 			value = float(price) * float(eachstk.shares)
# 			portTotal = portTotal + value
# 			logging.info("Stock:"+str(eachstk.ticker)+" Price:"+str(price)+ " value:"+str(value))
# 		# if portTotal > 1000:
# 		#     message = mail.EmailMessage(sender="Stockee Support <tochitemi@gmail.com>", subject="Your total portfolio value is low")
# 		#     message.to = email
# 		#     message.body = """
# 		#     Dear Albert:
# 		#     """
# 		#     message.send()
# 		#     # return
# 		logging.info("portTotal Value:"+str(portTotal))
# 		doRender(self, 'portfolio.htm',{'portfolio':portTotal})

class PortfolioHandler(webapp.RequestHandler):
    def get(self):
        logging.info("get for portfolio")
        # useremail = session['useremail']
        que2 = db.Query(Notification)
        results2 = que2.filter('enduser = ', session['username'])
        results2 = que2.fetch(limit=1)
        takevalue = 0.0
        if len(results2) > 0 :
            takevalue = float(results2[0].minval)
        else:
            takevalue = takevalue

        que = db.Query(Stock)
        results = que.filter('user = ', session['username'])
        logging.info("portfolio results:"+str(results))
        portTotal = 0.0
        for eachstk in results:
            price = get_price(eachstk.ticker)
            value = float(price) * float(eachstk.shares)
            portTotal = portTotal + value
            logging.info("Stock:"+str(eachstk.ticker)+" Price:"+str(price)+ " value:"+str(value))
        logging.info("portTotal Value:"+str(portTotal))
        # if portTotal < 1000:
        #     message = mail.EmailMessage(sender="Stockee Support <tochitemi@gmail.com>", subject="Your total portfolio value is low")
        #     message.to = str(useremail)
        #     message.body = """
        #     Dear Big Ben:
        #     """
        #     message.send()

        if float(takevalue) > portTotal:
            doRender(self, 'portfolio.htm',{'portfolio': portTotal, 'minvalue': '*Your total portfolio value has gone below your set minimum value'})
            return
        else:
            doRender(self, 'portfolio.htm',{'portfolio':portTotal})
            return


class ProfileHandler(webapp.RequestHandler):
	def get(self):
		que = db.Query(User)
		user_list = que.fetch(limit=100)
		logging.info("user_list:"+str(user_list))
		doRender(self, 'profile.htm', {'user_list': user_list})

class MainHandler(webapp.RequestHandler):

    def get(self):
        if doRender(self,self.request.path) :
            return
        doRender(self,'index.htm')


session = Session()
app = webapp.WSGIApplication([
                          ('/login', LoginHandler),
                          ('/apply', ApplyHandler),
                          ('/stock', StockHandler),
                          ('/delete', DeleteHandler),
                          ('/minimum', MinValHandler),
                          ('/onestock', OneStockHandler),
			              ('/profile', ProfileHandler),
			              ('/portfolio', PortfolioHandler),
                          ('/stocklist', StockListHandler),
                          ('/logout', LogoutHandler),
                          ('/.*', MainHandler)],
                         debug=False)

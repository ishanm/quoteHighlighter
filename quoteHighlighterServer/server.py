from wsgiref.simple_server import make_server
from urlparse import parse_qs
from cgi import FieldStorage
from Cookie import SimpleCookie

class ServerException(Exception):
    def __init__(self, message):
        self.message = message
        
    def __str__(self):
        return self.message
    
class Request(object):
    def __init__(self, environ):
        self.environ = environ
        self.method = self.environ['REQUEST_METHOD'].upper()
        self.pathInfo = self.environ.get('PATH_INFO', '/')
        self.queryString = self.environ['QUERY_STRING']
        self._get = None
        self._post = None
        self._body = None
        self._cookie = None

    @property
    def GET(self):
        """
        Parse the query string to create a dictionary for the GET parameters
        """
        # Don't check for method type here like we do in POST as it could be a
        # POST method and still have query parameters
        
        if self._get is None:
            self._get = parse_qs(self.queryString)
            # parse_qs returns the values in a list. If there's just one value
            # we don't need it in a list
            for key, val in self._get:
                if len(val) == 1:
                    self._get[key] = val[0]
        return self._get
    
    @property
    def POST(self):
        """
        Parse the body of the request to create a dictionary for POST data
        """
        
        if self.method != "POST":
            raise ServerException("Request method was not POST")

        self.POST = {}
        fs = FieldStorage(fp=self.environ['wsgi.input'], environ=self.environ)

        for key in fs.keys():
            val = fs[key]
            if type(val) == list:
                self.POST[key] = [i.value for i in val]
            else:
                self.POST[key] = val.value
        
        return self.POST
                    
    @property
    def body(self):
        """
        Returns the contents of the body of the request as a string
        """
        if 'CONTENT_LENGTH' not in self.environ or int(self.environ['CONTENT_LENGTH']) == 0:
            return ""
        
        return self.environ['wsgi.input'].read(int(self.environ['CONTENT_LENGTH']))
    
    @property
    def cookie(self):
        """
        Returns a dictionary of cookies, without any additional information like
        the expiry time, secure, version etc. Just the key, value pairs
        """
        if 'HTTP_COOKIE' not in self.environ:
            return {}
        
        simpleCookie = SimpleCookie(self.environ['HTTP_COOKIE'])
        keyVals = [(key, morsel.value) for key, morsel in simpleCookie.items()]
        return dict(keyVals)

class Response(object):
    def __init__(self):
        self.body = None
        self._cookies = SimpleCookie()
        self._headers = {}
    
    @property
    def cookies(self):
        """
        Returns a SimpleCookie object for the user to manipulate. When the response
        is being sent, this SimpleCookie will be converted to the appropriate header
        """
        return self._cookies
    
    def set_cookie(self, key, val, **kargs):
        """
        Sets a cookie and it's additional info like path, expires, etc
        """
        self.cookies[key] = val
        for i, j in kargs.items():
            self.cookies[key][i] = j
            
    @property
    def headers(self):
        """
        This returns the headers of the response as a dict (exluding the cookies)
        """
        return self._headers
    
    @headers.setter
    def headers(self, key, val):
        self._headers[key] = val
        
    def combine_cookies_headers(self):
        """
        This method combines the cookies and non-cookie headers and returns
        the list of tuples to be returned by the WSGI app
        """
        cookies = [('Set-Cookie', morsel.OutputString()) for key, morsel in self.cookies.items()]
        return self.headers.items() + cookies
    
viewMap = {}

def addView(path, view):
    viewMap[path] = view
    
def getView(path):
    return viewMap[path]

class DefaultApp():
    def __init__(self):
        self.request = None
        self.response = None
        
    def __call__(self, environ, start_response):
        self.request = Request(environ)

        currentPath = environ['PATH_INFO']
        view = getView(currentPath)
        self.response = view(self.request)
        
        start_response('200 OK', self.response.combine_cookies_headers())
        return self.response.body



def serve(host='127.0.0.1', port=8080):
    httpd = make_server(host, port, DefaultApp())
    print "Starting server on host %s, port %d" % (host, port)
    httpd.serve_forever()

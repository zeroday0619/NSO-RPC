# Created by Deltaion Lee (MCMi460) on Github

import requests
import json
import uuid
import time
import sys
import webbrowser
import base64
import os
import hashlib
import re
import pickle
import logging
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def GET_NSO_APP_VERSION():
    page = requests.get("https://apps.apple.com/us/app/nintendo-switch-online/id1234806557")
    soup = BeautifulSoup(page.text, 'html.parser')
    elt = soup.find("p", {"class": "whats-new__latest__version"})
    ver = elt.get_text().replace("Version ","").strip()
    return ver


client_id = '71b963c1b7b6d119'
version = "unknown"
nsoAppVersion = "2.1.1"
languages = [ # ISO Language codes
'en-US',
'es-MX',
'fr-CA',
'ja-JP',
'en-GB',
'es-ES',
'fr-FR',
'de-DE',
'it-IT',
'nl-NL',
'ru-RU',
'ko-KR',
]

def log(info, time = time.time()):
    path = os.path.expanduser('~/Documents/NSO-RPC')
    if not os.path.isdir(path):
        os.mkdir(path)
    with open(os.path.join(path, 'logs.txt'), 'a') as file:
        file.write('%s: %s\n' % (time, info))
    return info

class API():
    def __init__(self, session_token, user_lang):
        self.headers = {
            'X-ProductVersion': '2.1.1',
            'X-Platform': 'iOS',
            'User-Agent': 'Coral/2.0.0 (com.nintendo.znca; build:1489; iOS 15.3.1) Alamofire/5.4.4',
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
            'Host': 'api-lp1.znc.srv.nintendo.net',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
        }

        self.user_lang = user_lang
        self.tokenResponse = Nintendo(session_token, self.user_lang).getServiceToken()
        self.id_token = self.tokenResponse['id_token']
        self.accessToken = self.tokenResponse['access_token']
        self.guid = str(uuid.uuid4())

        self.url = 'https://api-lp1.znc.srv.nintendo.net'

        self.userInfo = UsersMe(self.accessToken, self.user_lang).get()
        self.login = {
            'login': None,
            'time': 0,
        }

        self.friends = []

        path = os.path.expanduser('~/Documents/NSO-RPC')
        if not os.path.isdir(path):
            os.mkdir(path)
        with open(os.path.join(path, 'private.txt'), 'w') as file:
            file.write(json.dumps({
                'session_token': session_token,
                'user_lang': self.user_lang,
            }))

    def makeRequest(self, route):
        return requests.post(self.url + route, headers = self.headers)

    def updateLogin(self):
        path = os.path.expanduser('~/Documents/NSO-RPC/tempToken.txt')
        if os.path.isfile(path):
            with open(path, 'rb') as file:
                self.login = pickle.loads(file.read())
                self.headers['Authorization'] = 'Bearer %s' % self.login['login'].account['result'].get('webApiServerCredential').get('accessToken')
                log('Login from file')
        if time.time() - self.login['time'] < 7170:
            return
        login = Login(self.userInfo, self.user_lang, self.accessToken, self.guid)
        login.loginToAccount()
        self.headers['Authorization'] = 'Bearer %s' % login.account['result'].get('webApiServerCredential').get('accessToken') # Add authorization token
        self.login = {
            'login': login,
            'time': time.time(),
        }
        with open(path, 'wb') as file:
            file.write(pickle.dumps(self.login))

    def getSelf(self):
        route = '/v3/User/ShowSelf'

        response = self.makeRequest(route)
        logger.info(response.json())
        self.user = User(response.json()['result'])

    def getFriends(self):
        list = FriendList()
        list.populateList(self)
        self.friends = list.friendList

class Nintendo():
    def __init__(self, sessionToken, userLang):
        self.headers = {
            'User-Agent': 'Coral/2.0.0 (com.nintendo.znca; build:1489; iOS 15.3.1) Alamofire/5.4.4',
            'Accept': 'application/json',
            'Accept-Language': userLang,
            'Accept-Encoding': 'gzip, deflate',
        }
        self.body = {
            'client_id': client_id,
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer-session-token',
            'session_token': sessionToken,
        }

        self.url = 'https://accounts.nintendo.com'

    def getServiceToken(self):
        route = '/connect/1.0.0/api/token'
        response = requests.post(self.url + route, headers = self.headers, json = self.body)
        return response.json()

class UsersMe():
    def __init__(self, accessToken, userLang):
        self.headers = {
            'User-Agent': 'Coral/2.0.0 (com.nintendo.znca; build:1489; iOS 15.3.1) Alamofire/5.4.4',
            'Accept': 'application/json',
            'Accept-Language': userLang,
            'Authorization': 'Bearer %s' % accessToken,
            'Host': 'api.accounts.nintendo.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip',
        }
        self.url = 'https://api.accounts.nintendo.com'

    def get(self):
        route = '/2.0.0/users/me'

        response = requests.get(self.url + route, headers = self.headers)
        logger.info(response.json())
        return response.json()


class s2s():
    def __init__(self, id_token, timestamp):
        log('Login from Flapg/s2s')
        self.headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'NSO-RPC/%s' % version,
        }
        self.body = {
            'naIdToken': id_token,
            'timestamp': timestamp,
        }
        self.url = 'https://elifessler.com'

    def getHash(self):
        route = '/s2s/api/gen2'
        response = requests.post(self.url + route, headers = self.headers, data = self.body)
        return response.json()['hash']

class Flapg():
    def __init__(self, id_token, timestamp, guid):
        self.headers = {
            'x-token': id_token,
            'x-time': str(timestamp),
            'x-guid': guid,
            'x-hash': s2s(id_token, timestamp).getHash(),
            'x-ver': '3',
            'x-iid': 'nso',
        }

        self.url = 'https://flapg.com'

    def get(self):
        route = '/ika2/api/login?public'

        response = requests.get(self.url + route, headers = self.headers)
        logger.info(response.json())
        return response.json()['result']

class Login():
    def __init__(self, userInfo, userLang, accessToken, guid):
        self.headers = {
            'Host': 'api-lp1.znc.srv.nintendo.net',
            'Accept-Language': userLang,
            'User-Agent': 'com.nintendo.znca/' + nsoAppVersion + ' (Android/12.1.2)',
            'Accept': 'application/json',
            'X-ProductVersion': '2.1.1',
            'Content-Type': 'application/json; charset=utf-8',
            'Connection': 'Keep-Alive',
            'Authorization': 'Bearer',
            'X-Platform': 'Android',
            'Accept-Encoding': 'gzip'
        }

        self.url = 'https://api-lp1.znc.srv.nintendo.net'
        self.timestamp = int(time.time())
        self.guid = guid

        self.userInfo = userInfo
        self.accessToken = accessToken

        self.flapg = Flapg(self.accessToken, self.timestamp, self.guid).get()

        self.account = None

    def loginToAccount(self):
        route = '/v3/Account/Login'
        body = {
            'parameter': {
                'f': self.flapg['f'],
                'naIdToken': self.flapg['p1'],
                'timestamp': self.flapg['p2'],
                'requestId': self.flapg['p3'],
                'naCountry': self.userInfo['country'],
                'naBirthday': self.userInfo['birthday'],
                'language': self.userInfo['language'],
            },
        }
        response = requests.post(self.url + route, headers = self.headers, json = body)
        self.account = response.json()
        print(self.account)
        return self.account

class User():
    def __init__(self, f):
        self.id = f.get('id')
        self.nsaId = f.get('nsaId')
        self.imageUri = f.get('imageUri')
        self.image = None
        self.name = f.get('name')
        self.supportId = f.get('supportId')
        self.isChildRestricted = f.get('isChildRestricted')
        self.etag = f.get('etag')
        self.links = f.get('links')
        self.permissions = f.get('permissions')
        self.presence = Presence(f.get('presence'))

    def description(self):
        return ('%s (id: %s, nsaId: %s):\n' % (self.name, self.id, self.nsaId)
        + '   - Profile Picture: %s\n' % self.imageUri
        + '   - Status: %s\n' % self.presence.description()
        )

class Friend(User):
    def __init__(self, f):
        super().__init__(f)
        self.isFriend = f.get('isFriend')
        self.isFavoriteFriend = f.get('isFavoriteFriend')
        self.isServiceUser = f.get('isServiceUser')
        self.friendCreatedAt = f.get('friendCreatedAt')

    def description(self):
        return ('%s (id: %s, nsaId: %s):\n' % (self.name, self.id, self.nsaId)
        + '   - Profile Picture: %s\n' % self.imageUri
        + '   - Is Favorite: %s\n' % self.isFavoriteFriend
        + '   - Friend Creation Date: %s\n' % self.friendCreatedAt
        + '   - Status: %s\n' % self.presence.description()
        )

class FriendList():
    def __init__(self):
        self.route = '/v3/Friend/List' # Define API route

        self.friendList = [] # List of Friend object(s)

    def populateList(self, API:API):
        response = API.makeRequest(self.route)
        arr = response.json()
        print(arr)
        if arr is None:
            return
        arr = arr["result"]["friends"]
        self.friendList = [ Friend(friend) for friend in arr ]
    
    def my_presence(self):
        for friend in self.friendList:
            if friend.name == "0day0619":
                return friend.presence
        return None

class Presence():
    def __init__(self, f):
        logger.debug('Initializing Presence')
        self.state = f.get('state')
        self.updatedAt = f.get('updatedAt')
        self.logoutAt = f.get('logoutAt')
        self.game = Game(f.get('game'))
        logger.info('Status: %s' % self.state)
        logger.info('Last Updated: %s' % self.updatedAt)
        logger.info('Logout: %s' % self.logoutAt)
        logger.info('Game: %s' % self.game.description())

    def description(self):
        return ('%s (updatedAt: %s, logoutAt: %s)\n' % (self.state, self.updatedAt, self.logoutAt)
        + '   - Game: %s' % self.game.description()
        )

class Game():
    def __init__(self, f):
        logger.debug('Initializing Game')
        logger.debug(f)
        self.name = f.get('name')
        self.imageUri = f.get('imageUri')
        self.shopUri = f.get('shopUri')
        self.totalPlayTime = f.get('totalPlayTime')
        self.firstPlayedAt = f.get('firstPlayedAt')
        self.sysDescription = f.get('sysDescription')
        logger.info('Game: %s' % self.name)
        logger.info('Total Play Time: %s' % self.totalPlayTime)
        logger.info('First Played: %s' % self.firstPlayedAt)
        logger.info('System Description: %s' % self.sysDescription)


    def description(self):
        return ('%s (sysDescription: %s)\n' % (self.name, self.sysDescription)
        + '   - Game Icon: %s\n' % self.imageUri
        + '   - Shop Uri: %s\n' % self.shopUri
        + '   - Total Play Time: %s\n' % self.totalPlayTime
        + '   - First Played At: %s' % self.firstPlayedAt
        )

class Session():
    def __init__(self):
        self.headers = {
            'Accept-Encoding': 'gzip',
            'User-Agent': 'OnlineLounge/%s NASDKAPI Android' % nsoAppVersion,
        }
        self.Session = requests.Session()

    def login(self, receiveInput):
        state = base64.urlsafe_b64encode(os.urandom(36))
        verify = base64.urlsafe_b64encode(os.urandom(32))
        authHash = hashlib.sha256()
        authHash.update(verify.replace(b'=', b''))
        authCodeChallenge = base64.urlsafe_b64encode(authHash.digest())

        url = 'https://accounts.nintendo.com/connect/1.0.0/authorize'
        params = {
            'client_id': client_id,
            'redirect_uri': 'npf%s://auth' % client_id,
            'response_type': 'session_token_code',
            'scope': 'openid user user.birthday user.mii user.screenName',
            'session_token_code_challenge': authCodeChallenge.replace(b'=', b''),
            'session_token_code_challenge_method': 'S256',
            'state': state,
            'theme': 'login_form'
        }
        response = self.Session.get(url, headers = self.headers, params = params)

        webbrowser.open(response.history[0].url)
        tokenPattern = re.compile(r'(eyJhbGciOiJIUzI1NiJ9\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*)')
        code = tokenPattern.findall(receiveInput())[0]

        return code, verify

    def inputManually(self):
        return input('After logging in, please copy the link from \'Select this account\' and enter it here:\n')

    def run(self, code, verify):
        url = 'https://accounts.nintendo.com/connect/1.0.0/api/session_token'
        headers = self.headers
        headers.update({
            'Accept-Language': 'en-US',
            'Accept':          'application/json',
            'Content-Type':    'application/x-www-form-urlencoded',
            'Content-Length':  '540',
            'Host':            'accounts.nintendo.com',
            'Connection':      'Keep-Alive',
        })
        body = {
            'client_id': client_id,
            'session_token_code': code,
            'session_token_code_verifier': verify.replace(b'=', b''),
        }
        response = self.Session.post(url, data = body, headers = headers)
        return response.json()['session_token']

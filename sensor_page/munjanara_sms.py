import urllib
import urllib2


def send_sms(receiver, message):
    url = 'http://www.munjanara.co.kr/MSG/send/web_admin_send.htm'
    values = {
        'userid': 'chiknhed',
        'passwd': 'shfur2@@',
        'sender': '01090344820',
        'receiver': receiver,
        'message': message,
        }
    data = urllib.urlencode(values)
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)

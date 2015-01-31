import urllib
import urllib2
import logging

#ToDo : handle unformate phone number

def send_sms(receiver, message):
    url = 'http://www.munjanara.co.kr/MSG/send/web_admin_send.htm'
    values = {
        'userid': 'chiknhed',
        'passwd': 'shfur2@@',
        'sender': '01090344820',
        'receiver': receiver,
        'message': message.encode('EUC-KR'),
        }
    data = urllib.urlencode(values)
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    logging.error(response.read)
import urllib
import urllib2
import logging


def normalize_phone_number(string):
    normalized_str = ""
    for character in string:
        if character < '0':
            continue
        elif character > '9':
            continue
        normalized_str += character
    return normalized_str


def send_sms(receiver, message):
    url = 'http://www.munjanara.co.kr/MSG/send/web_admin_send.htm'
    receiver = normalize_phone_number(receiver)
    values = {
        'userid': 'chiknhed',
        'passwd': 'sensortest',
        'sender': '01090344820',
        'receiver': receiver,
        'message': message.encode('EUC-KR'),
        }
    data = urllib.urlencode(values)
    req = urllib2.Request(url, data)
    urllib2.urlopen(req)


def send_bulk_sms(tuples):
    for (receiver, msg) in tuples:
        send_sms(receiver, msg)
# -*- coding: utf-8 -*-

import hashlib


def get_sensor_type_str(sensor_type):
    if sensor_type == 0:
        return u'온도'
    elif sensor_type == 1:
        return u'습도'
    elif sensor_type == 2:
        return u'압력'
    else:
        return u'??'


def get_hash_from_mac(mac_str):
    sha = hashlib.sha1()
    sha.update('owen77')
    sha.update('-'.join(mac_str.split(':')))
    sha.update('young')
    return sha.hexdigest()

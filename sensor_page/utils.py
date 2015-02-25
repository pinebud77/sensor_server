# -*- coding: utf-8 -*-

import hashlib


def get_hash_from_mac(mac_str):
    sha = hashlib.sha1()
    sha.update('owen77')
    sha.update('-'.join(mac_str.split(':')))
    sha.update('young')
    return sha.hexdigest()


def get_app_hash(username, password):
    sha = hashlib.sha1()
    sha.update('hello')
    sha.update(username)
    sha.update(password)
    sha.update('application')
    return sha.hexdigest()
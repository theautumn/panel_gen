#!/usr/bin/python
# https://github.com/ettoreleandrotognoli/python-ami

import os
import time
from settings import login, connection
import re

from asterisk.ami import AMIClient
from asterisk.ami import EventListener
from asterisk.ami import Response

def event_notification(source, event):
    output = str(event)
    order = re.sub(',','\n',output)
    print output
#    pattern1 = re.compile('(?<=DialString\'\:\su.{8})(\d{7})') 
#    pattern2 = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')
#    cnid = pattern1.findall(output)
#    DAHDIchan = pattern2.findall(output)
#    print 'Called line is: '+ cnid[0]
#    print 'DAHDI/' +  DAHDIchan[0]

client = AMIClient(**connection)
future = client.login(**login)
if future.response.is_error():
    raise Exception(str(future.response))

client.add_event_listener(EventListener(on_event=event_notification, white_list=['DialBegin', 'DialEnd']))
#client.add_event_listener(EventListener(on_event=event_notification))

try:
    while True:
        time.sleep(10)
except (KeyboardInterrupt, SystemExit):
    client.logoff()

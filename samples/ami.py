#!/usr/bin/python
# https://github.com/ettoreleandrotognoli/python-ami

import os
import time
from settings import login, connection
import re
import datetime

from asterisk.ami import AMIClient
from asterisk.ami import EventListener
from asterisk.ami import Response
from asterisk.ami import SimpleAction
from asterisk.ami import AMIClientAdapter

def event_notification(source, event):
    output = str(event)
    order = re.sub(',','\n',output)
    print(datetime.datetime.now())
    print order
#    pattern1 = re.compile('(?<=DialString\'\:\su.{8})(\d{7})') 
#    pattern2 = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')
#    cnid = pattern1.findall(output)
#    DAHDIchan = pattern2.findall(output)
#    print 'Called line is: '+ cnid[0]
#    print 'DAHDI/' +  DAHDIchan[0]

client = AMIClient(**connection)
adapter = AMIClientAdapter(client)
future = client.login(**login)
if future.response.is_error():
    raise Exception(str(future.response))

#client.add_event_listener(EventListener(on_event=event_notification, white_list=['DialBegin', 'DialEnd']))
#client.add_event_listener(EventListener(on_event=event_notification))


try:
    while True:
        time.sleep(1)
        adapter.Originate(Channel='SIP/sarah',Exten='sarah',Priority=1,Context='museum',CallerID='python')
except (KeyboardInterrupt, SystemExit):
    client.logoff()

#!/usr/bin/python3
#---------------------------------------------------------------------#
#                                                                     #
#  A call generator thing for the telephone switches at the           #
#  Connections Museum, Seattle WA.                                    #
#                                                                     #
#  Written by Sarah Autumn, 2017-2020                                 #
#  sarah@connectionsmuseum.org                                        #
#  github.com/theautumn/panel_gen                                     #
#                                                                     #
#---------------------------------------------------------------------#

from time import sleep
from os import system
import signal
import subprocess
import argparse
import logging
import uuid
import curses
import re
import threading
import sys
from configparser import ConfigParser
from datetime import datetime
from marshmallow import Schema, fields, post_load
from tabulate import tabulate
from numpy import random
from pycall import CallFile, Call, Application, Context
from asterisk.ami import AMIClient, EventListener, AMIClientAdapter


class Line():
    """
    This class defines Line objects.

    switch:             Set to an instantiated switch object. Usually Rainier,
                        Adams, or Lakeview
    kind:               Type of switch for above objects. "panel, 1xb, 5xb"
    status:             0 = OnHook, 1 = OffHook
    term:               String containing the 7-digit terminating line.
    timer:              Starts with a standard random.gamma, then gets set
                        subsequently by the call volume attribute of the switch.
    ident:              Integer starting with 0 that identifies the line.
    human_term:         Easily readable called line number, for my dyslexic ass.
    chan:               DAHDI channel the call is being placed on.
    magictoken:         UUID generated each time a callfile is passed to
                        Asterisk. Asterisk sends it back to us via AMI, and we
                        match it against our call.
    ast_status:         Returned from AMI. Indicates status of line from
                        Asterisk's perspective.
    ami_tmr:            Set when we ask Asterisk to do something. Number of seconds to wait
                        before we expect an AMI event response.
    switching_delay:    Set when a call is made that requires extra time in the dialing
                        state, such as a call via ANI trunks.
    pending_*           Set to true if this line is pending action by Asterisk.
                        Set to false when Asterisk confirms it took action.
    """

    def __init__(self, ident, switch, **kwargs):
        self.switch = switch
        self.kind = switch.kind
        self.status = 0
        self.term = self.pick_next_called(term_choices)
        self.timer = random.gamma(3,4)
        self.ident = ident
        self.human_term = phone_format(self.term)
        self.chan = '-'
        self.magictoken = ""
        self.ast_status = 'on_hook'
        self.ami_tmr = 0
        self.switching_delay = 0
        self.longdistance = False
        self.pending_call = False
        self.pending_dialend = False
        self.pending_hangup = False

    def __repr__(self):
        return 'Line('+ repr(self.ident) + ', ' + repr(self.term) +')'

    def tick(self):
        """
        Decrement line timer.
        Manages the line's state machine by placing calls or hanging up,
        depending on status.

        Returns the new value of self.timer
        """
        try:
            if self.switch.running == False:
                self.switch.running = True
            self.timer -= 0.10
            self.ami_tmr -= 0.10
            if self.timer <= 0:
                if self.ast_status == "on_hook":
                    if self.switch.is_dialing < self.switch.max_dialing:
                        self.call()
                    else:
                        # Back off until some calls complete.
                        self.timer = random.gamma(4,4)
                        logging.debug("Hit sender limit: %s with %s calls " +
                            "dialing. Delaying call.",
                            self.switch.max_dialing, self.switch.is_dialing)
                elif self.ast_status == "Dialing" or self.ast_status == "Ringing":
                    self.hangup()

            # Check to make sure we're still sane :)
            safetynet()

        except Exception as e:
            logging.exception(e)

        return self.timer

    def pick_next_called(self, term_choices):
        """
        Returns a string containing a 7-digit number to call.

        term_choices:       List of office codes. Comes from config file
        """
        if len(NXX) != len(self.switch.trunk_load):
            logging.error("Check your config file! \"nxx\" is of a length %s " +
                        "and the trunk load of %s switch is %s",
                        len(NXX), self.switch.kind, len(self.switch.trunk_load))
            logging.error("Also check the switch class for the presence of each " +
                        "trunk load variable that exists in config file.")

        if term_choices == []:
            term_office = random.choice(NXX, p=self.switch.trunk_load)
        else:
            term_office = random.choice(term_choices)

        # Choose a sane number that appears on the line link or final
        # frame of the switches that we're actually calling. If something's
        # wrong, then assert false, so it will get caught.

        if term_office == 722 or term_office == 365:
            term_station = random.randint(Rainier.line_range[0], Rainier.line_range[1])
        elif term_office == 832 or term_office == 833 or term_office == 524:
            term_station = random.choice(Lakeview.line_range)
        elif term_office == 232:
            term_station = random.choice(Adams.line_range)
        elif term_office == 275:
            term_station = random.randint(Step.line_range[0], Step.line_range[1])
        elif term_office == 830:
            term_station = random.randint(ESS3.line_range[0], ESS3.line_range[1])
        else:
            logging.error("No terminating line available for this office.")
            assert False

        term = str(term_office) + str(term_station)
        logging.debug('Terminating line selected: %s', term)
        self.human_term = phone_format(term)
        return term


    def call(self, **kwargs):
        """
        Places a call. Returns nothing.

        kwargs:
            originating_switches:     switch call is coming from
            line:            line placing the call
            timer:           duration of the call

        """
        nextchan = self.switch.newchannel(self.switch.channel_choices)
        if nextchan == False:
            self.timer = random.gamma(4,4)
            return

        pred = ''

        if self.switch.ld_capable == True:          # Set in config.
            pred = longdistance(self, nextchan)

        #channel = 'DAHDI/{}'.format(self.switch.dahdi_group) + '/wwww%s' % self.term
        channel = 'DAHDI/{}'.format(nextchan) + '/wwww%s' % pred+self.term
        logging.debug('To Asterisk: %s on ident %s', channel, self.ident)

        self.timer = self.switch.newtimer()

        # Wait value to pass to Asterisk. (We will actually be controlling the
        # hangup from here, but this is kind of a safety net so asterisk dumps
        # the call if we can't for some reason.)
        wait = int(self.timer) + 7

        # OoOOOoOOoOOOO!
        self.magictoken = str(uuid.uuid4())

        # Set wait time for asterisk to auto hangup.
        vars = {'waittime': wait}
        cid = 'panel_gen <{}>'.format(self.switch.kind)

        self.ami_tmr = 4
        self.pending_call = True

        logging.debug('About to create .call file for line %s', self.ident)
        logging.debug('Magic Token: %s', self.magictoken)

        # Make the .call file amd throw it into the asterisk spool.
        # Pass control of the call to the sarah_callsim context in
        # the dialplan.
        # Set accountcode to our magic UUID for use later.
        c = Call(channel, variables=vars, callerid=cid,
                 account=self.magictoken)
        con = Context('sarah_callsim', pred+self.term, '1')
        cf = CallFile(c, con)
        cf.spool()



    def hangup(self):
        """
        Hangs up a call.

        Send an AMI hangup request to Asterisk,
        Set a timer to wait for Asterisk's response.
        Response is handled in on_Hangup()
        """

        adapter.Hangup(Channel='DAHDI/{}-1'.format(self.chan))
        self.pending_hangup = True
        self.ami_tmr = 3
        logging.debug('2: Asked Asterisk to hangup %s on DAHDI/%s, line %s',
                     self.term, self.chan, self.ident)

        self.switching_delay = 0
        self.longdistance = False
        logging.debug("Pending hangup: %s", self.pending_hangup)


class Switch():
    """
    This class is parameters and methods for a switch.

    kind:           Generic name for type of switch.
    running:        Whether or not switch is running.
    max_dialing:    Set based on sender capacity.
    is_dialing:     Records current number of calls in Dialing state.
    dahdi_group:    Passed to Asterisk when call is made.
    traffic_load:   String that contains "light", "heavy", or "normal".
                    Sets the random.gamma distribution for generating
                    new call timers.
    lines_normal:   Number of lines to use in normal traffic mode.
    lines_heavy:    Number of lines to use in heavy traffic mode.
    max_nxx:        Values for trunk load. Determined by how many
                    outgoing trunks we have provisioned on the switch.
    trunk_load:     List of max_nxx used to compute load on trunks.
    line_range:     Range of acceptable lines to dial when calling this office.
    """

    def __init__(self, **kwargs):
        self.kind = kwargs.get('kind',"")
        kind = self.kind
        self.running = False
        self.max_dialing = config.getint(kind, 'max_dialing')
        self.is_dialing = 0
        self.on_call = 0
        self.dahdi_group = config.get(kind, 'dahdi_group')
        self.channel_choices = config.get(kind, 'channels').split(",")
        self.ld_capable = config.getboolean(kind, 'long_distance')
        self.traffic_load = "normal"
        self.lines_normal = config.getint(kind, 'lines_normal')
        self.lines_heavy = config.getint(kind, 'lines_heavy')
        self.max_722 = float(config[kind]['max_722'])
        self.max_232 = float(config[kind]['max_232'])
        self.max_832 = float(config[kind]['max_832'])
        self.max_275 = float(config[kind]['max_275'])
        self.max_365 = float(config[kind]['max_365'])
        self.max_830 = float(config[kind]['max_830'])
        self.max_833 = float(config[kind]['max_833'])
        self.max_524 = float(config[kind]['max_524'])
        self.trunk_load = [self.max_722, self.max_232,
                self.max_832, self.max_275, self.max_365,
                self.max_830, self.max_833, self.max_524]
        self.line_range = config.get(kind, 'line_range').split(",")
        self.n_ga = config.get(kind, 'n_gamma')
        self.h_ga = config.get(kind, 'h_gamma')

    def __repr__(self):
        return 'Switch('+ repr(self.kind) + ')'

    def newtimer(self):
        """
        Returns timer back to Line() object. Checks to see
        if running as __main__ or as a module and act
        accordingly.
        """
        if self.traffic_load == 'heavy':
            a,b = (int(x) for x in self.h_ga.split(","))
            timer = random.gamma(a,b)
        elif self.traffic_load == 'normal':
            a,b = (int(x) for x in self.n_ga.split(","))
            timer = random.gamma(a,b)
        return timer

    def newchannel(self, channel_choices):
        """
        We can either ask Asterisk to pick a channel, or
        we can do it ourselves. That decision is made in call()

        channel_choices: defined in panel_gen.conf
        """
        channels_inuse = [l.chan for l in lines]
        logging.debug('Begin channel selection')
        logging.debug("In use: %s", channels_inuse)
        channels_avail = [c for c in channel_choices if not c in channels_inuse]
        logging.debug("Avail:  %s", channels_avail)

        if channels_avail == []:
            logging.warning("No channels available on %s. Not placing call.", self.kind)
            return False
        else:
            nextchan = random.choice(channels_avail)
            logging.debug("End channel selection. Selected: %s", nextchan)
            return nextchan


# +-----------------------------------------------+
# |                                               |
# |      <----- BEGIN AMI NONSENSE ----->         |
# |                                               |
# +-----------------------------------------------+

def on_DialBegin(event, **kwargs):
    """
    Callback function for DialBegin AMI events.

    Account Code is a magic number we send to Asterisk and expect
    to get back. This is how we match events with calls in progress.
    """
    try:
        event = str(event)

        DB_DestChannel = re.compile('(?<=DestChannel\'\:\s.{7})([^-]*)')
        AccountCode = re.compile('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

        DB_DestChannel = DB_DestChannel.findall(event)
        AccountCode = AccountCode.findall(event)

        if DB_DestChannel == [] or AccountCode == []:
            # Fuckin bail out!
            logging.debug("***DialBegin regex isn't matching!***")
            return

        for l in lines:
            if AccountCode[0] == l.magictoken:
                l.chan = DB_DestChannel[0]
                l.ast_status = 'Dialing'
                l.switch.is_dialing += 1
                l.switch.on_call +=1
                l.status = 1
                l.pending_call = False
                l.pending_dialend = True
                l.ami_tmr = 18
                logging.debug('DialBegin %s on DAHDI/%s from %s ident %s ->>',
                             l.term, l.chan, l.switch.kind, l.ident)
    except Exception as e:
        logging.exception(e)


def on_DialEnd(event, **kwargs):
    """
    Callback function for DialEnd AMI events.

    """

    try:
        event = str(event)

        DE_DestChannel = re.compile('(?<=DestChannel\'\:\s.{7})([^-]*)')
        AccountCode = re.compile('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

        DE_DestChannel = DE_DestChannel.findall(event)
        AccountCode = AccountCode.findall(event)

        if DE_DestChannel == [] or AccountCode == []:
            #Outta here
            logging.debug("***DialEnd regex isn't matching!***")
            return

        for l in lines:
            if AccountCode[0] == l.magictoken:
                logging.debug('FROM ASTERISK: DialEnd for line %s', l.term)
                l.pending_dialend = False
                line = l
                break

        def doDialEnd():
            try:
                logging.debug("C: DialEnd bookkeeping starting on %s. Pending hangup is %s",
                             line.term, line.pending_hangup)
                if line.pending_hangup == False:
                    if line.ast_status == 'Dialing':
                        line.ast_status = 'Ringing'
                        line.switch.is_dialing -= 1
                        logging.debug('Ringing %s on line %s', line.term, line.ident)
                    elif line.ast_status == 'on_hook':
                        logging.error('How did we get to DialEnd from on_hook?')
                        # This might break everything lets see XXXXXXXXXX
                        # It did -- Matt
                        # line.ast_status = 'Ringing':
                        # logging.error('Set status to Ringing on line %s', line.ident)
                        pass # xxx this might be problems
                    logging.debug('on_DialEnd with %s calls dialing', line.switch.is_dialing)
            except Exception as e:
                logging.exception(e)

        if len(lines) > 0:
            if line:
                enqueue_event(line.switching_delay, doDialEnd)
                logging.debug("B: Event enqueued  delay %s.", line.switching_delay)

    except Exception as e:
        logging.exception(e)

def enqueue_event(delay, callback):
    try:
        eventtimer = threading.Timer(delay, callback)
        eventtimer.start()
        logging.debug("A: Started event timer delay %s", delay)
    except Exception as e:
        logging.exception(e)


def on_Hangup(event, **kwargs):
    """
    Callback for processing hangup events.
    """

    try:
        event = str(event)
        HU_DestChannel = re.compile('(?<=DestChannel\'\:\s.{7})([^-]*)')
        AccountCode = re.compile('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')

        AccountCode = AccountCode.findall(event)
        HU_DestChannel = HU_DestChannel.findall(event)

        if AccountCode == []:
            logging.debug("*** AccountCode didn't match on hangup***")
            return

        for l in lines:
            if AccountCode[0] == l.magictoken:
                if l.ast_status == 'Dialing':
                    l.switch.is_dialing -= 1
                    logging.debug('Hangup while dialing %s on DAHDI %s', l.term, l.chan)

                l.status = 0
                l.chan = '-'
                l.ast_status = 'on_hook'
                l.switch.on_call -= 1
                l.timer = l.switch.newtimer()
                l.term = l.pick_next_called(term_choices)
                l.pending_hangup = False
                logging.debug('<<- Asterisk reports hangup OK. Line %s status is %s',
                              l.ident, l.status)
    except Exception as e:
        logging.exception(e)


def parse_args():
    # Gets called at runtime and parses arguments given on command line.
    # If no arguments are presented, the program will run with default
    # mostly sane options.

    parser = argparse.ArgumentParser(description='Generate calls to electromechanical switches. '
            'Defaults to originate a sane amount of calls from the panel switch if no args are given.')
    parser.add_argument('-a', metavar='lines', type=int, default=[], choices=[1,2,3,4,5,6,7,8,9,10],
            help='Maximum number of active lines.')
    parser.add_argument('-o', metavar='switch', type=str, nargs='?', action='append', default=[],
            choices=['1xb','1xbos','5xb','panel','all','722', '832', '232'],
            help='Originate calls from a particular switch. Takes either 3 digit NXX values '
            'or switch name.  1xb, 1xbos, 5xb, panel, or all. Default is panel.')
    parser.add_argument('-t', metavar='switch', type=str, nargs='?', action='append', default=[],
            choices=['1xb','5xb','panel','office','step', '722', '832', '232', '365', '275'],
            help='Terminate calls only on a particular switch. Takes either 3 digit NXX values '
            'or switch name. Defaults to sane options for whichever switch you are originating from.')
    parser.add_argument('-v', metavar='volume', type=str, default='normal',
            help='Call volume is a proprietary blend of frequency and randomness. Can be light, '
            'normal, or heavy. Default is normal, which is good for average load.')
    parser.add_argument('-log', metavar='loglevel', type=str, default='INFO',
            help='Set log level to WARNING, INFO, DEBUG.')

    global args
    args = parser.parse_args()
    return args


def phone_format(n):
    return format(int(n[:-1]), ",").replace(",", "-") + n[-1]


def longdistance(line, chan):
    # Some lines can be long distance calls with ANI

    newsenders = ['13','14','16','27','28','29','32','45','46','47']
    pd = ''

    if line.kind == "1xb":
        if chan in newsenders:
            if line.term[0:3] == "832" or line.term[0:3] == "232":
                if line.longdistance == False:
                    i = random.randint(0,10)
                    if i >= 7:
                        logging.info("ANI call being placed on %s to %s, chan %s",
                                     line.kind, line.term, chan)
                        line.human_term = line.human_term + '*'
                        pd = '11'
                        line.switching_delay = 6
                        line.longdistance = True

    if line.kind == "5xb":
        too_many = sum(1 for l in lines if l.longdistance == True and l.kind =="5xb")
        if line.term[0:3] == "832" or line.term[0:3] == "232":
            i=random.randint(0,10)
            if i >= 5:
                if too_many < 2:
                    logging.info("ANI call being placed on %s to %s, chan %s",
                        line.kind, line.term, chan)
                    line.human_term = line.human_term + '*'
                    pd = '1'
                    line.switching_delay = 4
                    line.longdistance = True

    return pd

def safetynet():
    # Most of these things should never need to be done
    # but its better to be fault tolerant if possible

    def doRestartSwitch(reason, kind):
        api_stop(switch=s.kind)
        api_start(switch=s.kind)
        logging.error("Restarted switch %s due to invalid state: %s", kind, reason)

    def errorhandle(reason, status):

        logging.error("Failed to get AMI %s within allotted time on %s",
                      status, l)
        logging.error("Channel: %s", l.chan)
        logging.error("Status: %s", l.status)
        logging.error("Asterisk: %s", l.ast_status)
        logging.error("Term: %s", l.human_term)

    reason = ''

    for s in originating_switches:
        if s.is_dialing < 0:
            reason =  "dialing counter < 0"
            doRestartSwitch(reason, s.kind)

        if s.is_dialing > s.max_dialing:
            reason = "exceeded max dialing"
            doRestartSwitch(reason, s.kind)

    for l in lines:
        if l.pending_call == True:
            status = "DialBegin"
            if l.ami_tmr <= 0:
                l.pending_call = False
                errorhandle(reason, status)

        if l.pending_dialend == True:
            status = "DialEnd"
            if l.ami_tmr <= 0:
                l.pending_dialend = False
                errorhandle(reason, status)

        if l.pending_hangup == True:
            status = "Hangup"
            if l.ami_tmr <= 0:
                l.pending_hangup = False
                # This pass prevents silly threading confusion where
                # asterisk will report a hangup before we realize that we've
                # asked for one ;P
                if l.chan == '-':
                    pass
                else:
                    errorhandle(reason, status)


def make_switch(args):
    # Instantiate some switches so we can work with them later.
    # Behave differently if we're running as __main__ or __panel_gen__

    global Rainier
    global Adams
    global Lakeview
    global Step
    global ESS3

    Rainier = Switch(kind='panel')
    Adams = Switch(kind='5xb')
    Lakeview = Switch(kind='1xb')
    Step = Switch(kind='step')
    ESS3 = Switch(kind='3ess')

    global originating_switches
    originating_switches = []

    if __name__ == 'panel_gen':
        originating_switches.append(Rainier)
        originating_switches.append(Adams)
        originating_switches.append(Lakeview)

    if __name__ == '__main__':
        for o in args.o:
            if o == 'panel' or o == '722':
                originating_switches.append(Rainier)
            elif o == '5xb' or o == '232':
                originating_switches.append(Adams)
            elif o == '1xb' or o == '832':
                originating_switches.append(Lakeview)
            elif o == 'ess' or o == '830':
                originating_switches.append(ESS3)
            elif o == 'all':
                originating_switches.extend((Lakeview, Adams, Rainier))

        if args.o == []:
            originating_switches.append(Rainier)

    global term_choices
    term_choices = []

    for t in args.t:
        if t == 'panel' or t == '722':
            term_choices.append(722)
        elif t == '5xb' or t == '232':
            term_choices.append(232)
        elif t == '1xb' or t == '832':
            term_choices.append(832)
        elif t == 'office' or t == '365':
            term_choices.append(365)
        elif t == 'step' or t == '275':
            term_choices.append(275)


def make_lines(**kwargs):
    """
    Takes several kwargs. Returns a bunch of lines.

    source:         the origin of the call to this function
    switch:         the switch where the lines will originate on
    originating_switches:    list of originating switches passed in from args
    numlines:       number of lines we should create. should be determined and
                    passed in before this function is called
    """
    try:
        source = kwargs.get('source', '')
        switch = kwargs.get('switch', '')
        originating_switches = kwargs.get('originating_switches','')
        numlines = kwargs.get('numlines', '')

        new_lines = []
        if source == 'main':
            if args.a == []:
                new_lines = [Line(n, switch) for switch in originating_switches for n in range(switch.lines_normal)]
            else:
                new_lines = [Line(n, switch) for switch in originating_switches for n in range(args.a)]

        elif source == 'api':
            new_lines = [Line(n, switch) for n in range(numlines)]
    except Exception as e:
        logging.exception(e)

    return new_lines

def start_ui():
    """
    This starts the panel_gen UI. Only useful when run as module.
    When run as __main__, the UI is started for you.

    :return:    Nothing
    :args:      Nothing
    """
    global t_ui

    try:
        t_ui = ui_thread()
        t_ui.daemon = True
        t_ui.start()
    except Exception as e:
        print(e)

def ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET):
    global client
    global adapter
    client = AMIClient(address=AMI_ADDRESS, port=int(AMI_PORT))
    adapter = AMIClientAdapter(client)
    future = client.login(username=AMI_USER, secret=AMI_SECRET)
    logging.info('Connected to Asterisk AMI')
    if future.response.is_error():
        raise Exception(str(future.response))

    # These listeners are for the AMI so I can catch events.
    client.add_event_listener(on_DialBegin, white_list = 'DialBegin')
    client.add_event_listener(on_DialEnd, white_list = 'DialEnd')
    client.add_event_listener(on_Hangup, white_list = 'Hangup')


# +----------------------------------------------------+
# |                                                    |
# | The following chunk of code is for the             |
# | panel_gen API, run from http_server.py             |
# | The http server starts Flask, Connexion, which     |
# | reads the API from swagger.yml, and executes HTTP  |
# | requests using the code in switch.py, line.py and  |
# | app.py.                                            |
# |                                                    |
# | These functions return values to those .py's       |
# | when panel_gen is imported as a module.            |
# |                                                    |
# +----------------------------------------------------+

class AppSchema(Schema):
    name = fields.Str()
    app_running = fields.Boolean()
    panel_running = fields.Boolean()
    xb5_running = fields.Boolean()
    xb1_running = fields.Boolean()
    ui_running = fields.Boolean()
    is_paused = fields.Boolean()
    num_lines = fields.Integer()

class LineSchema(Schema):
    line = fields.Dict()
    ident = fields.Integer()
    kind = fields.Str()
    timer = fields.Integer()
    is_dialing = fields.Boolean()
    ast_status = fields.Str()
    status = fields.Int()
    chan = fields.Str()
    term = fields.Str()
    human_term = fields.Str()
    hook_state = fields.Integer()

class SwitchSchema(Schema):
    switch = fields.Dict()
    kind = fields.Str()
    max_dialing = fields.Integer()
    is_dialing = fields.Integer()
    on_call = fields.Integer()
    lines_normal = fields.Integer()
    lines_heavy = fields.Integer()
    dahdi_group = fields.Str()
    trunk_load = fields.List(fields.Str())
    line_range = fields.List(fields.Str())
    running = fields.Boolean()
    timer = fields.Str()
    traffic_load = fields.Str()

    @post_load
    def engage_motherfucker(self, data, **kwargs):
            return Switch(**data)

def get_info():
    """ Returns info about app state. """
    schema = AppSchema()

    ui_running = False

    try:
        if t_ui.started == True:
            ui_running = True
    except Exception as e:
        pass

    result = dict([
        ('name', __name__),
        ('app_running', t_work.is_alive),
        ('is_paused', t_work.paused),
        ('ui_running', ui_running),
        ('num_lines', len(lines)),
        ('panel_running', Rainier.running),
        ('xb5_running', Adams.running),
        ('xb1_running', Lakeview.running),
        ])
    return schema.dump(result)


def api_start(**kwargs):
    """
    Creates new lines when started from API.

    - Checks to see if work thread is running
    - Assigns generic switch type to instantiated name
    - Checks to see if the switch is already running
    - A special case is created for Sunday. See further notes
    below.

    source:     Used to log where the start request came from.
    switch:     Specifies which switch to start calls on.
    traffic_load:  'normal' or 'heavy'. Impacts number of lines we start with.

    """

    global lines
    global new_lines
    source = kwargs.get('source', '')
    switch = kwargs.get('switch', '')
    traffic_load = kwargs.get('traffic_load', '')

    try:
        if source == 'web':
            logging.info("App requested START on %s", switch)
        elif source == 'key':
            logging.info('Key operated: START on %s', switch)
        else:
            logging.warning('I dont know why, but we are starting on %s', switch)

        if t_work.is_alive == True:
            for i in originating_switches:
                if switch == i.kind:
                    if i.running == True:
                        logging.warning("%s is running. Can't start twice.", i.kind)
                    elif i.running == False:

                        # Reset the dialing counter for safety.
                        i.is_dialing = 0

                        # This block handles whether or not the user passed in
                        # a traffic load setting. If not, we'll just use whatever
                        # we already have.
                        if traffic_load == "normal" or traffic_load == "heavy":
                            if traffic_load != i.traffic_load:
                                i.traffic_load = traffic_load
                                logging.info('Changing traffic load to %s', traffic_load)
                        if i.traffic_load == 'heavy':
                            numlines = i.lines_heavy
                        if i.traffic_load == 'normal':
                            numlines = i.lines_normal
                        if i == Adams:
                            # Carve out a special case for Sundays. This was requested
                            # by museum volunteers so that we can give tours of the
                            # step and 1XB without interruption by the this program.
                            # This will only be effective if the key is operated.
                            # Will have no impact when using web app.
                            if datetime.today().weekday() == 6:
                                logging.info('Its Sunday!')
                                if source == 'key':
                                    logging.info('5XB special Sunday mode active')
                                    i.trunk_load = [.1, .80, .1, .0, .0, .0, .0, .0]
                                    new_lines = make_lines(switch=i, numlines=numlines,
                                    source='api')

                                # Adams: If we start from the web interface, ignore
                                # those rules.
                                else:
                                    logging.info('5XB special Sunday mode skipped')
                                    new_lines = make_lines(switch=i, numlines=numlines,
                                    source='api')

                            # Adams: If its any other day of the week, just act normal.
                            else:
                                new_lines = make_lines(switch=i, numlines=numlines,
                                source='api')

                        # Everyone else: Make lines.
                        else:
                            new_lines = make_lines(switch=i, numlines=numlines,
                            source='api')

                        # Append the lines we just created.
                        for l in new_lines:
                            lines.append(l)

                        i.running = True
                        logging.info('Appended %s lines to %s', len(new_lines), switch)

                    lines_created = len(new_lines)
                    result = get_info()
                    return result
    except Exception as e:
        logging.execption(e)
        return False


def api_stop(**kwargs):
    """
    Immediately hang up calls, and destroy lines.

    switch:     Which switch to hangup and stop. Can be
                'panel', '5xb', '1xb' 'all'. Other switches not
                yet implemented.
    source:     Where the request came from. Used for logging.
    """

    switch = kwargs.get('switch', '')
    source = kwargs.get('source', '')

    if source == 'web':
        logging.info("App requested STOP on %s", switch)
    elif source == 'key':
        logging.info('Key operated: STOP on %s', switch)
    elif source == 'module':
        logging.info('Module exited. Hanging up.')

    global lines

    try:
        if switch == 'all':
            for l in lines:
                l.hangup()
            lines = []
            for s in originating_switches:
                s.running = False
                s.is_dialing = 0
                s.on_call = 0

            # Just hangup all channels when I use the FORCE button.
            # After all. If I hit that button, I'm not kidding.
            adapter.Hangup(Channel='/(.*?)/')

            # Delete all remaining files in spool.
            try:
                system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")
            except Exception as e:
                logging.warning("Failed to delete remaining files in spool.")
                logging.warning(e)
        else:
            for s in originating_switches:
                if s.kind == switch:
                    deadlines = [l for l in lines if l.kind == s.kind]
                    lines = [l for l in lines if l.kind != s.kind]
                    s.running = False
                    s.is_dialing = 0

                    for n in deadlines:
                        n.hangup()
                    s.on_call = 0

    except Exception as e:
        logging.exception(e)
        return False

    return get_info()


def get_all_lines():
    """ Returns formatted list of all lines """

    schema = LineSchema()
    result = [schema.dump(l) for l in lines]
    return result

def get_line(ident):
    # Check if ident passed in via API exists in lines.
    # If so, send back that line. Else, return False..

    api_ident = int(ident)
    schema = LineSchema()
    result = None
    for l in lines:
        if api_ident == l.ident:
            result = (schema.dump(l))
    if result == None:
        return False
    else:
        return result

def create_line(**kwargs):
    # Creates a new line using default parameters.
    # lines.append uses the current number of lines in list
    # to create the ident value for the new line.

    schema = LineSchema()
    result = []

    switch = kwargs.get('switch','')
    numlines = kwargs.get('numlines','')

    for i in originating_switches:
        if switch == i or switch == i.kind:
            for n in range(numlines):
                lines.append(Line(len(lines), i))
                result.append(len(lines) - 1)

    if result == []:
        return False
    else:
        return result

def delete_line(**kwargs):
    """
    Deletes a specific line.

    switch:     switch object
    kind:       type of switch
    numlines:   number of lines to delete
    """

    global lines
    switch = kwargs.get('switch','')

    for i in originating_switches:
        if i == switch or i.kind == kwargs.get('kind',''):
            for n in range(kwargs.get('numlines','')):
                lines.pop()

    result = get_switch(i.kind)

    if result == []:
        return False
    else:
        return result

def get_all_switches():
    """ Returns formatted list of all switches """

    schema = SwitchSchema()
    result = [schema.dump(n) for n in originating_switches]
    return result

def get_switch(kind):
    """ Gets the parameters for a particular switch object. """

    schema = SwitchSchema()
    result = []

    if kind == 'panel':
        result.append(schema.dump(Rainier))
    if kind == '5xb':
        result.append(schema.dump(Adams))
    if kind == '1xb':
        result.append(schema.dump(Lakeview))
    if kind == '3ess':
        result.append(schema.dump(ESS3))

    if result == []:
        return False
    else:
        return result

def create_switch(kind):
    """ Creates a switch. """

    if 'panel' not in originating_switches:
        if kind == 'panel':
            originating_switches.append(Rainier)
    if '5xb' not in originating_switches:
        if kind == '5xb':
            originating_switches.append(Adams)
    if '1xb' not in originating_switches:
        if kind == '1xb':
            originating_switches.append(Lakeview)
    if 'ESS3' not in originating_switches:
        if kind == '3ess':
            originating_switches.append(ESS3)

    if originating_switches != []:
        return originating_switches
    else:
        return False

def update_switch(**kwargs):
    # This is terrible and needs to be changed.
    # Currently only works with traffic_load
    # bugs: can change traffic load between light + normal
    # and it will reduce lines by 2 every time. also doesnt
    # do any kind of sanity checking :\

    schema = SwitchSchema()
    result = []

    for i in originating_switches:
        if i.kind == kwargs.get("kind", ""):
            # Wipe out the top parameter, because I said so
            del kwargs['kind']
            # Lets iterate over the parameters we can work with.
            for k,v in kwargs.items():
                for k1 in v.items():
                    desired_load = k1[1]
                    if i.traffic_load != desired_load:
                        i.traffic_load = desired_load

                        # Determine how many lines we have to add or remove.
                        numlines = i.lines_heavy - i.lines_normal

                        if i.running == True:
                            if i.traffic_load == 'heavy':
                                create_line(switch=i, numlines=numlines)
                            elif i.traffic_load == 'normal':
                                delete_line(switch=i, numlines=numlines)
                        logging.info("Traffic on %s changed to %s",
                                    i.kind, i.traffic_load)
            result.append(schema.dump(i))
    if result != []:
        return result
    else:
        return False


def test_call(num_to_dial, ast_channel):
    """
    Helper function for web-based remote control
    """

    channel = 'DAHDI/{}'.format(ast_channel) + '/wwww%s' % num_to_dial
    logging.info(channel)
    vars = {'waittime':10}

    c = Call(channel, variables=vars, callerid='test')
    con = Context('sarah_callsim', num_to_dial, '1')
    cf = CallFile(c, con)
    cf.spool()



# +-----------------------------------------------+
# |                                               |
# |      <----- BEGIN SCREEN/UI STUFF ----->      |
# |                                               |
# +-----------------------------------------------+

class Screen():
    # Draw the screen, get user input.

    def __init__(self, stdscr):
        # For some reason when we init curses using wrapper(), we have to tell it
        # to use terminal default colors, otherwise the display gets wonky.

        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
        self.y, self.x = stdscr.getmaxyx()
        stdscr.nodelay(1)
        self.stdscr = stdscr

    def getkey(self, stdscr):
    #Handles user input.

        key = stdscr.getch()

        if key == ord(' '):
            if t_work.paused == False:
                self.pausescreen()
                key = stdscr.getch()
                if key == ord(' '):
                    self.resumescreen()
            elif t_work.paused == True:
                t_work.resume()
        # u: add a line to the first switch.
        if key == ord('u'):
            try:
                lines.append(Line(7, originating_switches[0]))
            except Exception:
                logging.warning("Couldn't add lines to switch.")
        # d: delete the 0th line.
        if key == ord('d'):
            if len(lines) >= 1:
                del lines[0]

    def update_size(self, stdscr, y, x):
        # This gets called if the screen is resized. Makes it happy so
        # exceptions don't get thrown.

        self.stdscr.clear()
        curses.resizeterm(y, x)
        self.stdscr.refresh()

    def pausescreen(self):
        # Draw the PAUSED notification when execution is paused.
        # Just as importantly, pause the worker thread. Control goes back to
        # getkey(), which waits for another <spacebar> then resumes.

        y, x = self.stdscr.getmaxyx()
        half_cols = int(x/2)
        rows_size = 5
        x_start_row = y - 9
        y_start_col = half_cols - int(half_cols / 2)

        logging.info("Paused")
        t_work.pause()
        self.stdscr.nodelay(0)
        pause_scr = self.stdscr.subwin(rows_size, half_cols, x_start_row, y_start_col)
        pause_scr.box()
        pause_scr.addstr(2, int(half_cols/2) - 5, "P A U S E D", curses.color_pair(1))
        pause_scr.bkgd(' ', curses.color_pair(2))
        self.stdscr.addstr(y-1,0,"Spacebar: pause/resume, ctrl + c: quit", curses.A_BOLD)
        pause_scr.refresh()

    def resumescreen(self):
        # This should erase the paused window and refresh the screen.

        t_work.resume()
        self.stdscr.nodelay(1)
        self.stdscr.refresh()
        self.draw(self.stdscr, lines, self.y, self.x)
        logging.info("Resumed")


    def draw(self, stdscr, lines, y, x):
        # Output handling. make pretty things.

        table = [[n.kind, n.chan, n.human_term, int(n.timer),
                n.status, n.ast_status] for n in lines]
        stdscr.erase()
        stdscr.addstr(0,5," __________________________________________")
        stdscr.addstr(1,5,"|                                          |")
        stdscr.addstr(2,5,"|  Rainier Full Mechanical Call Simulator  |")
        stdscr.addstr(3,5,"|__________________________________________|")
        stdscr.addstr(6,0,tabulate(table, headers=["switch", "channel", "term",
                    "tick", "state", "asterisk"],
                    tablefmt="pipe", stralign = "right" ))

        # Print asterisk channels below the table so we can see what its actually doing.
        if y > 35:
            try:
                ast_out = subprocess.check_output(['asterisk', '-rx', 'core show channels'])
                stdscr.addstr(22,0,ast_out)
            except Exception:
                stdscr.addstr(22,0,"** MUST BE RUNNING AS ROOT FOR ASTERISK OUTPUT **")
                stdscr.addstr(20,5,"============ Asterisk output ===========")
        # Print the contents of /var/log/panel_gen/calls.log
        if y > 45:
            try:
                logs = subprocess.check_output(['tail', '/var/log/panel_gen/calls.log'])
                stdscr.addstr(32,5,'================= Logs =================')
                stdscr.addstr(34,0,logs)
            except Exception as e:
                pass

        stdscr.addstr(y-1,0,"Spacebar: pause/resume, ctrl + c: quit", curses.A_BOLD)
        stdscr.addstr(y-1,x-20,"Lines:",curses.A_BOLD)
        stdscr.addstr(y-1,x-13, str(len(lines)),curses.A_BOLD)

        # Refresh the screen.
        stdscr.refresh()


# +-----------------------------------------------+
# |                                               |
# |      <----- BEGIN THREADING CODE ----->       |
# |                                               |
# +-----------------------------------------------+

class ui_thread(threading.Thread):
    # The UI thread! Besides handling pause and resume, this also
    # sets up a screen, and calls various things in Screen() to
    # help with drawing.

    def __init__(self):

        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()
        self.started = True

    def run(self):
        try:
            curses.wrapper(self.ui_main)
        except Exception as e:
            logging.exception(e)

    def ui_main(self, stdscr):

        global screen
        # Instantiate a screen, so we can play with it later.
        screen = Screen(stdscr)

        while not self.shutdown_flag.is_set():

            # Handle user input.
            screen.getkey(stdscr)

            # Check if screen has been resized. Handle it.
            y, x = stdscr.getmaxyx()
            resized = curses.is_term_resized(y, x)
            if resized is True:
                y, x = stdscr.getmaxyx()
                screen.update_size(stdscr, y, x)

            # Draw the window
            screen.draw(stdscr, lines, y, x)
            stdscr.refresh()
            sleep(1)

    def draw_paused(self):
        try:
            screen.pausescreen()
        except NameError:
            pass

    def draw_resumed(self):
        try:
            screen.resumescreen()
        except NameError:
            pass

class work_thread(threading.Thread):
    # Does all the work! Can be paused and resumed. Handles all of
    # the exciting things, but most important is calling tick()
    # which evaluates the timers and makes call processing decisions.

    def __init__(self):

        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()
        self.paused = False
        self.paused_flag = threading.Condition(threading.Lock())

        # We get here from __main__, and this kicks the loop into gear.

        logging.info('--- Started panel_gen ---')

    def run(self):
        try:
            while not self.shutdown_flag.is_set():
                self.is_alive = True
                with self.paused_flag:
                    while self.paused:
                        self.paused_flag.wait()

                # The main program loop.
                    for l in lines:
                        l.tick()
                    sleep(0.1)
        except Exception as e:
            logging.exception(e)

    def pause(self):
        self.paused = True
        self.paused_flag.acquire()

    def resume(self):
        self.paused = False
        self.paused_flag.notify()
        self.paused_flag.release()


class ServiceExit(Exception):
    pass

def app_shutdown(signum, frame):
    raise ServiceExit

def module_shutdown():
    """
    Cleanly exit panel_gen
    """

    try:
        t_ui.shutdown_flag.set()
        t_ui.join()
    except Exception:
        pass
    t_work.shutdown_flag.set()
    t_work.join()

    logging.shutdown()
    client.logoff()

    print("\n\nShutdown requested. Hanging up Asterisk channels, and cleaning up /var/spool/")


if __name__ == "__main__":
    # Init a bunch of things if we're running as a standalone app.
    # Set up signal handlers so we can shutdown cleanly later.

    signal.signal(signal.SIGTERM, app_shutdown)
    signal.signal(signal.SIGINT, app_shutdown)

    paused = None

    config = ConfigParser()
    config.read('/etc/panel_gen.conf')

    global AMI_ADDRESS
    global AMI_PORT
    global AMI_USER
    global AMI_SECRET

    config = ConfigParser()
    config.read('/etc/panel_gen.conf')
    AMI_ADDRESS = config.get('ami', 'address')
    AMI_PORT = config.get('ami', 'port')
    AMI_USER = config.get('ami', 'user')
    AMI_SECRET = config.get('ami', 'secret')

    NXX = list(map(int,config.get('nxx', 'nxx').split(",")))    # Gross!

    # If logfile does not exist, create it so logging can write to it.
    try:
        with open('/var/log/panel_gen/calls.log', 'a') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.DEBUG,
            datefmt='%m/%d/%Y %I:%M:%S %p')
    except IOError:
        with open('/var/log/panel_gen/calls.log', 'w') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.DEBUG,
            datefmt='%m/%d/%Y %hh:%M:%S %p')

    # Connect to AMI
    try:
        ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET)
    except:
      #  logging.error('AMI connection failed. This will break things.')
      #  sys.exit('Failed to connect to Asterisk AMI. Is Asterisk running?')
      logging.error("all that junk", exc_info=True)

    # Parse any arguments the user gave us.
    parse_args()
    make_switch(args)

    logging.info('Originating calls on %s', originating_switches)

    if args.t != []:
        logging.info('Terminating calls on %s', term_choices)

    logging.info('Call volume set to %s', args.v)

    # Here is where we actually make the lines.
    lines = make_lines(source='main', originating_switches=originating_switches,
                       numlines = args.a)

    try:
        t_ui = ui_thread()
        t_ui.daemon = True
        t_ui.start()
        t_work = work_thread()
        t_work.daemon = True
        t_work.start()

        while True:
            sleep(1)

    except (KeyboardInterrupt, ServiceExit):
        # Exception handler for console-based shutdown.

        logging.info("--- Caught keyboard interrupt! Shutting down gracefully. ---")
        api_stop(switch='all')
        module_shutdown()

    except Exception as e:
        # Exception for any other errors that I'm not explicitly handling.

        t_ui.shutdown_flag.set()
        t_ui.join()
        t_work.shutdown_flag.set()
        t_work.join()

        print(("\nOS error {0}".format(e)))
        logging.exception('**** OS Error ****')

if __name__ == "panel_gen":
    # The below gets run if this code is imported as a module.
    # It skips lots of setup steps.

    config = ConfigParser()
    config.read('/etc/panel_gen.conf')
    AMI_ADDRESS = config.get('ami', 'address')
    AMI_PORT = config.get('ami', 'port')
    AMI_USER = config.get('ami', 'user')
    AMI_SECRET = config.get('ami', 'secret')

    NXX = list(map(int,config.get('nxx', 'nxx').split(",")))    # Gross!

    # If logfile does not exist, create it so logging can write to it.
    try:
        with open('/var/log/panel_gen/calls.log', 'a') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO,
            datefmt='%m/%d/%Y %I:%M:%S %p')
    except IOError:
        with open('/var/log/panel_gen/calls.log', 'w') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO,
            datefmt='%m/%d/%Y %hh:%M:%S %p')

    # Connect to AMI
    try:
        ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET)
    except:
        #logging.error('AMI connection failed. This will break things.')
        #sys.exit('Failed to connect to Asterisk AMI. Is Asterisk running?')
        logging.error("all that junk", exc_info=True)

    # We call parse_args here just to set some defaults. Otherwise
    # not used when running as module.
    parse_args()

    # Make some switches.
    make_switch(args)


    lines = []
    logging.info('Starting panel_gen as thread from http_server')

    try:
        t_work = work_thread()
        t_work.daemon = True
        t_work.start()

        sleep(.5)

    except Exception:
        api_stop(switch='all')

#!/usr/bin/python
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
import curses
import re
import threading
from configparser import ConfigParser
from datetime import datetime
from marshmallow import Schema, fields, post_load
from tabulate import tabulate
from numpy import random
from pycall import CallFile, Call, Application, Context
from asterisk.ami import AMIClient, EventListener, AMIClientAdapter, AutoReconnect


class Line():
    """
    This class defines Line objects.

    self.switch:        Set to an instantiated switch object. Usually Rainier,
                        Adams, or Lakeview
    self.kind:          Type of switch for above objects. "panel, 1xb, 5xb"
    self.status:        0 = OnHook, 1 = OffHook
    self.term:          String containing the 7-digit terminating line.
    self.timer:         Starts with a standard random.gamma, then gets set
                        subsequently by the call volume attribute of the switch.
    self.ident:         Integer starting with 0 that identifies the line.
    self.chan:          DAHDI channel. We get this from asterisk.ami once call
                        is in progress. See on_DialBegin()
    self.ast_status:    Returned from AMI. Indicates status of line from
                        Asterisk's perspective.
    self.is_api:        Used to identify an API one-shot line in the console
                        interface.
    self.api_indicator: See above. Is set to "***" if a line is a temp API line.
    """

    def __init__(self, ident, switch, **kwargs):
        self.switch = switch
        self.kind = switch.kind
        self.status = 0

        if args.l:
            self.term = args.l
        else:
            self.term = self.pick_next_called(term_choices)

        self.timer = int(random.gamma(3,4))
        self.ident = ident
        self.human_term = phone_format(str(self.term)) 
        self.chan = '-'
        self.ast_status = 'on_hook'
        self.is_api = kwargs.get('is_api', False)
        self.api_indicator = ""

    def __repr__(self):
        return '<Line({self.ident!r})>'.format(self=self)

    def tick(self):
        """
        Decrement line timer by 1 every second until it reaches 0.
        Manages the self.status state machine by placing calls or hanging up,
        depending on line.status.

        Returns the new value of self.timer
        """
        if self.switch.running == False:
            self.switch.running = True
        self.timer -= 1
        if self.timer <= 0:
            if self.status == 0:
                if self.switch.is_dialing < self.switch.max_dialing:
                    self.call()
                    self.status = 1
                else:
                    # Back off until some calls complete.
                    self.timer = int(round(random.gamma(4,4)))
                    logging.warning("Exceeded sender limit: %s with %s calls " +
                        "dialing. Delaying call.",
                        self.switch.max_dialing, self.switch.is_dialing)
            elif self.status == 1:
                self.hangup()
        return self.timer

    def pick_next_called(self, term_choices):
        """
        Returns a string containing a 7-digit number to call.

        args.l:             Command line arg for called line
        term_choices:       List of office codes we can dial
                            set as a global in __main__
        """
        # As of 1/8/2020, current nxx should be 722,232,832,275,365,830
        # in that order. This is specified in the config file.
        # Have to do some weirdness here to get the values from config,
        # which come in as a list of strings, then convert to a list of
        # ints.
        nxx_config = config.get('nxx','nxx')
        nxx_string = nxx_config.split(",")
        nxx = list(map(int, nxx_string))

        if args.l:                      # If user specified a line
            term = args.l               # Set term line to user specified
        else:
            if term_choices == []:
                term_office = random.choice(nxx, p=self.switch.trunk_load)
            else:
                term_office = random.choice(term_choices)

            # Choose a sane number that appears on the line link or final
            # frame of the switches that we're actually calling. If something's
            # wrong, then assert false, so it will get caught.
            # Some number wackiness going on here because when we pull from
            # config, the values are always str() so we have to int() them if
            # we are calling thru Lakeview. This is so we can prepend a '0'.

            if term_office == 722 or term_office == 365:
                term_station = random.randint(Rainier.line_range[0], Rainier.line_range[1])
            elif term_office == 832:
                term_station = "%04d" % int(random.choice(Lakeview.line_range))
            elif term_office == 232:
                term_station = random.choice(Adams.line_range)
            elif term_office == 275:
                term_station = random.randint(Step.line_range[0], Step.line_range[1])
            elif term_office == 830:
                term_station = random.randint(ESS3.line_range[0], ESS3.line_range[1])
            else:
                logging.error("No terminating line available for this office.")

            term = int(str(term_office) + str(term_station))
        logging.debug('Terminating line selected: %s', term)
        self.human_term = phone_format(str(term)) 
        return term

    def call(self, **kwargs):
        """
        Places a call. Returns nothing.

        kwargs:
            originating_switches:     switch call is coming from
            line:            line placing the call
            timer:           duration of the call

        """

        CHANNEL = 'DAHDI/{}'.format(self.switch.dahdi_group) + '/wwww%s' % self.term

        self.timer = self.switch.newtimer()

        # Wait value to pass to Asterisk dialplan if not using API to start call
        wait = self.timer + 15

        # The kwargs come in from the API. The following lines handle them
        # and set up the special call case outside of the normal program flow.
        for key, value in list(kwargs.items()):
            if key == 'originating_switches':
                switch = value
            if key == 'line':
                line = value
            if key == 'timer':
                self.timer = value
                wait = value

        # If the line comes from the API /call/{switch}/{line} then this
        # line is temporary. This sets up special handling so that the status
        # starts at "1", which will cause hangup() to hang up the call and
        # delete the line when the call is done.
        if self.is_api == True:
            self.status = 1
            self.api_indicator = "***"

        # Set the vars to actually pass to call file
        vars = {'waittime': wait}

        # Make the .call file amd throw it into the asterisk spool.
        # Pass control of the call to the sarah_callsim context in
        # the dialplan. This will allow me to better interact with
        # Asterisk from here.
        c = Call(CHANNEL, variables=vars)
        con = Context('sarah_callsim','s','1')
        cf = CallFile(c, con)
        cf.spool()


    def hangup(self):
        """
        Hangs up a call.

        Checks if a call is being dialed during hangup.
        If so, we need to decrement the dialing counter.
        Then, send an AMI hangup request to Asterisk,
        set status, chan, and ast_status back to normal values,
        set a new timer, and set the next called line.
        """

        if self.ast_status == 'Dialing':
            logging.debug('Hangup while dialing %s on DAHDI %s', self.term, self.chan)
            self.switch.is_dialing -= 1

        # This try block exists because sometimes the AMI likes to disconnect
        # us for no reason. When this happens, calls fail to hangup properly.
        # The hope here is that we can attempt to reconnect on the fly and
        # hangup again.
        try:
            adapter.Hangup(Channel='DAHDI/{}-1'.format(self.chan))
        except Exception:
            logging.error('AMI failed to stop calls. Attempting to recover.')
            try:
                ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET)
                adapter.Hangup(Channel='DAHDI/{}-1'.format(self.chan))
                logging.info('AMI connection recovered!')
            except Exception:
                logging.error('AMI recovery failed.')

        logging.debug('Hung up %s on DAHDI/%s from %s', self.term, self.chan, self.switch.kind)
        self.status = 0
        self.chan = '-'
        self.ast_status = 'on_hook'
        self.switch.on_call -= 1

        # Delete the line if we are just doing a one-shot call from the API.
        if self.is_api == True:
            logging.info("Deleted API one-shot line.")
            currentlines = [l for l in lines if l.switch == self.switch]

            del lines[self.ident]
            if len(currentlines) <= 1:
                self.switch.running = False
        self.timer = self.switch.newtimer()
        self.term = self.pick_next_called(term_choices)


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
    trunk_load:	    List of max_nxx used to compute load on trunks.
    line_range:	    Range of acceptable lines to dial when calling this office.
    """

    def __init__(self, **kwargs):
        self.kind = kwargs.get('kind',"")
        kind = self.kind
        self.running = False
        self.max_dialing = config.getint(kind, 'max_dialing')
        self.is_dialing = 0
        self.on_call = 0
        self.dahdi_group = config.get(kind, 'dahdi_group')
        self.traffic_load = "normal"
        self.lines_normal = config.getint(kind, 'lines_normal')
        self.lines_heavy = config.getint(kind, 'lines_heavy')
        self.max_722 = float(config[kind]['max_722'])
        self.max_232 = float(config[kind]['max_232'])
        self.max_832 = float(config[kind]['max_832'])
        self.max_275 = float(config[kind]['max_275'])
        self.max_365 = float(config[kind]['max_365'])
        self.max_830 = float(config[kind]['max_830'])
        self.trunk_load = [self.max_722, self.max_232,
                self.max_832, self.max_275, self.max_365, self.max_830]
        lr = config.get(kind, 'line_range')
        self.line_range = lr.split(",")
        self.l_ga = config.get(kind, 'l_gamma')
        self.n_ga = config.get(kind, 'n_gamma')
        self.h_ga = config.get(kind, 'h_gamma')

    def __repr__(self):
       return "<Switch(name={self.kind!r})>".format(self=self)

    def newtimer(self):
        """
        Returns timer back to Line() object. Checks to see
        if arguments have been passed in at runtime. If so,
            args.w:         User-specified wait time
            args.v:         User-specified call volume

        If no args have been passed in (the more likely situation)
        Then see if running as __main__ or as a module and act
        accordingly.
        """

        if args.w:
            timer = args.w
        else:
            if args.v == 'light' or self.traffic_load == 'light':
                a,b = (int(x) for x in self.l_ga.split(","))
                timer = int(round(random.gamma(a,b)))
            elif args.v == 'heavy' or self.traffic_load == 'heavy':
                a,b = (int(x) for x in self.h_ga.split(","))
                timer = int(round(random.gamma(a,b)))
            elif args.v == 'normal' or self.traffic_load == 'normal':
                a,b = (int(x) for x in self.n_ga.split(","))
                timer = int(round(random.gamma(a,b)))
        return timer

# +-----------------------------------------------+
# |                                               |
# | # <----- BEGIN BOOKKEEPING STUFF -----> #     |
# |   This is uncategorized bookkeeping for       |
# |   the rest of the program. Includes           |
# |   getting AMI events, and parsing args.       |
# |                                               |
# +-----------------------------------------------+

def on_DialBegin(event, **kwargs):
    """
    Callback function for DialBegin AMI events. Extracts DialString
    and DestChannel and stores it to variables in each line.
    Increments the "is_dialing" counter.
    """

    output = str(event)
    DialString = re.compile('(?<=w)(\d{7})')
    DB_DestChannel = re.compile('(?<=DestChannel\'\:\s.{7})([^-]*)')

    DialString = DialString.findall(output)
    DB_DestChannel = DB_DestChannel.findall(output)

    for l in lines:
        if DialString[0] == str(l.term) and l.ast_status == 'on_hook':
            l.chan = DB_DestChannel[0]
            logging.debug('Line %s is on channel %s', l.ident, l.chan)
            l.ast_status = 'Dialing'
            l.switch.is_dialing += 1
            l.switch.on_call +=1
            logging.debug('Calling %s on DAHDI/%s from %s', l.term, l.chan, l.switch.kind)

def on_DialEnd(event, **kwargs):
    """
    Callback function for DialEnd AMI events. Sets state to "Ringing".
    Decrements the "is_dialing" counter.

    """
    output = str(event)
    DE_DestChannel = re.compile('(?<=DestChannel\'\:\s.{7})([^-]*)')
    DE_DestChannel = DE_DestChannel.findall(output)

    for l in lines:
        if DE_DestChannel[0] == str(l.chan) and l.ast_status == 'Dialing':
            l.ast_status = 'Ringing'
            l.switch.is_dialing -= 1
            logging.debug('on_DialEnd with %s calls dialing', l.switch.is_dialing)


def parse_args():
    # Gets called at runtime and parses arguments given on command line.
    # If no arguments are presented, the program will run with default
    # mostly sane options.

    parser = argparse.ArgumentParser(description='Generate calls to electromechanical switches. '
            'Defaults to originate a sane amount of calls from the panel switch if no args are given.')
    parser.add_argument('-a', metavar='lines', type=int, choices=[1,2,3,4,5,6,7,8,9,10],
            help='Maximum number of active lines.')
    parser.add_argument('-l', metavar='line', type=int,
            help='Call only a particular line. Can be used with the -d option for placing test '
            'calls to a number over and over again.')
    parser.add_argument('-o', metavar='switch', type=str, nargs='?', action='append', default=[],
            choices=['1xb','5xb','panel','all','722', '832', '232'],
            help='Originate calls from a particular switch. Takes either 3 digit NXX values '
            'or switch name.  1xb, 5xb, panel, or all. Default is panel.')
    parser.add_argument('-t', metavar='switch', type=str, nargs='?', action='append', default=[],
            choices=['1xb','5xb','panel','office','step', '722', '832', '232', '365', '275'],
            help='Terminate calls only on a particular switch. Takes either 3 digit NXX values '
            'or switch name. Defaults to sane options for whichever switch you are originating from.')
    parser.add_argument('-v', metavar='volume', type=str, default='normal',
            help='Call volume is a proprietary blend of frequency and randomness. Can be light, '
            'normal, or heavy. Default is normal, which is good for average load.')
    parser.add_argument('-w', metavar='seconds', type=int, help='Use with -d option to specify '
            'wait time between calls.')
    parser.add_argument('-z', metavar='seconds', type=int,
            help='Use with -d option to specify call duration.')
    parser.add_argument('-log', metavar='loglevel', type=str, default='INFO',
            help='Set log level to WARNING, INFO, DEBUG.')

    global args
    args = parser.parse_args()
    return args

def phone_format(n):
    return format(int(n[:-1]), ",").replace(",", "-") + n[-1]

def make_switch(args):
    """ Instantiate some switches so we can work with them later."""

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
        originating_switches.append(ESS3)

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


def make_lines(**kwargs):
    """
    Takes several kwargs. Returns a bunch of lines.

    source:         the origin of the call to this function
    switch:         the switch where the lines will originate on
    originating_switches:    list of originating switches passed in from args
    traffic_load:   light, normal, or heavy
    numlines:       number of lines we should create
    """

    source = kwargs.get('source', '')
    switch = kwargs.get('switch', '')
    traffic_load = kwargs.get('traffic_load', '')
    originating_switches = kwargs.get('originating_switches','')
    numlines = kwargs.get('numlines', '')

    new_lines = []

    if source == 'main':
        new_lines = [Line(n, switch) for switch in originating_switches for n in range(switch.lines_normal)]
    elif source == 'api':
        new_lines = [Line(n, switch, is_api=True) for n in range(numlines)]
        if traffic_load != '':
            switch.traffic_load = str(traffic_load)
    return new_lines

def start_ui():
    """
    This starts the panel_gen UI. Only useful when run as module.
    When run as __main__, the UI is started for you.

    :return:    Nothing
    :args:      Nothing
    """
    global t

    try:
        t = ui_thread()
        t.daemon = True
        t.start()
    except Exception as e:
        print(e)

def ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET):
    global client
    global adapter
    client = AMIClient(address=AMI_ADDRESS, port=int(AMI_PORT))
    adapter = AMIClientAdapter(client)
    #AutoReconnect(client)
    future = client.login(username=AMI_USER, secret=AMI_SECRET)
    if future.response.is_error():
        raise Exception(str(future.response))

    # These listeners are for the AMI so I can catch events.
    client.add_event_listener(on_DialBegin, white_list = 'DialBegin')
    client.add_event_listener(on_DialEnd, white_list = 'DialEnd')


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
        if t.started == True:
            ui_running = True
    except Exception as e:
        pass

    result = dict([
        ('name', __name__),
        ('app_running', w.is_alive),
        ('is_paused', w.paused),
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

    mode:       'demo' or ''. Demo mode will start with preset params.
    source:     Used to log where the start request came from.
    switch:     Specifies which switch to start calls on.

    """

    global lines
    mode = kwargs.get('mode', '')
    source = kwargs.get('source', '')
    switch = kwargs.get('switch', '')

    if source == 'web':
        logging.info("App requested START on %s", switch)
    elif source == 'key':
        logging.info('Key operated: START on %s', switch)
    else:
        logging.info('I dont know why, but we are starting on %s', switch)

    if w.is_alive == True:
        for i in originating_switches:
            if switch == i.kind:
                if i.running == True:
                    logging.warning("%s is running. Can't start twice.", i)
                elif i.running == False:
                    # Reset the dialing counter for safety.
                    i.is_dialing = 0

                    if i.traffic_load == 'heavy':
                        numlines = i.lines_heavy
                    elif i.traffic_load == 'normal':
                        numlines = i.lines_normal

                    if mode == 'demo':
                        if i == Adams:
                            # Carve out a special case for Sundays. This was requested
                            # by museum volunteers so that we can give tours of the
                            # step and 1XB without interruption by the this program.
                            # This will only be effective if the key is operated.
                            # Will have no impact when using web app.
                            if datetime.today().weekday() == 6:
                                if source == 'key':
                                    i.trunk_load = [.15, .85, .0, .0, .0, .0]
                                    logging.info('Its Sunday!')
                            new_lines = make_lines(switch=i, numlines=numlines,
                                        traffic_load='heavy', source='api')
                        else:
                            new_lines = make_lines(switch=i, numlines=numlines, source='api')
                    elif mode != 'demo':
                        new_lines = [Line(n, i) for n in range(i.lines_normal)]
                    for l in new_lines:
                        lines.append(l)
                    i.running = True
                    logging.info('Appending %s lines to %s', len(new_lines), switch)

                try:
                    new_lines
                    lines_created = len(new_lines)
                    result = get_info()
                    return result
                except NameError as e:
                    logging.error(e)
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

            # Can't do this unless we're running as root.
            #system("asterisk -rx \"channel request hangup all\" > /dev/null 2>&1")

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
                s.is_dialing = 0
                s.on_call = 0
    except Exception as e:
        logging.warning("Exception occurred while stopping calls.")
        logging.warning(e)
        return False

    return get_info()

def call_now(**kwargs):
    """
    Immediately places a call from switch to destination. The line is
    deleted when the call timer expires.

    switch:             Switch to originate call on.
    term_line:          Destination number to call.
    one_shot_timer:     Number of seconds before hangup.
    """

    schema = LineSchema()

    switch = kwargs.get('switch','')
    term_line = kwargs.get('destination','')
    one_shot_timer = int(kwargs.get('timer',''))

    logging.info('API requested one-shot call on %s', switch)

    # Validates switch input.
    if switch == 'panel':
        switch = Rainier
    elif switch == '5xb':
        switch = Adams
    elif switch == '1xb':
        switch = Lakeview
    elif switch == '3ess' or 'ess':
        switch = ESS3
    else:
        logging.warning("API one-shot switch failed validation check.")
        return False

    # Validates line input. If sane, set up line for
    # immediate calling.
    if len(term_line) == 7:
        api_lines = make_lines(source='api', switch=switch, numlines=1) 
        api_lines[0].term = term_line
        api_lines[0].human_term = phone_format(str(term_line))
        lines.append(api_lines[0])
        api_lines[0].call(originating_switches=switch, timer=one_shot_timer)
        api_lines[0].tick()
        result = schema.dump(api_lines[0])
        return result
    else:
        logging.warning("API one-shot line failed validation check.")
        return False

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

    # Iterate over our originating_switches and see if the switch
    # that the API asked for matches an existing switch.
    for i in originating_switches:
        # If the type of switch matches the type we're trying to edit
        if i.kind == kwargs.get("kind", ""):
            # Wipe out the top parameter, because I said so
            del kwargs['kind']
            current_load = i.traffic_load
            # Lets iterate over the parameters we can work with.
            for k,v in kwargs.items():
                for k1 in v.items():
                    desired_load = k1[1]
                    if i.traffic_load != desired_load:
                        i.traffic_load = desired_load
                        if i.running == True:
                            if i.traffic_load == 'heavy':
                                create_line(switch=i, numlines=2)
                            elif i.traffic_load == 'normal':
                                delete_line(switch=i, numlines=2)
                        logging.info("Traffic on %s changed to %s", 
                                    i.kind, i.traffic_load)
            result.append(schema.dump(i))
    if result != []:
        return result
    else:
        return False

# +-----------------------------------------------+
# |                                               |
# |  Below is the class for the screen. These     |
# |  methods are called by the UI thread when     |
# |  it needs to interact with the user, either   |
# |  by getting keys, or drawing things.          |
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
            if w.paused == False:
                self.pausescreen()
                key = stdscr.getch()
                if key == ord(' '):
                    self.resumescreen()
            elif w.paused == True:
                w.resume()
        # u: add a line to the first switch.
        if key == ord('u'):
            lines.append(Line(7, originating_switches[0]))
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
        w.pause()
        self.stdscr.nodelay(0)
        pause_scr = self.stdscr.subwin(rows_size, half_cols, x_start_row, y_start_col)
        pause_scr.box()
        pause_scr.addstr(2, int(half_cols/2) - 5, "P A U S E D", curses.color_pair(1))
        pause_scr.bkgd(' ', curses.color_pair(2))
        self.stdscr.addstr(y-1,0,"Spacebar: pause/resume, ctrl + c: quit", curses.A_BOLD)
        pause_scr.refresh()

    def resumescreen(self):
        # This should erase the paused window and refresh the screen.
        # It erases the window ok, but drawing doesn't resume unless the user
        # hits a key in the console window. I don't know why, and I've
        # tried a bunch of different things. The work thread appears to
        # resume OK.

        w.resume()
        self.stdscr.nodelay(1)
        self.stdscr.refresh()
        self.draw(self.stdscr, lines, self.y, self.x)
        logging.info("Resumed")


    def draw(self, stdscr, lines, y, x):
        # Output handling. make pretty things.
        table = [[n.kind, n.chan, n.human_term, n.timer,
                n.status, n.ast_status, n.api_indicator] for n in lines]
        stdscr.erase()
        stdscr.addstr(0,5," __________________________________________")
        stdscr.addstr(1,5,"|                                          |")
        stdscr.addstr(2,5,"|  Rainier Full Mechanical Call Simulator  |")
        stdscr.addstr(3,5,"|__________________________________________|")
        stdscr.addstr(6,0,tabulate(table, headers=["switch", "channel", "term",
                    "tick", "state", "asterisk", "api"],
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


#-->                      <--#
# Work and UI threads are below
#-->                      <--#

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
            logging.error(e)

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
    # once per second. This evaluates the timers and makes call processing
    # decisions.

    def __init__(self):

        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()
        self.paused = False
        self.paused_flag = threading.Condition(threading.Lock())

        # We get here from __main__, and this kicks the loop into gear.

        logging.info('--- Started panel_gen ---')

    def run(self):

        while not self.shutdown_flag.is_set():
            self.is_alive = True
            with self.paused_flag:
                while self.paused:
                    self.paused_flag.wait()

            # The main loop that kicks everything into gear.
                for l in lines:
                    l.tick()
                sleep(1)

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
    Attempts to cleanly exit panel_gen
    """

    try:
        t.shutdown_flag.set()
        t.join()
    except Exception:
        pass
    w.shutdown_flag.set()
    w.join()

    # Clean exit for logging
    logging.shutdown()

    # Log out of AMI
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

    # Connect to AMI
    try:
        ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET)
    except Exception:
        logging.warning('Failed to connect to Asterisk AMI!')
    
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
            datefmt='%m/%d/%Y %I:%M:%S %p')

    # Parse any arguments the user gave us.
    parse_args()
    make_switch(args)

    logging.info('Originating calls on %s', originating_switches)

    if args.t != []:
        logging.info('Terminating calls on %s', term_choices)

    logging.info('Call volume set to %s', args.v)

    # Here is where we actually make the lines.
    lines = make_lines(source='main', originating_switches=originating_switches)

    try:
        t = ui_thread()
        t.daemon = True
        t.start()
        w = work_thread()
        w.daemon = True
        w.start()

        while True:
            sleep(.5)

    except (KeyboardInterrupt, ServiceExit):
        # Exception handler for console-based shutdown.

        logging.info("--- Caught keyboard interrupt! Shutting down gracefully. ---")
        api_stop(switch='all')
        module_shutdown()

    except Exception as e:
        # Exception for any other errors that I'm not explicitly handling.

        t.shutdown_flag.set()
        t.join()
        w.shutdown_flag.set()
        w.join()

        print(("\nOS error {0}".format(e)))
        logging.exception('**** OS Error ****')

if __name__ == "panel_gen":
    # The below gets run if this code is imported as a module.
    # It skips lots of setup steps.

    #global AMI_ADDRESS
    #global AMI_PORT
    #global AMI_USER
    #global AMI_SECRET

    config = ConfigParser()
    config.read('/etc/panel_gen.conf')
    AMI_ADDRESS = config.get('ami', 'address')
    AMI_PORT = config.get('ami', 'port')
    AMI_USER = config.get('ami', 'user')
    AMI_SECRET = config.get('ami', 'secret')

    # Connect to AMI
    try:
        ami_connect(AMI_ADDRESS, AMI_PORT, AMI_USER, AMI_SECRET)
    except Exception:
        logging.warning('Failed to connect to Asterisk AMI!')

    # We call parse_args here just to set some defaults. Otherwise
    # not used when running as module.
    parse_args()

    # Make some switches.
    make_switch(args)


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
            datefmt='%m/%d/%Y %I:%M:%S %p')

    lines = []
    logging.info('Starting panel_gen as thread from http_server')

    try:
        w = work_thread()
        w.daemon = True
        w.start()

        sleep(.5)

    except Exception:
        api_stop(switch='all')

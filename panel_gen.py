#!/usr/bin/python
#---------------------------------------------------------------------#
#                                                                     #
#  A call generator thing for the Rainier Panel switch at the         #
#  Connections Museum, Seattle WA.                                    #
#                                                                     #
#  Written by Sarah Autumn, 2017-2019                                 #
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
from datetime import datetime
from marshmallow import Schema, fields
from tabulate import tabulate
from numpy import random
from pathlib import Path
from pycall import CallFile, Call, Application, Context
from asterisk.ami import AMIClient, EventListener, AMIClientAdapter


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

    def __init__(self, ident, switch):
        self.switch = switch
        self.kind = switch.kind
        self.status = 0

        if args.l:
            self.term = args.l
        else:
            self.term = self.pick_called_line(term_choices)

        self.timer = int(random.gamma(3,4))
        self.ident = ident
        self.chan = '-'
        self.ast_status = 'on_hook'
        self.is_api = False
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
                    self.timer = int(round(random.gamma(5,5)))
                    logging.warning("Exceeded sender limit: %s with %s calls " +
                    "dialing. Delaying call.",
                            self.switch.max_dialing, self.switch.is_dialing)
            elif self.status == 1:
                self.hangup()
        return self.timer

    def pick_called_line(self, term_choices):
        """
        Returns a string containing a 7-digit number to call.

        args.l:             Command line arg for called line
        term_choices:       List of office codes we can dial
                            set as a global in __main__
        """

        if args.l:                      # If user specified a line
            term = args.l               # Set term line to user specified
        else:
            if term_choices == []:
                term_office = random.choice(self.switch.nxx, p=self.switch.trunk_load)
            else:
                term_office = random.choice(term_choices)

            # Choose a sane number that appears on the line link or final
            # frame of the switches that we're actually calling. If something's
            # wrong, then assert false, so it will get caught.
            # Whenever possible, these values should be defined in the switch class.
            # This makes it so we can change these values more easily.

            if term_office == 722 or term_office == 365:
                term_station = random.randint(Rainier.line_range[0], Rainier.line_range[1])
            elif term_office == 832:
                term_station = "%04d" % random.choice(Lakeview.line_range)
            elif term_office == 232:
                term_station = random.choice(Adams.line_range)
            elif term_office == 275:
                term_station = random.randint(Step.line_range[0], Step.line_range[1])
            else:
                logging.error("No terminating line available for this office.")
                assert False


            term = int(str(term_office) + str(term_station))
        logging.debug('Terminating line selected: %s', term)
        return term

    def call(self, **kwargs):
        """
        Places a call. Returns nothing.

        kwargs:
            orig_switch:     switch call is coming from
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
            if key == 'orig_switch':
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
        Check if a call is being dialed during hangup.
        If so, we need to decrement the dialing counter.
        Then, send an AMI hangup request to Asterisk,
        set status, chan, and ast_status back to normal values,
        set a new timer, and set the next called line.
        """

        if self.ast_status == 'Dialing':
            logging.debug('Hangup while dialing %s on DAHDI %s', self.term, self.chan)
            self.switch.is_dialing -= 1

        adapter.Hangup(Channel='DAHDI/{}-1'.format(self.chan))

        logging.debug('Hung up %s on DAHDI/%s from %s', self.term, self.chan, self.switch.kind)
        self.status = 0
        self.chan = '-'
        self.ast_status = 'on_hook'

        # Delete the line if we are just doing a one-shot call from the API.
        if self.is_api == True:
            logging.info("Deleted API one-shot line.")
            currentlines = [l for l in lines if l.switch == self.switch]

            del lines[self.ident]
            if len(currentlines) <= 1:
                self.switch.running = False

        self.timer = self.switch.newtimer()
        self.term = self.pick_called_line(term_choices)

    def update(self, api):
        """ Used by the API PATCH method to update line parameters."""

        for (key, value) in list(api.items()):
            if key == 'switch':
               # 1XB doesn't work for some reason
               # also this needs to validate and return a 406 on failure
                if value == 'panel':
                    self.switch = Rainier
                    self.kind = 'panel'
                if value == '5xb':
                    self.switch = Adams
                    self.kind = '5xb'
                if value == '1xb':
                    self.switch = Lakeivew
                    self.kind = '1xb'
                else:
                    return False
            if key == 'timer':
                # Change the current timer of the line.
                self.timer = value
            if key == 'dahdi_chan':
                # Change which channel a line belongs to.
                # Also might break everything.
                self.chan = value
            if key == 'called_no':
                self.term = value

# <----- END LINE CLASS -----> #

# <----- BEGIN SWITCH CLASSES ------> #

class panel():
    """
    This class is parameters and methods for the panel switch.

    kind:           Generic name for type of switch.
    running:        Whether or not switch is running.
    max_dialing:    Set based on sender capacity.
    is_dialing:     Records current number of calls in Dialing state.
    dahdi_group:    Passed to Asterisk when call is made.
    api_volume:     String that contains "light", "heavy", or "".
                    Sets the random.gamma distribution for generating
                    new call timers.
    max_calls:      Maximum concurrent calls the switch can handle.
    max_nxx:        Values for trunk load. Determined by how many
                    outgoing trunks we have provisioned on the switch.
    nxx:            List of office codes we can dial. Corresponds directly
                    to max_nxx.
    trunk_load:	    List of max_nxx used to compute load on trunks.
    line_range:	    Range of acceptable lines to dial when calling this office.
    """

    def __init__(self):
        self.kind = "panel"
        self.running = False
        self.max_dialing = 5
        self.is_dialing = 0
        self.dahdi_group = "r6"
        self.api_volume = ""

        if args.d:
            self.max_calls = 1
        elif args.a:
            self.max_calls = args.a
        else:
            self.max_calls = 4

        self.max_nxx1 = .5
        self.max_nxx2 = .3
        self.max_nxx3 = .2
        self.max_nxx4 = .0
        self.nxx = [722, 365, 232, 832]
        self.trunk_load = [self.max_nxx1, self.max_nxx2,
                self.max_nxx3, self.max_nxx4]
        self.line_range = [4000,5999]

    def __repr__(self):
        return("{}".format(self.__class__.__name__))

    def newtimer(self):
        """
        Returns timer back to Line() object. Checks to see
        if arguments have been passed in at runtime. If so,
            args.d:         Deterministic Mode
            args.w:         User-specified wait time
            args.v:         User-specified call volume

        If no args have been passed in (the more likely situation)
        Then see if running as __main__ or as a module and act
        accordingly.
        """

        if args.d:
            if args.w:
                self.timer = args.w
            else:
                self.timer = 15
        else:
            if __name__ == '__main__':
                if args.v == 'light':
                    timer = int(round(random.gamma(20,8)))
                elif args.v == 'heavy':
                    timer = int(round(random.gamma(5,7)))
                else:
                    timer = int(round(random.gamma(4,14)))

            if __name__ == 'panel_gen':
                if self.api_volume == 'light':
                    timer = int(round(random.gamma(20,8)))
                elif self.api_volume == 'heavy':
                    timer = int(round(random.gamma(5,7)))
                else:
                    timer = int(round(random.gamma(4,14)))

        return timer


class xb1():
    # This class is for the No. 1 Crossbar.
    # For a description of each of these lines, see the panel class above.

    def __init__(self):
        self.kind = "1xb"
        self.running = False
        self.max_dialing = 2
        self.is_dialing = 0
        self.dahdi_group = "r11"
        self.api_volume = ""

        if args.d:
            self.max_calls = 1
        elif args.a:
            self.max_calls = args.a
        else:
            self.max_calls = 2

        self.max_nxx1 = .5
        self.max_nxx2 = .5
        self.max_nxx3 = 0
        self.max_nxx4 = 0
        self.nxx = [722, 832, 232]
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]
        self.line_range = [105,107,108,109,110,111]

    def __repr__(self):
        return("{}('{}')".format(self.__class__.__name__, self.running))

    def newtimer(self):
        """
        See similar function in panel() class for documentation.
        """

        if args.d:
            if args.w:
                self.timer = args.w
            else:
                self.timer = 15
        else:
            if __name__ == '__main__':
                if args.v == 'light':
                    timer = int(round(random.gamma(20,8)))
                elif args.v == 'heavy':
                    timer = int(round(random.gamma(5,7)))
                else:
                    timer = int(round(random.gamma(4,14)))

            if __name__ == 'panel_gen':
                if self.api_volume == 'heavy':
                    timer = int(round(random.gamma(5,7)))
                elif self.api_volume == 'light':
                    timer = int(round(random.gamma(20,8)))
                else:
                    timer = int(round(random.gamma(4,14)))

        return timer


class xb5():
    # This class is for the No. 5 Crossbar.
    # For a description of these line, see the panel class, above.

    def __init__(self):
        self.kind = "5xb"
        self.running = False
        self.max_dialing = 7
        self.is_dialing = 0
        self.dahdi_group = "r5"
        self.api_volume = ""

        if args.d:
            self.max_calls = 1
        elif args.a:
            self.max_calls = args.a
        else:
            self.max_calls = 4

        self.max_nxx1 = .2
        self.max_nxx2 = .1
        self.max_nxx3 = .6
        self.max_nxx4 = .1
        self.nxx = [722, 832, 232, 275]
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3, self.max_nxx4]
        self.line_range = [1330,1435,9072,9073,1274,1485,1020,5852,
                1003,6766,6564,1076,5018,1137,9138,1165,1309,9485,
                9522,9361,1603,1704,9929,1939,1546,1800,5118,9552,
                4057,1055,1035,9267,1381,1470,9512,1663,1841,1921]

    def __repr__(self):
        return("{}('{}')".format(self.__class__.__name__, self.running))

    def newtimer(self):
        """
        See similar function in panel() class for documentation.
        """

        if args.d:
            if args.w:
                self.timer = args.w
            else:
                self.timer = 15
        else:
            if __name__ == '__main__':
                if args.v == 'light':
                    timer = int(round(random.gamma(20,8)))
                elif args.v == 'heavy':
                    timer = int(round(random.gamma(5,7)))
                else:
                    timer = int(round(random.gamma(4,14)))

            if __name__ == 'panel_gen':
                if self.api_volume == 'heavy':
                    timer = int(round(random.gamma(5,4)))
                elif self.api_volume == 'light':
                    timer = int(round(random.gamma(20,8)))
                else:
                    timer = int(round(random.gamma(4,14)))

        return timer


class step():
    # This class is for the SxS office. It's very minimal, as we are not currently
    # originating calls from there, only completing them from the 5XB.

    def __init__(self):
        self.kind = "Step"
        self.line_range = [4124,4127]


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
    DB_DestChannel = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')

    DialString = DialString.findall(output)
    DB_DestChannel = DB_DestChannel.findall(output)

    for l in lines:
        if DialString[0] == str(l.term) and l.ast_status == 'on_hook':
            logging.debug('DialString match %s and %s', DialString[0], str(l.term))
            l.chan = DB_DestChannel[0]
            l.ast_status = 'Dialing'
            l.switch.is_dialing += 1
            logging.debug('Calling %s on DAHDI %s from %s', l.term, l.chan, l.switch.kind)

def on_DialEnd(event, **kwargs):
    """
    Callback function for DialEnd AMI events. Sets state to "Ringing".
    Decrements the "is_dialing" counter.

    """
    output = str(event)
    DE_DestChannel = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')
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
    parser.add_argument('-d', action='store_true',
            help='Deterministic mode. Eliminate timing randomness. Places one call at a time. '
            'Ignores -a and -v options entirely. Use with -l.')
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
    make_switch(args)

def make_switch(args):
    """ Instantiate some switches so we can work with them later."""

    global Rainier
    global Adams
    global Lakeview
    global Step

    Rainier = panel()
    Adams = xb5()
    Lakeview = xb1()
    Step = step()

    global orig_switch
    orig_switch = []

    if __name__ == 'panel_gen':
        orig_switch.append(Rainier)
        orig_switch.append(Adams)
        orig_switch.append(Lakeview)

    if __name__ == '__main__':

        for o in args.o:
            if o == 'panel' or o == '722':
                orig_switch.append(Rainier)
            elif o == '5xb' or o == '232':
                orig_switch.append(Adams)
            elif o == '1xb' or o == '832':
                orig_switch.append(Lakeview)
            elif o == 'all':
                orig_switch.extend((Lakeview, Adams, Rainier))

        if args.o == []:
            orig_switch.append(Rainier)

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

    return args

def make_lines(**kwargs):
    """
    Takes several kwargs. Returns a bunch of lines.

    source:         the origin of the call to this function
    switch:         the switch where the lines will originate on
    orig_switch:    list of originating switches passed in from args
    traffic_load:   light, medium, or heavy
    numlines:       number of lines we should create
    """

    source = kwargs.get('source', '')
    switch = kwargs.get('switch', '')
    traffic_load = kwargs.get('traffic_load', '')
    orig_switch = kwargs.get('orig_switch','')
    numlines = kwargs.get('numlines', '')

    new_lines = []

    if source == 'main':
        new_lines = [Line(n, switch) for switch in orig_switch for n in range(switch.max_calls)]
    elif source == 'api':
        new_lines = [Line(n, switch) for n in range(numlines)]
        if traffic_load != '':
            switch.api_volume = str(traffic_load)
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
    ui_running = fields.Boolean()
    is_paused = fields.Boolean()
    num_lines = fields.Integer()

class LineSchema(Schema):
    line = fields.Dict()
    ident = fields.Integer()
    kind = fields.Str()
    switch = fields.Str()
    timer = fields.Integer()
    is_dialing = fields.Boolean()
    ast_status = fields.Str()
    status = fields.Int()
    chan = fields.Str()
    term = fields.Str()
    hook_state = fields.Integer()

class SwitchSchema(Schema):
    switch = fields.Dict()
    kind = fields.Str()
    max_dialing = fields.Integer()
    is_dialing = fields.Integer()
    max_calls = fields.Integer()
    dahdi_group = fields.Str()
    nxx = fields.List(fields.Int())
    trunk_load = fields.List(fields.Str())
    line_range = fields.List(fields.Str())
    running = fields.Boolean()
    timer = fields.Str()
    api_volume = fields.Str()


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

        if switch == 'panel':
            instance = Rainier
        elif switch == '5xb':
            instance = Adams
        elif switch == '1xb':
            instance = Lakeview
        else:
            return False

        if instance.running == True:
            logging.warning("%s is running. Can't start twice.", instance)
        elif instance.running == False:
            if mode == 'demo':
                if instance == Rainier:
                    new_lines = make_lines(switch=instance, numlines=5, source='api')
                elif instance == Adams:
                    
                    # Carve out a special case for Sundays. This was requested
                    # by museum volunteers so that we can give tours of the
                    # step and 1XB without interruption by the this program.
                    # This will only be effective if the key is operated.
                    # Will have no impact when using web app.
                    if datetime.today().weekday() == 6:
                        if source == 'key':
                            Adams.nxx = [232, 722]
                            Adams.trunk_load = [.7, .3]
                            logging.info('Its Sunday!')
                    new_lines = make_lines(switch=instance, numlines=9,
                                traffic_load='heavy', source='api')
                    Adams.api_volume = 'heavy'
                elif instance == Lakeview:
                    new_lines = make_lines(switch=instance, numlines=2, source='api')
            elif mode != 'demo':
                new_lines = [Line(n, instance) for n in range(instance.max_calls)]
            for l in new_lines:
                lines.append(l)
            instance.running = True
            logging.info('Appending %s lines to %s', len(new_lines), switch)

        try:
            new_lines
            lines_created = len(new_lines)
            result = get_info()
            return result
        except NameError:
            return False

def api_stop(**kwargs):
    """
    Immediately hang up all calls, and destroy all lines.

    switch:     Which switch to hangup and stop.
    source:     Where the request came from. Used for logging.
    """

    switch = kwargs.get('switch', '')
    source = kwargs.get('source', '')

    if source == 'web':
        logging.info("App requested STOP on %s", switch)
    elif source == 'key':
        logging.info('Key operated: STOP on %s', switch)
    else:
        logging.info('Stopping, but not sure why!')

    global lines

    # Validate switch input.
    if switch == 'panel':
        instance = Rainier
    elif switch == '5xb':
        instance = Adams
    elif switch == '1xb':
        instance = Lakeview
    elif switch == 'all':
        pass
    else:
        return False
    try:
        if switch == 'all':
            lines = []
            for s in orig_switch:
                s.running = False
                s.is_dialing = 0

            system("asterisk -rx \"channel request hangup all\" > /dev/null 2>&1")

        else:
            deadlines = [l for l in lines if l.kind == switch]
            lines = [l for l in lines if l.kind != switch]
            instance.running = False
            instance.is_dialing = 0

            for i in deadlines:
                i.hangup()

    except Exception as e:
        logging.exception("Exception thrown while stopping calls.")
        return False

    return get_info()

def api_pause():
    # Not used at the moment. Broken.

    if w.paused == False:
        w.pause()
        return get_info()
    else:
        return False

def api_resume():
    # Not used at the moment. Broken.

    if w.paused == True:
        w.resume()
        return get_info()
    else:
        return False

def call_now(**kwargs):
    """
    Immediately places a call from switch to destination. The line is
    deleted when the call timer expires.

    switch:     Switch to originate call on.
    term_line:  Destination number to call.
    """

    schema = LineSchema()

    switch = kwargs.get('switch','')
    term_line = kwargs.get('destination','')

    logging.info('API requested one-shot call on %s', switch)

    # Validates switch input.
    if switch == 'panel':
        switch = Rainier
    elif switch == '5xb':
        switch = Adams
    elif switch == '1xb':
        switch = Lakeview
    else:
        return False

    # The call timer. Can be changed, if needed.
    on_call_time = 18

    # Validates line input. If sane, set up line for
    # immediate calling.
    if len(term_line) == 7:
        lines.append(Line(len(lines), switch))
        calling_line = len(lines) - 1
        lines[calling_line].is_api = True
        lines[calling_line].timer = 1
        lines[calling_line].term = term_line
        lines[calling_line].call(orig_switch=switch, timer=on_call_time)

        result = schema.dump(lines[calling_line])
        return result
    else:
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
    for l in lines:
        if api_ident == l.ident:
            result.append(schema.dump(lines[api_ident]))

    if result == []:
        return False
    else:
        return result

def create_line(switch):
    # Creates a new line using default parameters.
    # lines.append uses the current number of lines in list
    # to create the ident value for the new line.

    schema = LineSchema()
    result = []

    if switch == 'panel':
        lines.append(Line(len(lines), Rainier))
        result.append(len(lines) - 1)
    if switch == '5xb':
        lines.append(Line(len(lines), Adams))
        result.append(len(lines) - 1)
    if switch == '1xb':
        lines.append(Line(len(lines), Lakeview))
        result.append(len(lines) - 1)

    if result == []:
        return False
    else:
        return result

def delete_all_lines():
    # This feels like a really dirty way to do this, but here it is.
    # Deletes all lines immediately. Lists are hard.

    logging.info("API requested delete all lines.")
    while len(lines) > 0:
        del lines[0]
    if len(lines) == 0:
        return True
    else:
        return False

def delete_line(ident):
    # Deletes a specific line passed in via ident.

    global lines
    api_ident = int(ident)
    result = []
    lines = [l for l in lines if l.ident != api_ident]
    result.append(api_ident)
    if result == []:
        return False
    else:
        return result

def update_line(**kwargs):
    # Updates a given line with new parameters.

    schema = LineSchema()

    api_ident = kwargs.get("ident", "")
    # Pull the line ident out of the dict the API passed in.
    for i,  o in enumerate(lines):
        if o.ident == int(api_ident):
            parameters = kwargs['line']
            result = schema.load(parameters)
            outcome = o.update(result)
            return schema.dump(o)

def get_all_switches():
    """ Returns formatted list of all switches"""

    schema = SwitchSchema()
    result = [schema.dump(n) for n in orig_switch]
    return result

def get_switch(kind):
    # Gets the parameters for a particular switch object.

    schema = SwitchSchema()
    result = []

    if kind == 'panel':
        result.append(schema.dump(Rainier))
    if kind == '5xb':
        result.append(schema.dump(Adams))
    if kind == '1xb':
        result.append(schema.dump(Lakeview))

    if result == []:
        return False
    else:
        return result

def create_switch(kind):

    if 'panel' not in orig_switch:
        if kind == 'panel':
            orig_switch.append(Rainier)
    if '5xb' not in orig_switch:
        if kind == '5xb':
            orig_switch.append(Adams)
    if '1xb' not in orig_switch:
        if kind == '1xb':
            orig_switch.append(Lakeview)
    
    if orig_switch != []:
        return orig_switch
    else:
        return False

def update_switch(**kwargs):
    # Not used at the moment. Broken.

    schema = SwitchSchema()

    # Pull the switch type out of the dict the API passed in.
    api_switch_type = kwargs.get("kind", "")

    # Enumerate our local orig_switch and see if the switch
    # that the API asked for matches an existing switch.
    for i, o in enumerate(orig_switch):
        # If the type of switch matches the type we're trying to edit
        if o.kind == api_switch_type:
            # Make sure we're editing the instance of the switch
            if o.kind == "panel":
                switch = Rainier
            elif o.kind == "5xb":
                switch = Adams
            elif o.kind == "1xb":
                switch = Lakeview
    #Pull in the parameters
    parameters = kwargs
    # Wipe out the top parameter, because I said so
    del parameters['kind']
    result = schema.load(parameters)
    logging.info(result)

    return schema.dump(switch)

def delete_switch(kind):
    # This "works" but it actually doesn't cause calls to stop on a switch.
    # orig_switch is only used with line creation at the start of execution.
    # after that, lines already have the property of their switch, so
    # I need to find a way to actually stop calls to a switch when it
    # no longer exists.

    result = []
    for i, o in enumerate(orig_switch):
        if o.kind == kind:
            del orig_switch[i]
            result.append(o.kind)
            logging.info("API requested delete switch %s", o.kind)

    if result == []:
        return False
    else:
        return result


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
            lines.append(Line(7, orig_switch[0]))
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
        half_cols = x/2
        rows_size = 5
        x_start_row = y - 9
        y_start_col = half_cols - half_cols / 2

        w.pause()
        self.stdscr.nodelay(0)
        pause_scr = self.stdscr.subwin(rows_size, half_cols, x_start_row, y_start_col)
        pause_scr.box()
        pause_scr.addstr(2, half_cols/2 - 5, "P A U S E D", curses.color_pair(1))
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


    def draw(self, stdscr, lines, y, x):
        # Output handling. make pretty things.
        table = [[n.kind, n.chan, n.term, n.timer,
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

        # These listeners are for the AMI so I can catch events.
        client.add_event_listener(on_DialBegin, white_list = 'DialBegin')
        client.add_event_listener(on_DialEnd, white_list = 'DialEnd')

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

def module_shutdown(service_killed):
    """
    Attempts to cleanly exit panel_gen, either from __main__
    or when called from http_server.py.

    service_killed:   BOOLEAN   True if running as service
                                False if running as main
    """

    if service_killed == True:
        logging.info("--Exited due to service shutdown--")

    try:
        t.shutdown_flag.set()
        t.join()
    except Exception:
        pass
    w.shutdown_flag.set()
    w.join()

    # Hang up and clean up spool.
    system("asterisk -rx \"channel request hangup all\"")
    system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")

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

    # Parse any arguments the user gave us.
    parse_args()

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

    logging.info('Originating calls on %s', orig_switch)

    if args.t != []:
        logging.info('Terminating calls on %s', term_choices)
    if args.d == True:
        logging.info('Deterministic Mode set!')
    logging.info('Call volume set to %s', args.v)

    # Here is where we actually make the lines.
    lines = make_lines(source='main',orig_switch=orig_switch)

    # Connect to AMI
    client = AMIClient(address='127.0.0.1',port=5038)
    adapter = AMIClientAdapter(client)
    future = client.login(username='panel_gen',secret='t431434')
    if future.response.is_error():
        raise Exception(str(future.response))

    try:
        t = ui_thread()
        t.daemon = True
        t.start()
        w = work_thread()
        w.daemon = True
        w.start()

        while True:
            sleep(0.5)

    except (KeyboardInterrupt, ServiceExit):
        # Exception handler for console-based shutdown.

        logging.info("--- Caught keyboard interrupt! Shutting down gracefully. ---")
        service_killed= False
        module_shutdown(service_killed)

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
    parse_args()

    # Connect to AMI
    client = AMIClient(address='127.0.0.1',port=5038)
    adapter = AMIClientAdapter(client)
    future = client.login(username='panel_gen',secret='t431434')
    if future.response.is_error():
        raise Exception(str(future.response))

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
        # Exception handler for any exception
        logging.exception("Exception thrown in main try loop.")
        service_killed = True
        module_shutdown(service_killed)

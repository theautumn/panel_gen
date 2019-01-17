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
from marshmallow import Schema, fields
from tabulate import tabulate
from numpy import random
from pathlib import Path
from pycall import CallFile, Call, Application, Context
from asterisk.ami import AMIClient, EventListener

class Line():
# Main class for calling lines. Contains all the essential vitamins and minerals.
# It's an important part of a balanced breakfast.

    def __init__(self, ident, switch):
        self.switch = switch
        self.kind = switch.kind
        self.status = 0                                             # Set status to on-hook.

	if args.l:                                                  # If user specified a line
            self.term = args.l                                      # Set term line to user specified
        else:                                                       # Else,
            self.term = self.pick_called_line(term_choices)         # Generate a term line randomly.

        self.timer = int(random.gamma(3,4))                         # Set a start timer because i said so.
        self.ident = ident                                          # Set an integer for identity.
        self.chan = '-'                                             # Set DAHDI channel to 0 to start
        self.ast_status = 'on_hook'
        self.is_api = False                                         # Used for temporary lines from API
        self.api_indicator = ""                                     # For drawing the table in the UI

    def __repr__(self):
        return '<Line(name={self.ident!r})>'.format(self=self)

    def set_timer(self):
        self.timer = switch.newtimer
        return self.timer

    def tick(self):
        # Decrement timers by 1 every second until it reaches 0
        # At 0, we're going to check a few things. First, status. If line is on hook "0",
        # and if we haven't maxed out the senders, then call and set the status of the line to "1".
        # If we have more dialing than we have sender capacity, then we reset the timer to
        # a "reasonable number of seconds" and try again.
        # If self.status is "1", we simply call hangup(), which takes care of the cleanup.

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
                    logging.info("Exceeded sender limit: %s with %s calls dialing. Delaying call.",
			self.switch.max_dialing, self.switch.is_dialing)
            elif self.status == 1:
                self.hangup()
        return self.timer

    def pick_called_line(self, term_choices):
        # If a terminating office wasn't given at runtime, then just default to a random choice
        # as defined by the class of the switch we're calling from. Else, pick a random from the
        # args that the user gave with the -t switch.

        if term_choices == []:
            term_office = random.choice(self.switch.nxx, p=self.switch.trunk_load)
        else:
            term_office = random.choice(term_choices)

        # Choose a sane number that appears on the line link or final frame of the switches
        # that we're actually calling. If something's wrong, then assert false so it will get caught.
        # Whenever possible, these values should be defined in the switch class, and pulled from there.
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


        term = int(str(term_office) + str(term_station))        # And put it together.
        #logging.info('Terminating line selected: %s', term)
        return term

    def call(self, **kwargs):
	# Checks if we're in deterministic mode and sets duration
	# accordingly. Also checks for wait time in -d mode.
	#
        # Dialing takes ~10 to 12 seconds. We're going to set a timer
        # for call duration here, and then a few lines down,
        # we're gonna tell Asterisk to set its own wait timer to the same value - 10.
        # This should give us a reasonable buffer between the program's counter and
        # Asterisk's wait timer (which itself begins when the call goes from
        # dialing to "UP").

        if args.d:
            if args.z:
                self.timer = args.z
            else:
                self.timer = 15
        else:
            self.timer = self.switch.newtimer()

            # Wait value to pass to Asterisk dialplan if not using API to start call
            wait = self.timer - 10

            # The kwargs come in from the API. The following lines handle them and set up
            # the special call case outside of the normal program flow.
            for key, value in kwargs.items():
                if key == 'orig_switch':
                    switch = value
                if key == 'line':
                    line = value
                if key == 'timer':
                    self.timer = value
                    wait = value

            # If the line comes from the API /call/{switch}/{line} then this line is temporary.
            # This sets up special handling so that the status starts at "1", which will cause 
            # hangup() to hang up the call and delete the line when the call is done. 
            if self.is_api == True:
                self.status = 1
                self.api_indicator = "***"

            # Set the vars to actually pass to call file
            vars = {'waittime': wait}

        # Make the .call file amd throw it into the asterisk spool.
        # Pass control of the call to the sarah_callsim context in
        # the dialplan. This will allow me to better interact with
        # Asterisk from here.
        c = Call('DAHDI/' + self.switch.dahdi_group + '/wwww%s' % self.term, variables=vars)
        con = Context('sarah_callsim','s','1')
        cf = CallFile(c, con, user='asterisk')
        cf.spool()


    def hangup(self):
        # Asterisk manages the actual hangup of the call, but we need to make sure the program
        # flow is on track with whats happening out in the world. We check if a call
        # is being dialed when hangup() is called. If so, we need to decrement the dialing counter.
        # Then, set status, chan, and ast_status back to normal values, set a new timer, and
        # set the next called line.

        if self.ast_status == 'Dialing':
            logging.info('Hangup while dialing %s on DAHDI %s', self.term, self.chan)
            self.switch.is_dialing -= 1
        logging.info('Hung up %s on DAHDI/%s from %s', self.term, self.chan, self.switch.kind)
        self.status = 0                                         # Set the status of this call to 0.
        self.chan = '-'
        self.ast_status = 'on_hook'

        # Delete the line if we are just doing a one-shot call from the API.
        if self.is_api == True:
            logging.info("Deleted API one-shot line.")
            del lines[self.ident]

        if args.d:                                              # Are we in deterministic mode?
            if args.w:                                          # args.w is wait time between calls
               self.timer = args.w                              # Set length of the wait time before next call
            else:
                self.timer = 15                                 # If no args.w defined, use default value.
        else:
            self.timer = self.switch.newtimer()                 # <-- Normal call timer if args.d not specified.

        if args.l:                                              # If user specified a line
            self.term = args.l                                  # Set term line to user specified
        else:
            self.term = self.pick_called_line(term_choices)     # Pick a new terminating line.

    def update(self, api):
        # Used by the API PATCH method to update line parameters.

        for (key, value) in api.items():
            if key == 'switch':
                # Would this even work? Can you change a switch without breaking it?
                if value == 'panel':
                    self.switch = Rainier
                if value == '5xb':
                    self.switch = Adams
                if value == '1xb':
                    self.switch = Lakeivew
            if key == 'timer':
                # Change the current timer of the line.
                self.timer = value
            if key == 'dahdi_chan':
                # Change which channel a line belongs to. Also might break everything.
                self.dahdi_chan = value
            if key == 'called_no':
                self.term = value
 
# <----- END LINE CLASS -----> #

# <----- BEGIN SWITCH CLASSES ------> #

class panel():
    # This class is parameters and methods for the panel switch.
    # It should not normally need to be edited.

    def __init__(self):
        self.kind = "panel"                             # The kind of switch we're calling from.
        self.running = False
        self.max_dialing = 6
        self.is_dialing = 0
        self.dahdi_group = "r6"                         # Which DAHDI group to originate from.
        self.api_tl = ""
        self.traffic_load = self.newtimer()             # Start a new timer when switch is instantiated.

        if args.d:                                      # If deterministic mode is set,
            self.max_calls = 1                          # Set the max calls to 1, to be super basic.
        elif args.a:
            self.max_calls = args.a                     # Else, use the value given with -a
        else:
            self.max_calls = 3                          # Finally, if no args are given, use this default.

        self.max_nxx1 = .6                              # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                              # Load for office 2 in self.trunk_load
        self.max_nxx3 = .2                              # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                               # Load for office 4 in self.trunk_load
        self.nxx = [722, 365, 232]                      # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1,
            self.max_nxx2, self.max_nxx3]
        self.line_range = [5000,5999]                   # Range of lines that can be chosen.

    def __repr__(self):
        return("{}('{}')".format(self.__class__.__name__, self.running))

    def newtimer(self):
        # First checks to see if args.v is specified.
        # If we're running as module, ignore args, and use API value.

        if __name__ == '__main__':
            if args.v == 'light':
                traffic = int(round(random.gamma(20,8)))
            elif args.v == 'heavy':
                traffic = int(round(random.gamma(5,7)))
            elif args.v == 'normal':
                traffic = int(round(random.gamma(4,14)))

        if __name__ == 'panel_gen':
            if self.api_tl == 'heavy':
                traffic = int(round(random.gamma(5,7)))
            elif self.api_tl == 'light':
                traffic = int(round(random.gamma(20,8)))
            else:
                traffic = int(round(random.gamma(4,14)))

        return traffic

    def update(self, api):
        # Used by the API PATCH method to update switch parameters.

        for (key, value) in api["switch"].items():
            if key == 'line_range':
                # Line range must be a tuple from 1000-9999
                self.line_range = value
            if key == 'nxx':
                # nxx must be 3 digits, matching codes we can dial
		# number of values in nxx must also match trunk_load
                for i in value:
                    self.nxx = value
            if key == 'running':
		# Can be used to start and stop a particular switch.
		# This feature is not yet implemented fully.
                self.running = value
            if key == 'max_dialing':
		# Must be <= 10
                if value >=10:
                    return "Fail: bad_max"
                else:
                    self.max_dialing = value
            if key == 'max_calls':
		# Must be <= 10
                if value >= 10:
                    return "Fail: must be less than 10 max dialing"
                else:
                    self.max_calls = value
            if key == 'dahdi_group':
		# Must be a group that we have hooked in to panel_gen
                self.dahdi_group = value
            if key == 'trunk_load':
		# Total of all values must add up to 1
		# Number of values must equal number of NXXs
                self.trunk_load = value
            if key == 'traffic_load':
                self.api_tl = value

class xb1():
    # This class is for the No. 1 Crossbar.
    # For a description of each of these lines, see the panel class above.

    def __init__(self):
        self.kind = "1xb"
        self.running = False
        self.max_dialing = 2
        self.is_dialing = 0
        self.dahdi_group = "r11"
        self.traffic_load = self.newtimer()

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
        self.line_range = [105,107,108,109,110,111,112,113,114]

    def __repr__(self):
        return("{}('{}')".format(self.__class__.__name__, self.running))

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))                  # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(5,9)))                   # Heavy Traffic
        else:
            t = int(round(random.gamma(5,10)))                  # Medium Traffic
        return t

    def update(self, api):
        # Used by the API PATCH method to update switch parameters.

        for (key, value) in api["switch"].items():
            if key == 'line_range':
                # Line range must be a tuple from 1000-9999
                self.line_range = value
            if key == 'nxx':
                # nxx must be 3 digits, matching codes we can dial
		# number of values in nxx must also match trunk_load
                for i in value:
                    self.nxx = value
            if key == 'running':
		# Can be used to start and stop a particular switch.
		# This feature is not yet implemented fully.
                self.running = value
            if key == 'max_dialing':
		# Must be <= 10
                if value >=10:
                    return "Fail: bad_max"
                else:
                    self.max_dialing = value
            if key == 'max_calls':
		# Must be <= 10
                if value >= 10:
                    return "Fail: must be less than 10 max dialing"
                else:
                    self.max_calls = value
            if key == 'dahdi_group':
		# Must be a group that we have hooked in to panel_gen
                self.dahdi_group = value
            if key == 'trunk_load':
		# Total of all values must add up to 1
		# Number of values must equal number of NXXs
                self.trunk_load = value
            if key == 'traffic_load':
                self.api_tl = value

class xb5():
    # This class is for the No. 5 Crossbar.
    # For a description of these line, see the panel class, above.

    def __init__(self):
        self.kind = "5xb"
        self.running = False
        self.max_dialing = 7
        self.is_dialing = 0
        self.dahdi_group = "r5"
        self.traffic_load = self.newtimer()

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
        self.line_range = [1330,1009,1904,1435,9072,9073,1274,1485,1020,5678,5852,
                        1003,6766,6564,1076,1026,5018,1137,9138,1165,1309,1440,9485,
                        9522,9361,1603,1704,9929,1939,1546,1800,5118,9552,4057,1055,
                        1035,1126,9267,1381,1470,9512,1663,9743,1841,1921]

    def __repr__(self):
        return("{}('{}')".format(self.__class__.__name__, self.running))

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))                  # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(4,5)))            # 4,6  # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))                  # Medium Traffic
        return t

    def update(self, api):
        # Used by the API PATCH method to update switch parameters.

        for (key, value) in api["switch"].items():
            if key == 'line_range':
                # Line range must be a tuple from 1000-9999
                self.line_range = value
            if key == 'nxx':
                # nxx must be 3 digits, matching codes we can dial
		# number of values in nxx must also match trunk_load
                for i in value:
                    self.nxx = value
            if key == 'running':
		# Can be used to start and stop a particular switch.
		# This feature is not yet implemented fully.
                self.running = value
            if key == 'max_dialing':
		# Must be <= 10
                if value >=10:
                    return "Fail: bad_max"
                else:
                    self.max_dialing = value
            if key == 'max_calls':
		# Must be <= 10
                if value >= 10:
                    return "Fail: must be less than 10 max dialing"
                else:
                    self.max_calls = value
            if key == 'dahdi_group':
		# Must be a group that we have hooked in to panel_gen
                self.dahdi_group = value
            if key == 'trunk_load':
		# Total of all values must add up to 1
		# Number of values must equal number of NXXs
                self.trunk_load = value
            if key == 'traffic_load':
                self.api_tl = value

class step():
    # This class is for the SxS office. It's very minimal, as we are not currently
    # originating calls from there, only completing them from the 5XB.

    def __init__(self):
        self.kind = "Step"
        self.line_range = [4124,4129]


# +-----------------------------------------------+
# |                                               |
# | # <----- BEGIN BOOKKEEPING STUFF -----> #     |
# |   This is uncategorized bookkeeping for       |
# |   the rest of the program. Includes           |
# |   getting AMI events, and parsing args.       |
# |                                               |
# +-----------------------------------------------+

def on_DialBegin(event, **kwargs):
    # This parses DialBegin notifications from the AMI.
    # It uses regex to extract the DialString and DestChannel, then associates the
    # dialed number with its DAHDI channel. This is then displayed for the user.
    # Also increments the is_dialing counter.

    # The regex match for DialString relies on the dialplan having at least
    # one 'w' (wait) in it to wait before dialing. If you change that, the
    # regex will break. Normally, we should always wait before dialing.

    output = str(event)
    DialString = re.compile('(?<=w)(\d{7})')
    DB_DestChannel = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')

    DialString = DialString.findall(output)
    DB_DestChannel = DB_DestChannel.findall(output)
    #logging.info('%s', DialString)
    #logging.info('%s', DestChannel)

    for n in lines:
        if DialString[0] == str(n.term) and n.ast_status == 'on_hook':
            # logging.info('DialString match %s and %s', DialString[0], str(n.term))
            n.chan = DB_DestChannel[0]
            n.ast_status = 'Dialing'
            n.switch.is_dialing += 1
            logging.info('Calling %s on DAHDI/%s from %s', n.term, n.chan, n.switch.kind)

def on_DialEnd(event, **kwargs):
    # Same thing as above, except catches DialEnd and sets the state of the call
    # to "Ringing", and decrements the is_dialing counter.

    output = str(event)
    DE_DestChannel = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')
    DE_DestChannel = DE_DestChannel.findall(output)

    for n in lines:
        if DE_DestChannel[0] == str(n.chan) and n.ast_status == 'Dialing':
            n.ast_status = 'Ringing'
            n.switch.is_dialing -= 1
            # logging.info('on_DialEnd with %s calls dialing', n.switch.is_dialing)

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
    parser.add_argument('--http', action='store_true',
            help='Run in headless HTTP server mode for remote control.')

    global args
    args = parser.parse_args()
    make_switch(args)

def make_switch(args):
    # Instantiate some switches. This is so we can ask to get their parameters later.

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
        if args.o == []:                # If no args provided, just assume panel switch.
            args.o = ['panel']

        for o in args.o:
            if o == 'panel' or o == '722':
                orig_switch.append(Rainier)
            elif o == '5xb' or o == '232':
                orig_switch.append(Adams)
            elif o == '1xb' or o == '832':
                orig_switch.append(Lakeview)
            elif o == 'all':
                orig_switch.extend((Lakeview, Adams, Rainier))

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


# +----------------------------------------------------+
# |                                                    |
# | The following chunk of code is for the             |
# | panel_gen API, currently run from http_server.py   |
# | The http server starts Flask, Connexion, which     |
# | reads the API from swagger.yml, and executes HTTP  |
# | requests using the code in switch.py and line.py   |
# |                                                    |
# | These functions return values to those two .py's   |
# | when panel_gen is imported as a module.            |
# |                                                    |
# +----------------------------------------------------+

class AppSchema(Schema):
    name = fields.Str()
    app_running = fields.Boolean()
    is_paused = fields.Boolean()
    ui_running = fields.Boolean()
    paused = fields.Boolean()
    num_lines = fields.Integer()

class LineSchema(Schema):
    line = fields.Dict()
    ident = fields.Integer()
    switch = fields.Str()
    timer = fields.Integer()
    is_dialing = fields.Boolean()
    ast_status = fields.Str()
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
    traffic_load = fields.Str()
    api_tl = fields.Str()

class CallSchema(Schema):
    orig_switch = fields.Str()
    called_no = fields.Str()
    timer = fields.Integer()

def get_info():
    # API can get general info about running state.
    schema = AppSchema()
    result = dict([
        ('name', __name__),
        ('app_running', w.is_alive),
        ('is_paused', w.paused),
        ('ui_running', t.started),
        ('num_lines', len(lines))
        ])
    return schema.dump(result)

def operate(switch):
    # Should do the opposite of start(). 
    # Should read in switch to start on, and
    # create lines from a DB using preset defaults
    # similar to how things work if you start via
    # the command line. Currently THIS DOES NOT WORK.

    logging.info("API requested start on %s", switch)
    if w.is_alive != True:
        w.start()
    if w.is_alive == True:

        global lines
        if switch == 'panel':
            switch = Rainier
        if switch == '5xb':
            switch = Adams
        if switch == '1xb':
            switch = Lakeview

        if switch.running == True:
            logging.info("%s is running. Can't start twice.", switch)
        elif switch.running == False:
            logging.info("Appending lines to %s", switch)
            new_lines = [Line(n, switch) for n in range(switch.max_calls)]
            for n in new_lines:
                lines.append(n)
            switch.running = True

    result = get_info()
    return result
    
def stop(*args):
    # This should pause execution and immediately hang up all calls, just
    # as though we were exiting the program. Of course, we can't actually
    # exit, as this function is only called if we're running as a module,
    # and a module can not just exit. 


    try:
        # First, delete all the lines.
        delete_all_lines()

        # Set all switches to False
        for n in orig_switch:
            n.running = False

        # Hang up and clean up spool.
        system("asterisk -rx \"channel request hangup all\" > /dev/null 2>&1")
        system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")
    except Exception as e:
        logging.info(e)
        return False

    return True
    
def api_pause():
    # All of these functions should probably return something meaningful.
    # They're mostly just placeholders for now.
    # WE CAN ONLY SEND THIS ONCE, OTHERWISE EVERYTHING WILL BLOCK. FIX ME PLEASE!

    if w.paused == False:
        if t.started == True:
            t.draw_paused()
        elif t.started ==False:
            w.pause()
            return " PAUSED: UI thread not running"
    elif w.paused == True:
        return "Already paused"

def api_resume():
    # This works, but only sort of. Need to fix!
    if w.paused == True:
        if t.started == True:
            t.draw_resumed()
        elif t.started == False:
            w.resume()
            return "UI Thread not running"
    else:
        return "Already running"

def call_now(switch, term_line):
    # This is called when a POST is sent to /api/{switch}/{line}
    # and immediately places a call from SWITCH to LINE. The line
    # is deleted when the call is done.

    schema = LineSchema()

    # Validates switch input.
    if switch == 'panel':
        switch = Rainier
    elif switch == '5xb':
        switch = Adams
    elif switch == '1xb':
        switch = Lakeview
    else:
        return False
    
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
    # From API. Gets all active lines.

    schema = LineSchema()
    result = []
    for n in lines:
        result.append(schema.dump(n))
    return result

def get_line(ident):
    # Check if ident passed in via API exists in lines.
    # If so, send back that line. Else, return False..

    api_ident = int(ident)
    schema = LineSchema()
    result = []
    for n in lines:
        if api_ident == n.ident:
            result.append(schema.dump(lines[api_ident]))

    if result == []:
        return False
    else:
        return result

def create_line(switch):
    # Creates a new line using default parameters.
    # lines.append uses the current number of lines in list
    # to create the ident value for the new line.

    # Should eventually accept optional parameters.

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
    # Deletes all lines immediately.

    logging.info("API requested delete all lines.")
    while len(lines) > 0:
        del lines[0]
    if len(lines) == 0:
        return True
    else:
        return False

def delete_line(ident):
    # Deletes a specific line passed in via ident.

    api_ident = int(ident)
    result = []
    for n in lines:
        if api_ident == n.ident:
            logging.info("API requested delete line %s", n.ident)
            del lines[n.ident]
            result.append(api_ident)
    if result == []:
        return False
    else:
        return result

def update_line(**kwargs):
    schema = LineSchema()

    api_ident = kwargs.get("ident", "")
    # Pull the line ident out of the dict the API passed in.
    for i, o in enumerate(lines):
        if o.ident == int(api_ident):
           parameters = kwargs['line']
           result = schema.load(parameters)
           outcome = o.update(result)
           return schema.dump(o)

def get_all_switches():
    # Return all switches that exist in orig_switch. Sort of
    # broken because I don't use orig_switch properly.

    schema = SwitchSchema()
    result = []
    for n in orig_switch:
        result.append(schema.dump(n))
    return result

def get_switch(kind):
    # Gets the parameters for a particular switch object.

    schema = SwitchSchema()
    result = []
    for n in orig_switch:
        if kind == n.kind:
            if n.kind == 'panel':
                result.append(schema.dump(Rainier))
            if n.kind == '5xb':
                result.append(schema.dump(Adams))
            if n.kind == '1xb':
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
    outcome = switch.update(result)

    # >>> !! Should return the switch, or a specific error that the user can act upon.
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
        # h: Help
        if key == ord('h'):
            self.helpscreen(stdscr)
            key = stdscr.getch()
            if key:
                self.stdscr.nodelay(1)
                self.stdscr.erase()
                self.stdscr.refresh()
        # u: add a line to the first switch.
        if key == ord('u'):
            lines.append(Line(7, orig_switch[0]))
        # d: delete the 0th line.
        if key == ord('d'):
            if len(lines) <=1:
                logging.info("Tried to delete last remaining line. No.")
            elif len(lines) > 1:
                del lines[0]

    def update_size(self, stdscr, y, x):
        # This gets called if the screen is resized. Makes it happy so exceptions don't get thrown.

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

    def helpscreen(self):
        # Draw the help screen when 'h' is pressed. Then, control goes back to
        # getkey(), which waits for any key, and goes back to drawing the UI.

        y, x = stdscr.getmaxyx()
        half_cols = x/2
        rows_size = 20
        x_start_row = y - 40
        y_start_col = half_cols - half_cols / 2
        w
        stdscr.nodelay(0)
        stdscr.clear()
        help_scr = stdscr.subwin(rows_size, half_cols, x_start_row, y_start_col)
        help_scr.box()
        help_scr.bkgd(' ', curses.color_pair(1))
        help_scr.addstr(2, half_cols/2 - 5, "HJAELP!", curses.color_pair(1))
        help_scr.addstr(4, 5, "Spacebar         Run/Pause")
        help_scr.addstr(5, 5, "u/d              Add/Remove Lines")
        help_scr.addstr(6, 5, "h                Help")
        help_scr.addstr(7, 5, "Ctrl + C         Quit")


    def draw(self, stdscr, lines, y, x):
        # Output handling. make pretty things.
        table = [[n.kind, n.chan, n.term, n.timer, n.status, n.ast_status, n.api_indicator] for n in lines]
        stdscr.erase()
        stdscr.addstr(0,5," __________________________________________")
        stdscr.addstr(1,5,"|                                          |")
        stdscr.addstr(2,5,"|  Rainier Full Mechanical Call Simulator  |")
        stdscr.addstr(3,5,"|__________________________________________|")
        stdscr.addstr(6,0,tabulate(table, headers=["switch", "channel", "term", "tick", "state", "asterisk", "api"],
        tablefmt="pipe", stralign = "right" ))

        # Print asterisk channels below the table so we can see what its actually doing.
        if not args.http == True:
            if y > 35:
                ast_out = subprocess.check_output(['asterisk', '-rx', 'core show channels'])
                stdscr.addstr(20,5,"============ Asterisk output ===========")
                stdscr.addstr(22,0,ast_out)

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
    # help with drawing. Note: This thread does not start if
    # panel_gen is run with the --http option. No UI necessary
    # in headless mode.

    def __init__(self):

        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()
        self.started = True

    def run(self):
        try:
            curses.wrapper(self.ui_main)
        except Exception as e:
            logging.info(e)

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

    def draw_paused(self):
        screen.pausescreen()

    def draw_resumed(self):
        screen.resumescreen()

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
                for n in lines:
                    n.tick()
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

class WebShutdown(Exception):
    pass

def app_shutdown(signum, frame):
    raise ServiceExit

def web_shutdown(signum, frame):
    raise WebShutdown


if __name__ == "__main__":
    # Init a bunch of things if we're running as a standalone app.

    # Set up signal handlers so we can shutdown cleanly later.
    signal.signal(signal.SIGTERM, app_shutdown)
    signal.signal(signal.SIGINT, app_shutdown)
    signal.signal(signal.SIGALRM, web_shutdown)

    paused = None

    # Parse any arguments the user gave us.
    parse_args()

    # If logfile does not exist, create it so logging can write to it.
    try:
        with open('/var/log/panel_gen/calls.log', 'a') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')
    except IOError:
        with open('/var/log/panel_gen/calls.log', 'w') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')

    logging.info('Originating calls on %s', args.o)
    if args.t != []:
        logging.info('Terminating calls on %s', term_choices)
    if args.d == True:
        logging.info('Deterministic Mode set!')
    logging.info('Call volume set to %s', args.v)

    # Here is where we actually make the lines.
    global lines
    lines = [Line(n, switch) for switch in orig_switch for n in range(switch.max_calls)]

    # Connect to AMI
    client = AMIClient(address='127.0.0.1',port=5038)
    future = client.login(username='panel_gen',secret='t431434')
    if future.response.is_error():
        raise Exception(str(future.response))

    try:
        if not args.http:
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

        t.shutdown_flag.set()
        t.join()
        w.shutdown_flag.set()
        w.join()

        logging.info("--- Caught keyboard interrupt! Shutting down gracefully. ---")

        # Hang up and clean up spool.
        system("asterisk -rx \"channel request hangup all\"")
        system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")

        # Log out of AMI
        client.logoff()

        print("\n\nShutdown requested. Hanging up Asterisk channels, and cleaning up /var/spool/")
        print("Thank you for playing Wing Commander!\n\n")

    except WebShutdown:
        # Exception handler for http-server shutdown. The http-server
        # passes SIGALRM, which calls web_shutdown and eventually
        # leads us here.

        w.shutdown_flag.set()
        w.join()

        logging.info("Exited due to web interface shutdown")

        # Hang up and clean up spool.
        system("asterisk -rx \"channel request hangup all\"")
        system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")

        # Log out of AMI
        client.logoff()

        print("panel_gen web shutdown complete.\n")

    except Exception as e:
        # Exception for any other errors that I'm not explicitly handling.

	t.shutdown_flag.set()
	t.join()
        w.shutdown_flag.set()
        w.join()

        print("\nOS error {0}".format(e))
        logging.info('**** OS Error ****')
        logging.info('{0}'.format(e))

if __name__ == "panel_gen":
    # The below gets run if this code is imported as a module.
    # It skips lots of setup steps.
    parse_args()

    # Connect to AMI
    client = AMIClient(address='127.0.0.1',port=5038)
    future = client.login(username='panel_gen',secret='t431434')
    if future.response.is_error():
        raise Exception(str(future.response))

    # If logfile does not exist, create it so logging can write to it.
    try:
        with open('/var/log/panel_gen/calls.log', 'a') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')
    except IOError:
        with open('/var/log/panel_gen/calls.log', 'w') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')

#    lines = [Line(n, switch) for switch in orig_switch for n in range(switch.max_calls)]
    lines = []
    logging.info('Starting panel_gen as thread from http_server')

    try:
        w = work_thread()
        w.daemon = True
        w.start()
        t = ui_thread()
        t.daemon = True
        t.start()

        sleep(.5)

    except Exception:
        # Exception handler for any exception

        t.shutdown_flag.set()
        t.join()
        w.shutdown_flag.set()
        w.join()

        logging.info("--- Caught keyboard interrupt! Shutting down gracefully. ---")

        # Hang up and clean up spool.
        system("asterisk -rx \"channel request hangup all\"")
        system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")

        # Log out of AMI
        client.logoff()

        print("\n\nShutdown requested. Hanging up Asterisk channels, and cleaning up /var/spool/")
        print("Thank you for playing Wing Commander!\n\n")


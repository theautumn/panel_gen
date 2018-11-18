#---------------------------------------------------------------------#
#                                                                     #
#  A call generator thing for the Rainier Panel switch at the         #
#  Connections Museum, Seattle WA.                                    #
#                                                                     #
#  Written by Sarah Autumn, 2017-2018                                 #
#  sarah@connectionsmuseum.org                                        #
#  github.com/theautumn/panel_gen                                     #
#                                                                     #
#---------------------------------------------------------------------#

import time
import os
import sys
import subprocess
import argparse
import logging
import curses
import re
from tabulate import tabulate
from numpy import random
from pathlib import Path
from pycall import CallFile, Call, Application, Context
from asterisk.ami import AMIClient
from asterisk.ami import EventListener

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
            self.term = self.PickCalledLine(term_choices)           # Generate a term line randomly.

        self.timer = int(round(random.gamma(4,4)))                  # Set a start timer because i said so.
        self.ident = ident                                          # Set an integer for identity.
        self.chan = '-'                                             # Set DAHDI channel to 0 to start
        self.AstStatus = 'on_hook'

    def set_timer(self):
        self.timer = switch.newtimer
        return self.timer

    def tick(self):
        # Decrement timers by 1 every second until it reaches 0
        # At 0, we're going to check a few things. First, status. If line is on hook "0",
        # and if we haven't maxed out the senders, then call and set the status of the line to "1".
        # If we have more dialing than we have sender capacity, then we reset the timer to
        # a reasonable number of seconds and try again. 
        # If self.status is "1", we simply call hangup(), which takes care of all the cleanup.

        self.timer -= 1
        if self.timer <= 0:
            if self.status == 0:
                if self.switch.is_dialing < self.switch.max_dialing:
                    self.Call()
                    self.status = 1
                else:
                    self.timer = int(round(random.gamma(5,5)))
                    logging.info("Exceeded sender limit: %s with %s calls dialing. Delaying call.", self.switch.max_dialing, self.switch.is_dialing)
            elif self.status == 1:
                self.hangup()
        return self.timer

    def PickCalledLine(self, term_choices):
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
            term_station = random.randint(Rainier.linerange[0], Rainier.linerange[1])
        elif term_office == 832:
            term_station = "%04d" % random.randint(Lakeview.linerange[0],Lakeview.linerange[1])
        elif term_office == 232:
             term_station = random.randint(Adams.linerange[0], Adams.linerange[1])
        elif term_office == 275:
            term_station = random.randint(Step.linerange[0], Step.linerange[1])
        else:
            logging.error("No terminating line available for this office. Did you forget to add it to PickCalledLine?")
            assert False


        term = int(str(term_office) + str(term_station))        # And put it together.
        #logging.info('Terminating line selected: %s', term)
        return term

    def Call(self):
        # Dialing takes ~10 to 12 seconds. This should be somewhat consistent value
        # because its done by Asterisk / DAHDI. We're going to set a timer
        # for call duration here, and then a few lines down,
        # we're gonna tell Asterisk to set its own wait timer to the same value - 10.
        # This should give us a reasonable buffer between the program's counter and
        # Asterisk's wait timer (which itself begins when the call goes from
        # dialing to "UP").

        if args.d:                                              # Are we in deterministic mode?
            if args.z:                                          # args.z is call duration
                self.timer = args.z                             # Set length of call to what user specified
            else:
                self.timer = 15                                 # If no args.z, use default value for -d mode.
        else:                                                   # If we are in normal mode, then it's easy
            self.timer = self.switch.newtimer()                 # Reset the timer for the next go-around.

        wait = str(self.timer - 10)                             # Wait value to pass to Asterisk dialplan
        vars = {'waittime': wait}                               # Set the vars to actually pass over

        # Make the .call file amd throw it into the asterisk spool.
        # New behavior 8-15-18 is to pass control of the call to the sarah_callsim context in
        # the dialplan. Hopefully, this will allow me to better interact with Asterisk from here.
        c = Call('DAHDI/' + self.switch.dahdi_group + '/wwww%s' % self.term, variables=vars)
        con = Context('sarah_callsim','s','1')
        cf = CallFile(c, con, user='asterisk')
        cf.spool()


    def hangup(self):
        # Asterisk manages the actual hangup of the call, but we need to make sure the program
        # flow is on track with whats happening out in the world. We check if a call
        # is being dialed when hangup() is called. If so, we need to decrement the dialing counter.
        # Then, set status, chan, and AstStatus back to normal values, set a new timer, and
        # set the next called line.

        if self.AstStatus == 'Dialing':
            logging.info('Hangup while dialing %s on DAHDI %s', self.term, self.chan)
            self.switch.is_dialing -= 1
        logging.info('Hung up %s on DAHDI/%s from %s', self.term, self.chan, self.switch.kind)
        self.status = 0                                         # Set the status of this call to 0.
        self.chan = '-'
        self.AstStatus = 'on_hook'

        if args.d:                                              # Are we in deterministic mode?
            if args.w:                                          # args.w is wait time between calls
               self.timer = args.w                              # Set length of the wait time before next call
            else:
                self.timer = 15                                 # If no args.w defined, use default value.
        else:
            self.timer = self.switch.newtimer()                 # <-- Normal call timer if args.d not specified.

        if args.l:                                              # If user specified a line
            self.term = args.l                                  # Set term line to user specified
        else:                                                   # Else,
            self.term = self.PickCalledLine(term_choices)       # Pick a new terminating line.


# <----- END LINE CLASS THINGS -----> #

# <----- BEGIN SWITCH CLASSES ------> #

class panel():
# This class is parameters and methods for the panel switch.  It should not normally need to be edited.
# If you wish to change the office codes, or trunk weight, this is where you do it.

    def __init__(self):
        self.kind = "panel"                                     # The kind of switch we're calling from.
        self.max_dialing = 5                                    # Sender E is out of order, so max is 5.
        self.is_dialing = 0
        self.dahdi_group = "r6"                                 # Which DAHDI group to originate from.
        self.dcurve = self.newtimer()                           # Start a new timer when switch is instantiated.

        if args.d:                                              # If deterministic mode is set,
            self.max_calls = 1                                  # Set the max calls to 1, to be super basic.
        elif args.a:
            self.max_calls = args.a                             # Else, use the value given with -a
        else:
            self.max_calls = 3                                  # Finally, if no args are given, use this default.

        self.max_nxx1 = .6                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .2                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                       # Load for office 4 in self.trunk_load
        self.nxx = [722, 365, 232]                              # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]
        self.linerange = [5000,5999]                            # Range of lines that can be chosen.

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))                  # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(5,7)))                   # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))                  # Medium Traffic
        return t

class xb1():
# This class is for the No. 1 Crossbar. Same as panel, above, but with different parameters.
# For a description of each of these lines, see the panel class above.

    def __init__(self):
        self.kind = "1xb"
        self.max_dialing = 2
        self.is_dialing = 0
        self.dahdi_group = "r11"
        self.dcurve = self.newtimer()

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
        self.linerange = [105, 149]

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))                  # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(5,9)))                   # Heavy Traffic
        else:
            t = int(round(random.gamma(5,10)))                  # Medium Traffic
        return t


class xb5():
# This class is for the No. 5 Crossbar. Same as panel, above, but with different parameters.
# For a description of these, see the panel class, up there ^

    def __init__(self):
        self.kind = "5XB"
        self.max_dialing = 7
        self.is_dialing = 0
        self.dahdi_group = "r5"
        self.dcurve = self.newtimer()

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
        self.linerange = [5000,5999]

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))                  # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(4,5)))            # 4,6  # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))                  # Medium Traffic
        return t

class step():
# This class is for the SxS office. It's very minimal right now, as we are not currently
# originating calls from there, only completing them from the 5XB.

    def __init__(self):
        self.kind = "Step"
        self.linerange = [4124,4199]


# <----- BEGIN BOOKKEEPING STUFF -----> #

def on_DialBegin(event, **kwargs):
# This parses notifications received from Asterisk AMI, particularly DialBegin.
# It uses regex to extract the DialString and DestChannel, then associates the
# dialed number with its DAHDI channel. This is then displayed for the user.
# Also increments the is_dialing counter.

# The regex match for DialString relies on the dialplan having at least
# one 'w' (wait) in it to wait before dialing. If you change that, the 
# regex will break. Normally, we should always wait before dialing.

    # logging.info('Reached DialBegin')
    output = str(event)
    DialString = re.compile('(?<=w)(\d{7})')
    DB_DestChannel = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')

    DialString = DialString.findall(output)
    DB_DestChannel = DB_DestChannel.findall(output)
    #logging.info('%s', DialString)
    #logging.info('%s', DestChannel)

    for n in line:
        if DialString[0] == str(n.term) and n.AstStatus == 'on_hook':
            # logging.info('DialString match %s and %s', DialString[0], str(n.term))
            n.chan = DB_DestChannel[0]
            n.AstStatus = 'Dialing'
            n.switch.is_dialing += 1
            logging.info('Calling %s on DAHDI/%s from %s', n.term, n.chan, n.switch.kind)

def on_DialEnd(event, **kwargs):
# Same thing as above, except catches DialEnd and sets the state of the call
# to "Ringing", and decrements the is_dialing counter.

    # logging.info('Begin DialEnd')
    output = str(event)
    DE_DestChannel = re.compile('(?<=DestChannel\'\:\su.{7})([^-]*)')

    DE_DestChannel = DE_DestChannel.findall(output)

    for n in line:
        if DE_DestChannel[0] == str(n.chan) and n.AstStatus == 'Dialing':
            n.AstStatus = 'Ringing'
            n.switch.is_dialing -= 1
            # logging.info('on_DialEnd with %s calls dialing', n.switch.is_dialing)

def parse_args():
# Stuff for command line arguments, so we can configure some options at runtime.
# If no arguments are presented, the program will run with default
# mostly sane options.

    parser = argparse.ArgumentParser(description='Generate calls to electromechanical switches. Defaults to originate a sane amount of calls from the panel switch if no args are given.')
    parser.add_argument('-a', metavar='lines', type=int, choices=[1,2,3,4,5,6,7,8,9,10],
            help='Maximum number of active lines.')
    parser.add_argument('-d', action='store_true',
            help='Deterministic mode. Eliminate timing randomness. Places one call at a time. Ignores -a and -v options entirely. Use with -l.')
    parser.add_argument('-l', metavar='line', type=int, 
            help='Call only a particular line. Can be used with the -d option for placing test calls to a number over and over again.')
    parser.add_argument('-o', metavar='switch', type=str, nargs='?', action='append', default=[],
            choices=['1xb','5xb','panel','all','722', '832', '232'],
            help='Originate calls from a particular switch. Takes either 3 digit NXX values or switch name.  1xb, 5xb, panel, or all. Default is panel.')
    parser.add_argument('-t', metavar='switch', type=str, nargs='?', action='append', default=[],
            choices=['1xb','5xb','panel','office','step', '722', '832', '232', '365', '275'],
            help='Terminate calls only on a particular switch. Takes either 3 digit NXX values or switch name. Defaults to sane options for whichever switch you are originating from.')
    parser.add_argument('-v', metavar='volume', type=str, default='normal',
            help='Call volume is a proprietary blend of frequency and randomness. Can be light, normal, or heavy. Default is normal, which is good for average load.')
    parser.add_argument('-w', metavar='seconds', type=int, help='Use with -d option to specify wait time between calls.')
    parser.add_argument('-z', metavar='seconds', type=int,
            help='Use with -d option to specify call duration.')
    parser.add_argument('-log', metavar='loglevel', type=str, default='INFO',
            help='Set log level to WARNING, INFO, DEBUG.')

    args = parser.parse_args()
    return args


class Screen():
# This puts all the screen handling junk in its own class, so I can just poke it at will.

    def __init__(self, stdscr):
        # For some reason when we init curses using wrapper(), we have to tell it
        # to use terminal default colors, otherwise the display gets wonky.
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
        y, x = stdscr.getmaxyx()
        stdscr.nodelay(1)

    def getkey(self, stdscr):
    # Wait for a <spacebar>. When found, pause the thing, draw a "paused" box, and wait for another <spacebar>.
        key = stdscr.getch()
        if key == ord(' '):
            self.pausedwin(stdscr)
            key = stdscr.getch()
            if key == ord(' '):
                stdscr.nodelay(1)
                stdscr.erase()

    def is_resized(stdscr, y, x):
    # This gets called if the screen is resized. Makes it happy so exceptions don't get thrown.
        stdscr.clear()
        curses.resizeterm(y, x)
        stdscr.refresh()

    def pausedwin(self, stdscr):
    # Draw the PAUSED notification when execution is paused.
        y, x = stdscr.getmaxyx()
        half_cols = x/2
        rows_size = 5
        x_start_row = y - 9
        y_start_col = half_cols - half_cols / 2

        stdscr.nodelay(0)
        pause_scr = stdscr.subwin(rows_size, half_cols, x_start_row, y_start_col)
        pause_scr.box()
        pause_scr.addstr(2, half_cols/2 - 5, "P A U S E D", curses.color_pair(1))
        pause_scr.bkgd(' ', curses.color_pair(2))
        stdscr.addstr(y-1,0,"Spacebar: pause/resume, ctrl + c: quit", curses.A_BOLD)
        pause_scr.refresh()


def start(stdscr):
# Before we do anything else, the program needs to know which switch it will be originating calls from.
# Can be any of switch class: panel, xb5, xb1, all

    global orig_switch
    orig_switch = []

    if args.o == []:                                    # If no args provided, just assume panel switch.
        args.o = ['panel']

    for o in args.o:
        if o == 'panel' or o == '722':
            orig_switch.append(panel())
        elif o == '5xb' or o == '232':
            orig_switch.append(xb5())
        elif o == '1xb' or o == '832':
            orig_switch.append(xb1())
        elif o == 'all':
            orig_switch.extend((xb1(), xb5(), panel()))

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

    logging.info('Originating calls on %s', args.o)
    if args.t != []:
        logging.info('Terminating calls on %s', term_choices)
    if args.d == True:
        logging.info('Deterministic Mode set!')
    logging.info('Call volume set to %s', args.v)


    # If we got this far, log that we started successfully.
    logging.info('--- Started panel_gen ---')

    # Instantiate a screen, so we can play with it later.
    screen = Screen(stdscr)

    # These listeners are for the AMI so I can catch events. Probably should go somewhere else, but whatev.
    client.add_event_listener(on_DialBegin, white_list = 'DialBegin')
    client.add_event_listener(on_DialEnd, white_list = 'DialEnd')

    # Here is where we actually make the lines. Important stuff!
    global line
    line = [Line(n, switch) for switch in orig_switch for n in range(switch.max_calls)]

    # The main loop that kicks everything into gear. 
    while True:

        # Handle keyboard pause and resume. If pause, then set nodelay to 0, 
        # which pauses execution (thanks, curses!)
        screen.getkey(stdscr)

        # Check if screen has been resized. Handle it.
        y, x = stdscr.getmaxyx()
        resized = curses.is_term_resized(y, x)
        if resized is True:
            y, x = stdscr.getmaxyx()
            is_resized(stdscr, y, x)

        # Tick the clock
        for n in line:
            n.tick()

        # Output handling. make pretty things, sleep 1, repeat ... 
        table = [[n.kind, n.chan, n.term, n.timer, n.status, n.AstStatus] for n in line]
        stdscr.erase()
        stdscr.addstr(0,5," __________________________________________") 
        stdscr.addstr(1,5,"|                                          |")
        stdscr.addstr(2,5,"|  Rainier Full Mechanical Call Simulator  |")
        stdscr.addstr(3,5,"|__________________________________________|")
        stdscr.addstr(6,0,tabulate(table, headers=["switch", "channel", "term", "tick", "state", "asterisk"],
        tablefmt="pipe", stralign = "right" )) 

        # Print asterisk channels below the table so we can see what its actually doing.
        if y > 30:
            ast_out = subprocess.check_output(['asterisk', '-rx', 'core show channels'])
            stdscr.addstr(20,5,"============ Asterisk output ===========")
            stdscr.addstr(22,0,ast_out)

        # Print the contents of /var/log/panel_gen/calls.log
        if y > 45:
            logs = subprocess.check_output(['tail', '/var/log/panel_gen/calls.log'])
            stdscr.addstr(32,5,'================= Logs =================')
            stdscr.addstr(34,0,logs)

        stdscr.addstr(y-1,0,"Spacebar: pause/resume, ctrl + c: quit", curses.A_BOLD)

        # Refresh the screen.
        stdscr.refresh()

        # Take a nap.
        time.sleep(1)

if __name__ == "__main__":
# Init a bunch of things. Program stars here, and then calls curses.wrapper() which
# sets up ncurses and calls start() which is where the main loop lives.

    global args
    args = parse_args()

    # If logfile does not exist, create it so logging can write to it.
    try:
        with open('/var/log/panel_gen/calls.log', 'a') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', 
            filename='/var/log/panel_gen/calls.log',level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')
    except IOError:
        with open('/var/log/panel_gen/calls.log', 'w') as file:
            logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
            filename='/var/log/panel_gen/calls.log',level=logging.INFO, datefmt='%m/%d/%Y %I:%M:%S %p')

    # Instantiate some switches. This is so we can ask to get their parameters later.
    Rainier = panel()
    Adams = xb5()
    Lakeview = xb1()
    Step = step()

    # Connect to AMI
    client = AMIClient(address='127.0.0.1',port=5038)
    future = client.login(username='panel_gen',secret='t431434')
    if future.response.is_error():
        raise Exception(str(future.response))

    # The below calls curses wrapper and tells it to run the function 'start', which actually sets
    # everything in motion. This is the lynchpin, here. It's in a [try] block, so if there's an
    # exception like a keyboard interrupt, the output below will still get printed to the screen,
    # even after curses cleans up.
    try:
        curses.wrapper(start)

    # Gracefully handle keyboard interrupts.
    except KeyboardInterrupt:

        # Clean up curses.
        print "\nShutdown requested. Hanging up Asterisk channels, and cleaning up /var/spool/"

        #Log out of AMI
        client.logoff()

        # Hang up and clean up spool.
        os.system("asterisk -rx \"channel request hangup all\"")
        os.system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")
        logging.info("--- Caught keyboard interrupt! Shutting down gracefully. ---")

    except OSError as err:

        print("\nOS error {0}".format(err))
        logging.error('**** OS Error ****')
        logging.error('{0}'.format(err))
        logging.error('Check files that subprocess and logging try to open. Something is screwy there')


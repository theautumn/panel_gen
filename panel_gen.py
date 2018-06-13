#---------------------------------------------------------------------#
#                                                                     #
#  A call generator thing for the Rainier Panel switch at the         #
#  Connections Museum, Seattle WA.                                    #
#                                                                     #
#  Written by Sarah Autumn, 2017                                      #
#  sarah@connectionsmuseum.org                                        #
#  github.com/the_autumn/panel_gen                                    #
#                                                                     #
#---------------------------------------------------------------------#

import time
import os 
import sys
import subprocess
import argparse
from tabulate import tabulate
from numpy import random
from pathlib import Path
from pycall import CallFile, Call, Application

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
            self.term = self.p_term()                               # Generate a term line randomly.

        self.timer = int(round(random.gamma(4,4)))                  # else use the normal start formula.
        self.ident = ident                                          # Set an integer for identity.

    def set_timer(self):
        self.timer = switch.newtimer
        return self.timer

    def tick(self):
        # Decrement timers by 1 every second until it reaches 0
        # At 0, check status and call or hangup as necessary.

        self.timer -= 1
        if self.timer == 0:
            if self.status == 0:
                self.call()
            else:
                self.hangup()
        return self.timer

    def p_term(self):

        global term_office
        term_office = []

        if args.t == []:   
            term_office = random.choice(self.switch.nxx, p=self.switch.trunk_load)  # Using weight, pick an office to call.
        
        for t in args.t:
            if t == 'panel' or t == '722':
                term_office = 722
            elif t == '5xb' or t == '232':
                term_office = 232
            elif t == '1xb' or t == '832':
                term_office = 832
            elif t == 'office' or t == '365':
                term_office = 365
            else:
                assert False

        term_station = random.randint(5000,5999)             # Pick a random station that appears on our final frame.
        term = int(str(term_office) + str(term_station))     # And put it together.
        return term

    def call(self):
        # Dialing takes ~10 to 12 seconds. This should be somewhat consistent value because its done
        # by Asterisk / DAHDI. We're going to set a timer for call duration here, and then a few lines down,
        # we're gonna tell Asterisk to set its own wait timer to the same value - 10. This should give us a reasonable
        # buffer between the program's counter and Asterisk's wait timer (which itself begins when the call goes from 
        # dialing to "UP").

        if args.d:                                                      # Are we in deterministic mode?
            if args.z:                                                  # args.z is call duration
                self.timer = args.z                                     # Set length of call to what user specified
            else:
                self.timer = 15                                         # If no args.z defined, use default value for -d mode.
        else:                                                           # If we are in normal mode, then it's easy
            self.timer = self.switch.newtimer()                         # Reset the timer for the next go-around.
        
        c = Call('DAHDI/' + self.switch.dahdi_group + '/www%s' % self.term)   # Call DAHDI, on the right group. Wait before dialing.
        a = Application('Wait', str(self.timer - 10))                           # Make Asterisk wait once the call is connected.
        cf = CallFile(c,a, user='asterisk')                             # Make the call file
        cf.spool()                                                      # and throw it in the spool

        self.status = 1                                                 # Set the status of the call to 1 (active)

    def hangup(self):
        # This is more for show than anything else. Asterisk manages the actual hangup of a call in progress.
        # The deal here is to set a new wait timer, set the status to 0 (on hook), and randomly pick a new term
        # line for the next go-around.

        self.status = 0                                         # Set the status of this call to 0.

        if args.d:                                              # Are we in deterministic mode?
            if args.w:                                          # args.w is wait time between calls
               self.timer = args.w                              # Set the length of the wait time before next call
            else:
                self.timer = 15                                 # If no args.w defined, use default value.
        else:
            self.timer = self.switch.newtimer()                 # <-- Normal call timer if args.d is not specified.

        if args.l:                                              # If user specified a line
            self.term = args.l                                  # Set term line to user specified
        else:                                                   # Else,
            self.term = self.p_term()                           # Pick a new terminating line. 


class panel():                                              
# This class is parameters and methods for the panel switch.  It should not normally need to be edited.
# If you wish to change the office codes, or trunk weight, this is where you do it.
    
    def __init__(self):
        self.kind = "panel"
        self.max_dialing = 6                                    # We are limited by the number of senders we have.
        self.dahdi_group = "r6"                                 # This tells Asterisk where the Adit is.
        
        self.dcurve = self.newtimer()                           # Start a fresh new timer.
        
        if args.d:                                              # If deterministic mode is set,
            self.max_calls = 1                                  # Set the max calls to 1, to be super basic.
        else:
            self.max_calls = args.a                             # Else, panel max is 3 by default.

        self.max_nxx1 = .6                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .2                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                       # Load for office 4 in self.trunk_load
        self.nxx = [722, 365, 232]                              # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))          # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(5,2)))           # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))          # Medium Traffic
        return t

class xb1():
# This class is for the No. 1 Crossbar. Same as panel, above, but with different parameters.

    def __init__(self):
        self.kind = "1xb"
        self.max_dialing = 2                                    # We are limited by the number of senders we have.
        self.dahdi_group = "r11"                                 # This tells Asterisk where the Adit is.
        
        self.dcurve = self.newtimer()                           # Start a fresh new timer.

        if args.d:                                              # If deterministic mode is set,
            self.max_calls = 1                                  # Set the max calls to 1, to be super basic.
        else:
           # self.max_calls = args.a                             # Else, max is 3 by default.
            self.max_calls = 2

        self.max_nxx1 = .3                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .3                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .4                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                       # Load for office 4 in self.trunk_load
        self.nxx = [722, 832, 232]                              # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))          # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(5,9)))           # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))          # Medium Traffic
        return t


class xb5():
# This class is for the No. 5 Crossbar. Same as panel, above, but with different parameters.

    def __init__(self):
        self.kind = "5XB"
        self.max_dialing = 7                                    # We are limited by the number of senders we have.
        self.dahdi_group = "r7"                                 # This tells Asterisk where the Adit is.

        self.dcurve = self.newtimer()                           # Start a fresh new timer.

        if args.d:                                              # If deterministic mode is set,
            self.max_calls = 1                                  # Set the max calls to 1, to be super basic.
        else:
            self.max_calls = args.a                             # Else, panel max is 3 by default.

        self.max_nxx1 = .2                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .4                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = .2                                      # Load for office 4 in self.trunk_load
        self.nxx = [722, 832, 232, 275]                         # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3, self.max_nxx4]  # And put the trunk load together.

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))          # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(5,2)))           # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))          # Medium Traffic
        return t

# MAIN LOOP I GUESS
if __name__ == "__main__":

    # Stuff for command line arguments, so we can configure some options at runtime.
    # If no arguments are presented, the program will run with default
    # mostly sane options.

    parser = argparse.ArgumentParser(description='Generate calls to electromechanical switches. Defaults to originate a sane amount of calls from the panel switch if no args are given.')
    parser.add_argument('-a', metavar='lines', type=int, default=3, choices=[1,2,3,4,5,6,7],
                        help='Maximum number of active lines. Default is 3 for the panel switch. Other switches will depend on stuff.')
    parser.add_argument('-d', action='store_true', help='Deterministic mode. Eliminate timing randomness so various functions of the switch can be tested at-will. Places one call at a time. Will ignore -a and -v options entirely. Use with -l.')
    parser.add_argument('-l', metavar='line', type=int, 
                        help='Call only a particular line. Can be used with the -d option for placing test calls to a number over and over again.')
    parser.add_argument('-o', metavar='switch', type=str, nargs='?', action='append', default=[],  choices=['1xb','5xb','panel','all','722', '832', '232'],
                        help='Originate calls from a particular switch. Takes either 3 digit NXX values or switch name.  1xb, 5xb, panel, or all. Default is panel.')
    parser.add_argument('-t', metavar='switch', type=str, nargs='?', action='append', default=[], choices=['1xb','5xb','panel', 'office', '722', '832', '232', '365'],
                        help='Terminate calls only on a particular switch. Takes either 3 digit NXX values or switch name. Defaults to sane options for whichever switch you are originating from.')
    parser.add_argument('-v', metavar='volume', type=str, default='normal',
                        help='Call volume is a proprietary blend of frequency and randomness. Can be light, normal, or heavy. Default is normal, which is good for average load.')
    parser.add_argument('-w', metavar='seconds', type=int, help='Use with -d option to specify wait time between calls.')
    parser.add_argument('-z', metavar='seconds', type=int, help='Use with -d option to specify call duration.')

    args = parser.parse_args()

    # Before we do anything else, the program needs to know which switch it will be originating calls from.
    # Can be any of switch class: panel, xb5, xb1, all
    
    global switches
    switches = []

    if args.o == []:                  # If no args provided, just assume panel switch.
        args.o = ['panel']

    for o in args.o:
        if o == 'panel' or o == '722':                  # If args provided then go with that..
            switches.append(panel())
        elif o == '5xb' or o == '232':                  
            switches.append(xb5())
        elif o == '1xb' or o == '832':                   
            switches.append(xb1())
        elif o == 'all':
            switches.extend((xb1(), xb5(), panel()))

    try:
        line = [Line(n, switch) for switch in switches for n in range(switch.max_calls)]    # Make lines.
        while True:                                                                         # While always
            for n in line:                                                                  # For as many lines as there are.
                n.tick()                                                                    # Tick the timer, and do the things.
    
            # Output handling. Clear screen, draw table, sleep 1, repeat ... 
            os.system('clear')
            table = [[n.kind, n.ident, n.term, n.timer, n.status] for n in line]
            print " __________________________________________" 
            print "|                                          |"
            print "|  Rainier Full Mechanical Call Simulator  |"
            print "|__________________________________________|\n\n"
            print tabulate(table, headers=["switch", "ident", "term", "tick", "status"], tablefmt="pipe") 

            # Print asterisk channels below the table so we can see what its actually doing.
            ast_out = subprocess.check_output(['asterisk', '-rx', 'core show channels'])
            print "\n\n" + ast_out

            # Take a nap.
            time.sleep(1)
            
    # Gracefully handle keyboard interrupts. 
    except KeyboardInterrupt:
            print ""
            print "Shutdown requested. Cleaning up Asterisk and /var/spool/"
            os.system("asterisk -rx \"channel request hangup all\"")
            os.system("rm /var/spool/asterisk/outgoing/*.call > /dev/null 2>&1")


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

    def __init__(self, ident):
        self.status = 0
        self.term = self.p_term()
        self.timer = int(round(random.gamma(4,4)))
        self.ident = ident

    def set_timer(self):
        self.timer = switch.newtimer
        return self.timer

    def tick(self):
        # Decrement timers by 1 every second until it reaches 0
        # Also check status and call or hangup as necessary.

        self.timer -= 1
        if self.timer == 0:
            if self.status == 0:
                self.call()
            else:
                self.hangup()
        return self.timer

    def p_term(self):
        term_office = random.choice(switch.nxx, p=switch.trunk_load)    # Using weight, pick an office to call.
        term_station = random.randint(5000,5999)                        # Pick a random station that appears on our final frame.
        term = int(str(term_office) + str(term_station))                # And put it together.
        return term

    def call(self):
        # Dialing takes ~10 to 12 seconds. This should be somewhat consistent value because its done
        # by Asterisk / DAHDI. We're going to set a timer for call duration here, and then a few lines down,
        # we're gonna tell Asterisk to set its own wait timer to the same value - 10. This should give us a reasonable
        # buffer between the program's counter and whatever Asterisk is doing.

        self.timer = switch.newtimer()                                  # Reset the timer for the next go-around.
        c = Call('DAHDI/' + switch.dahdi_group + '/wwwww%s' % self.term)  # Call DAHDI, Group 6. Wait a second before dialing.
        a = Application('Wait', str(self.timer - 10))                   # Make Asterisk wait once the call is connected.
        cf = CallFile(c,a, user='asterisk', archive = True)             # Make the call file
        cf.spool()                                                      # and throw it in the spool

        self.status = 1                                                 # Set the status of the call to 1 (active)

    def hangup(self):
        # This is more for show than anything else. Asterisk manages the actual hangup of a call in progress.
        # The deal here is to set a new wait timer, set the status to 0 (on hook), and randomly pick a new term
        # line for the next go-around.

        self.timer = switch.newtimer()                                  # Set a timer to wait before another call starts.
        self.status = 0                                                 # Set the status of this call to 0.
        self.term = self.p_term()                                       # Pick a new terminating line. 


class panel():                                              
# This class is parameters and methods for the panel switch.  It should not normally need to be edited.
# If you wish to change the office codes, or trunk weight, this is where you do it.
    
    def __init__(self):
        self.kind = "panel"
        self.dcurve = int(round(random.gamma(4,14)))            # Medium/High Traffic
       # self.dcurve = int(round(random.gamma(20,8)))           # Low Traffic
        self.max_dialing = 6                                    # We are limited by the number of senders we have.
        self.max_calls = 3                                      # Max number of calls that can be in progress. Lower is safer.
        self.max_nxx1 = .5                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .3                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                       # Load for office 4 in self.trunk_load
        self.max_nxx5 = .0                                      # Load for office 5 in self.trunk_load
        self.nxx = [722, 365, 232]                              # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.
        self.dahdi_group = "r6"

    def newtimer(self):
        t = int(round(random.gamma(4,14)))
        return t

class test():
# This class will be set up to test specific switch functions. It can be edited at will to create any kind of call environment
# that's needed without impacting the performace of the other classes. Call it from the main loop below.

    def __init__(self):
        self.kind = "test"
        self.dcurve = int(round(random.gamma(4,12)))           # Medium/High Traffic
        self.max_dialing = 3                                   # We are limited by the number of senders we have.
        self.max_calls = 1                                     # Max number of calls that can be in progress. Lower is safer.
        self.max_nxx1 = .2                                     # Load for office 1 in self.trunk_load
        self.max_nxx2 = .6                                     # Load for office 2 in self.trunk_load
        self.max_nxx3 = .2                                     # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                      # Load for office 4 in self.trunk_load
        self.max_nxx5 = .0                                     # Load for office 5 in self.trunk_load
        self.nxx = [232]                                       # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.
        self.dahdi_group = "r0"

    def newtimer(self):
        t = int(round(random.gamma(4,14)))
        return t

class xb5():
# This class is for the No. 5 Crossbar. Same as panel, above, but with different parameters.

    def __init__(self):
        self.kind = "5xb"
        self.dcurve = int(round(random.gamma(3,10)))
        self.max_dialing = 7                                    # We are limited by the number of ORs we have.
        self.max_nxx1 = .6                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .2                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                       # Load for office 4 in self.trunk_load
        self.max_nxx5 = .0                                      # Load for office 5 in self.trunk_load
        self.nxx = [232, 832, 722]                              # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.
        self.dahdi_group = "r0"

    def newtimer(self):
        t = int(round(random.gamma(4,10)))
        return t

# MAIN LOOP I GUESS
if __name__ == "__main__":

    # Stuff for command line arguments, so we can configure some options at runtime.
    # If no arguments are presented, the program will run with default
    # mostly sane options. Therefore, I'm only going to go back into the code
    # and specify what happens *if* arguments are given.

    # This will probably be the following:
        # Which switch to use: panel, 1xb, 5xb, test-only
        # Call volume adjectives: busy, light (normal is normal)
        # Integer for maximum number of active lines at a given time.
        # Office codes to exclude: 722, 365, 832, 232, 929

    parser = argparse.ArgumentParser(description='Generate calls to electromechanical switches.')
    parser.add_argument('-s', metavar='switch', type=str, nargs='?', default='panel',
                        help='Which office to originate calls through: panel, 1xb, 5xb')
    parser.add_argument('-l', metavar='call volume', type=str, nargs='?', default='normal',
                        help='Call volume can be light, normal, or busy. Default is normal, which is good for average load.')
    parser. add_argument('-m', metavar='max active', type=int, nargs='?', default=3,
                        help='Maximum number of active lines. Default is 3 for the panel switch. Other switches will depend on stuff.')
    parser.add_argument('-x', metavar='office code', type=str, nargs='?', default="",
                        help='Exclude a particular switch from being called. Expects a 3-digit office code.')

    args = parser.parse_args()

    
    # Before we do anything else, the program needs to know which switch it will be originating calls from.
    # Can be any of switch class: panel, xb5, xb1
    
    global switch

    switch = panel()
#   switch = xb5()
#   switch = test()

    try:
        line = [Line(n) for n in range (switch.max_calls)]      # Make lines.
        while True:                                             # While always
            for n in line:                                      # For as many lines as there are.
                n.tick()                                        # Tick the timer, and do the things.
    
            # Output handling. Clear screen, draw table, sleep 1, repeat ... 
            os.system('clear')
            table = [[n.ident, n.term, n.timer, n.status] for n in line]
            print " __________________________________________" 
            print "|                                          |"
            print "|  Rainier Full Mechanical Call Simulator  |"
            print "|__________________________________________|\n\n"
            print tabulate(table, headers=["ident", "term", "tick", "status"], tablefmt="pipe") 

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


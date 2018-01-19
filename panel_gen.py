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
from tabulate import tabulate
from numpy import random
from pathlib import Path
from pycall import CallFile, Call, Application

# Main class for calling lines. Contains all the essential vitamins and minerals.
# It's an important part of a balanced breakfast.
class Line():
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
        # Dialing takes ~12.6 seconds. This should be somewhat consistent value because its done
        # by Asterisk / DAHDI. We're going to set a timer for call duration here, and then a few lines down,
        # we're gonna tell Asterisk to set its own wait timer to the same value - 10. This should give us a reasonable
        # buffer between the program's counter and whatever Asterisk is doing.

        self.timer = switch.newtimer()                                  # Reset the timer for the next go-around.
        c = Call('DAHDI/r6/wwwww%s' % self.term)                        # Call DAHDI, Group 6. Wait a second before dialing.
        a = Application('Wait', str(self.timer - 10))                   # Make Asterisk wait once the call is connected.
        cf = CallFile(c,a, user='asterisk', archive = True)             # Make the call file
        cf.spool()                                                      # and throw it in the spool

        self.status = 1                                                 # Set the status of the call to 1 (active)

    def hangup(self):
         # This isn't doing that much, since Asterisk is managing the hangup.
         # Really, it's not timed very well, since its just for show.
         # I'll have to come back to this and figure it out.

        self.timer = switch.newtimer()                                  # Set a timer to wait before another call starts.
        self.status = 0                                                 # Set the status of this call to 0.
        self.term = self.p_term()                                       # Pick a new terminating line. 

        if Path("/var/spool/asterisk/outgoing/" + str(self.term) + ".call").is_file():  # Delete the call file if there is one.
            os.remove("/var/spool/asterisk/outgoing/" + str(self.term) + ".call")       # Yep
        else:
            return

class panel():                                              
# This class is parameters and methods for the panel switch.  It should not normally need to be edited.
# If you wish to change the office codes, or trunk weight, this is where you do it.
    
    def __init__(self):
        self.kind = "panel"
        self.dcurve = int(round(random.gamma(4,14)))            # Medium/High Traffic
       # self.dcurve = int(round(random.gamma(20,8)))           # Low Traffic
        self.max_dialing = 6                                    # We are limited by the number of senders we have.
        self.max_calls = 4                                      # Max number of calls that can be in progress. Lower is safer.
        self.max_nxx1 = .5                                      # Load for office 1 in self.trunk_load
        self.max_nxx2 = .2                                      # Load for office 2 in self.trunk_load
        self.max_nxx3 = .3                                      # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                       # Load for office 4 in self.trunk_load
        self.max_nxx5 = .0                                      # Load for office 5 in self.trunk_load
        self.nxx = [722, 365, 232]                              # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.

    def newtimer(self):
        t = int(round(random.gamma(4,14)))
        return t

class test():
# This class will be set up to test specific switch functions. It can be edited at will to create any kind of call environment
# that's needed without impacting the performace of the other classes. Call it from the main loop below.

    def __init__(self):
        self.kind = "panel"
        self.dcurve = int(round(random.gamma(4,12)))           # Medium/High Traffic
        self.max_dialing = 6                                   # We are limited by the number of senders we have.
        self.max_calls = 1                                     # Max number of calls that can be in progress. Lower is safer.
        self.max_nxx1 = .2                                     # Load for office 1 in self.trunk_load
        self.max_nxx2 = .6                                     # Load for office 2 in self.trunk_load
        self.max_nxx3 = .2                                     # Load for office 3 in self.trunk_load
        self.max_nxx4 = 0                                      # Load for office 4 in self.trunk_load
        self.max_nxx5 = .0                                     # Load for office 5 in self.trunk_load
        self.nxx = [232]                                       # Office codes that can be dialed.
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  # And put the trunk load together.

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

    def newtimer(self):
        t = int(round(random.gamma(4,10)))
        return t

# MAIN LOOP I GUESS
def main():

    global switch

    # Change this to edit the behavior of the program to be suitable for whichever switch you'd like to use it on.
    # This gives us the ability to "port" the program to control calls through the different machines at the museum.
    # Can be any of switch class: panel, xb5, xb1, step, cx100
    
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

            time.sleep(1)

    # The below is here in an attempt to gracefully handle keyboard interrupts. 
    except KeyboardInterrupt:
            print ""
            print "Shutdown requested...cleaning up Asterisk spool"
            os.system("asterisk -rx \"channel request hangup all\"")
            os.system("rm /var/spool/asterisk/outgoing/*.call")
#    except Exception:
#           traceback.print_exc(file=sys.stdout)
#           sys.exit(0)

if __name__ == "__main__":
    main()

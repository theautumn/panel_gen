#-----------------------------------------------------------------------#
#                                                                       #
# A call generator thing for the Rainier Panel switch at the            #
# Connections Museum, Seattle WA.                                       #
#                                                                       #
# Written by Sarah Autumn, 2017                                         #
# I have no idea what I'm even doing.                                   #
# This program assumes the following:                                   #
#       - You are at the museum.                                        #
#       - You have access to the Panel switch                           #
#       - Your name is Sarah Autumn                                     #
#                                                                       #
#-----------------------------------------------------------------------#

import time
import os 
import sys
import traceback
from tabulate import tabulate
from numpy import random
from pathlib import Path
from pycall import CallFile, Call, Application

class Line():
    def __init__(self, ident):
        self.status = 0
        self.orig = lines_loaded.pop() 
        self.term = self.p_term()
        self.timer = random.randint(4,20)
        self.ident = ident
        self.group = "r6"

    def set_timer(self):
        self.timer = random.randint(15,55)
        return self.timer

    def tick(self):
        # Decrement timers by 1 every second until it reaches 0
        self.timer -= 1
        if self.timer == 0:
            if self.status == 0:
                self.call()
            else:
                self.hangup()
        return self.timer

    def p_term(self):
        term_office = random.choice(panel.nxx, p=panel.trunk_load)    # Using weight, pick an office to call.
        term_station = random.randint(5000,5999)
        term = int(str(term_office) + str(term_station))
        return term

    def call(self):
        self.timer= random.randint(18,55)
            
        c = Call('DAHDI/r6/wwwww%s' % self.term)
        a = Application('Wait', str(self.timer - 2))
        cf = CallFile(c,a, user='asterisk', archive = True)
        cf.spool()

        self.status = 1

    def hangup(self):
        self.timer = random.randint(18,55)
        # Kill an active call.
        self.status = 0
        self.term = self.p_term()
        lines_loaded.insert(0,self.orig)
        self.orig = lines_loaded.pop()
        if Path("/var/spool/asterisk/outgoing/" + str(self.term) + ".call").is_file():
            os.remove("/var/spool/asterisk/outgoing/" + str(self.term) + ".call")
        else:
            return

class Switch():
    def __init__(self):
        self.kind = "panel"
        self.max_dialing = 6                                    # We are limited by the number of senders we have.
        self.max_calls = 5                                      # Set to 4 for testing. Can be changed later.
        self.max_office = 1                                    # Load for panel intraoffice trunks
        self.max_district = 0                                  # needs to equal 1 or numpy gets mad.
        self.max_5xb = .0                                        # Max trunks to 5XB       
        self.max_1xb = .0                                        # Max trunks to 1XB
        self.nxx = [722, 365]                                   # Office codes
        self.trunk_load = [self.max_office, self.max_district]

    def bullshit():
        # Insert bullshit
        return


# MAIN LOOP BULLSHIT
def main():
    try:
        global lines_loaded
        global panel
        
        with open('./lines.txt') as f:               # Open text file containing calling lines.
            lines_loaded = f.read().splitlines()     # and write it to lines_available

        panel = Switch()

        line = [Line(n) for n in range (panel.max_calls)]
        while True:
            for n in line: 
                n.tick()
    
            # Output handling. Clear screen, draw table, sleep 1, repeat ... 
            os.system('clear')
            table = [[n.ident, n.orig, n.term, n.timer, n.status] for n in line]
            print tabulate(table, headers=["ident", "orig", "term", "tick", "status"], tablefmt="pipe") 
            time.sleep(1)

    except KeyboardInterrupt:
            print ""
            print "Shutdown requested...cleaning up Asterisk spool"
            os.system("rm /var/spool/asterisk/outgoing/*.call")
    except Exception:
           traceback.print_exc(file=sys.stdout)
           sys.exit(0)

if __name__ == "__main__":
    main()

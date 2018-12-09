class panel():
# This class is parameters and methods for the panel switch.  It should not normally need to be edited.
# If you wish to change the office codes, or trunk weight, this is where you do it.

    def __init__(self):
        self.kind = "panel"                                     # The kind of switch we're calling from.
        self.max_dialing = 6                                    # We're limited by number of senders we have.
        self.is_dialing = 0
        self.dahdi_group = "r6"                                 # Which DAHDI group to originate from.
        self.dcurve = self.newtimer()                           # Start a new timer when switch is instantiated.

        if args.d:                                              # If deterministic mode is set,
            self.max_calls = 1                                  # Set the max calls to 1, to be super basic.
        elif args.a:
            self.max_calls = args.a                             # Else, use the value given with -a
        else:
            self.max_calls = 3                                  # Finally, if no args are given, use this default.

#        logging.info('Concurrent lines: %s', self.max_calls)

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

#        logging.info('Concurrent lines: %s', self.max_calls)

        self.max_nxx1 = .5
        self.max_nxx2 = .5
        self.max_nxx3 = 0
        self.max_nxx4 = 0
        self.nxx = [722, 832, 232]
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3]  
        self.linerange = [105, 129]

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

#        logging.info('Concurrent lines: %s', self.max_calls)

        self.max_nxx1 = .2
        self.max_nxx2 = .2
        self.max_nxx3 = .4
        self.max_nxx4 = .2
        self.nxx = [722, 832, 232, 275]
        self.trunk_load = [self.max_nxx1, self.max_nxx2, self.max_nxx3, self.max_nxx4] 
        self.linerange = [5000,5999]

    def newtimer(self):
        if args.v == 'light':
            t = int(round(random.gamma(20,8)))                  # Low Traffic
        elif args.v == 'heavy':
            t = int(round(random.gamma(4,6)))                   # Heavy Traffic
        else:
            t = int(round(random.gamma(4,14)))                  # Medium Traffic
        return t

class step():
# This class is for the SxS office. It's very minimal right now, as we are not currently
# originating calls from there, only completing them from the 5XB.

    def __init__(self):
        self.kind = "Step"
        self.linerange = [4100,4199]

#!/usr/bin/python
#---------------------------------------------------------------------#
#                                                                     #
#  A frontend console for panel_gen                                   #
#                                                                     #
#  Written by Sarah Autumn, 2017-2019                                 #
#  sarah@connectionsmuseum.org                                        #
#  github.com/theautumn/panel_gen                                     #
#                                                                     #
#---------------------------------------------------------------------#

from time import sleep
import signal
import subprocess
import curses
import re
import threading
import logging
import requests
from marshmallow import Schema, fields, post_load, ValidationError
from tabulate import tabulate

class Line(object):
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
    self.chan:          DAHDI channel being used for call in progress
    self.ast_status:    Status of line according to Asterisk
    """

    def __init__(self, kind, status, term, timer, ident, chan, ast_status, **kwargs):
        self.kind = kind
        self.status = status
        self.term = term
        self.timer = timer
        self.ident = ident
        self.chan = chan
        self.ast_status = ast_status

    def __repr__(self):
        return '<Line(name={self.ident!r})>'.format(self=self)


# +----------------------------------------------------+
# |                                                    |
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
    ident = fields.Integer()
    kind = fields.Str()
    status = fields.Integer()
    timer = fields.Integer()
    ast_status = fields.Str()
    chan = fields.Str()
    term = fields.Str()
    hook_state = fields.Integer()

    @post_load
    def make_line(self, data):
        return Line(**data)

class MuseumSchema(Schema):
    status = fields.Boolean()

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
        if curses.has_colors():
            curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)
            curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
        self.y, self.x = stdscr.getmaxyx()
        stdscr.nodelay(1)
        self.screen = stdscr

        self.stdscr = stdscr

    def update_size(self, stdscr, y, x):
        # This gets called if the screen is resized. Makes it happy so exceptions don't get thrown.

        self.stdscr.clear()
        curses.resizeterm(y, x)
        self.stdscr.refresh()

    def getkey(self, stdscr):
        # Handles user input.

        key = stdscr.getch()
        if key == ord(' '):
            pass

    def draw(self, stdscr, lines, y, x):
        # Output handling. make pretty things.
        table = [[n.ident, n.kind, n.chan, n.term, n.timer, n.status, n.ast_status] for n in lines]
        stdscr.erase()
        stdscr.addstr(0, 5, " __________________________________________")
        stdscr.addstr(1, 5, "|                                          |")
        stdscr.addstr(2, 5, "|  Rainier Full Mechanical Call Simulator  |")
        stdscr.addstr(3, 5, "|__________________________________________|")
        stdscr.addstr(6, 0, tabulate(table, headers=["ident", "switch", "channel", "term",
            "tick", "state", "asterisk"],
            tablefmt="pipe", stralign = "right" ))

        # Print the contents of /var/log/panel_gen/calls.log
        if y > 45:
            try:
                logs = subprocess.check_output(['tail', '-n', '15', '/var/log/panel_gen/calls.log'])
                stdscr.addstr(32, 5, '================= Logs =================')
                stdscr.addstr(34, 0, logs)
            except Exception as e:
                pass

        y, x = self.stdscr.getmaxyx()
        cols = x
        rows = 1
        x_start_row = y - 1
        y_start_col = 0

        statusbar = self.stdscr.subwin(rows, cols, x_start_row, y_start_col)
        statusbar.bkgd(' ', curses.color_pair(1))
        statusbar.addstr(0, 0, "ctrl + c: quit", curses.A_BOLD)
        statusbar.addstr(0, x/4, "Museum status:", curses.A_BOLD)
        if museum_up == True:
            statusbar.addstr(0, x/4+15, "ONLINE", curses.color_pair(3))
        else:
            statusbar.addstr(0, x/4+15, "OFFLINE", curses.color_pair(2))
        statusbar.addstr(0, x/2, "Server status:", curses.A_BOLD)
        if server_up == True:
            statusbar.addstr(0, x/2+15, "ONLINE", curses.color_pair(3))
        else:
            statusbar.addstr(0, x/2+15, "OFFLINE", curses.color_pair(2))
        statusbar.addstr(0, x-15, "Lines:", curses.A_BOLD)
        statusbar.addstr(0, x-8, str(len(lines)), curses.A_BOLD)

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
            print(e)

    def ui_main(self, stdscr):

        global screen
        # Instantiate a screen, so we can play with it later.
        screen = Screen(stdscr)

        while not self.shutdown_flag.is_set():

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

class work_thread(threading.Thread):

    def __init__(self):

        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()

    def run(self):

        global lines
        global server_up

        while not self.shutdown_flag.is_set():
            self.is_alive = True

            try:
                r = requests.get(APISERVER, timeout=.5)
                schema = LineSchema()
                try:
                    result = schema.loads(r.content.decode('UTF-8'), many=True)
                except ValidationError as err:
                        print(err.messages)  # => {"email": ['"foo" is not a valid email address.']}
                        print(err.valid_data)  # => {"name": "John"}
                lines = result[0]
                server_up = True
                failcount = 0
                sleep(1)
            except requests.exceptions.RequestException:
                server_up = False
                failcount += 1
                if failcount == 1:
                    logger.critical("Connections service not running!")
                sleep(10)
                continue

class museum_thread(threading.Thread):

    def __init__(self):

        threading.Thread.__init__(self)
        self.shutdown_flag = threading.Event()

    def run(self):

        global museum_up
        timer = 40

        while not self.shutdown_flag.is_set():
            self.is_alive = True
            timer = timer - 1
            sleep(.5)
            if timer <= 0:
                try:
                    museum_pstate = museum_up
                    r = requests.get(MUSEUMSTATE, timeout=5)
                    schema = MuseumSchema()
                    result = schema.loads(r.content.decode())
                    museum = result[0]
                    for k, v in list(museum.items()):
                        museum_up = v
                    if museum_pstate != museum_up:
                        logger.warning("Museum state changed from %s to %s",
                                museum_pstate, museum_up)
                    timer = 40
                except requests.exceptions.RequestException:
                    museum_up = False
                    #logger.error("Timeout reached while checking museum status")
                    timer = 40
                    continue

class ServiceExit(Exception):
    pass

def app_shutdown(signum, frame):
    raise ServiceExit


if __name__ == "__main__":

    # Set up signal handlers so we can shutdown cleanly later.
    signal.signal(signal.SIGTERM, app_shutdown)
    signal.signal(signal.SIGINT, app_shutdown)

    APISERVER = "http://192.168.0.204:5000/api/lines"
    MUSEUMSTATE = "http://192.168.0.204:5000/api/museum"
    lines = []
    server_up = False
    museum_up = False
    failcount = 0

    try:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s',
                '%m/%d/%Y %I:%M:%S %p')
        handler = logging.FileHandler('/var/log/panel_gen/calls.log')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    except IOError:
        pass

    logger.info('Started console')

    try:
        w = work_thread()
        w.daemon = True
        w.start()
        w2 = museum_thread()
        w2.daemon = True
        w2.start()
        t = ui_thread()
        t.daemon = True
        t.start()

        while True:
            sleep(0.5)

    except (KeyboardInterrupt, ServiceExit):
        # Exception handler for console-based shutdown.

        t.shutdown_flag.set()
        t.join()
        w.shutdown_flag.set()
        w.join()
        w2.shutdown_flag.set()
        w2.join()

        print('\n')

    except Exception as e:
        # Exception for any other errors that I'm not explicitly handling.
        print(e)
        t.shutdown_flag.set()
        t.join()
        w.shutdown_flag.set()
        w.join()
        w2.shutdown_flag.set()
        w2.join()

        print(("\nOS error {0}".format(e)))

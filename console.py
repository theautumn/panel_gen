#!/usr/bin/python3
#---------------------------------------------------------------------#
#                                                                     #
#  A frontend console for panel_gen                                   #
#                                                                     #
#  Written by Sarah Autumn, 2017-2021                                 #
#  sarah@connectionsmuseum.org                                        #
#  github.com/theautumn/panel_gen                                     #
#                                                                     #
#---------------------------------------------------------------------#

from time import sleep
import signal
import subprocess
import curses
from curses.textpad import Textbox, rectangle
import re
import threading
import logging
import requests
from marshmallow import Schema, fields, post_load, ValidationError
from tabulate import tabulate

class Line(object):
	"""
	This class defines Line objects.
	For help, see panel_gen.py
	"""

	def __init__(self, kind, status, term, human_term, timer, ident, chan, ast_status, **kwargs):
		self.kind = kind
		self.status = status
		self.term = term
		self.human_term = human_term
		self.timer = timer
		self.ident = ident
		self.chan = chan
		self.ast_status = ast_status

	def __repr__(self):
		return '<Line(name={self.ident!r})>'.format(self=self)

class Switch():
	"""
	This class is parameters and methods for a switch.
	For help, see panel_gen.py
	"""

	def __init__(self, kind, running, max_dialing, is_dialing, on_call, dahdi_group, traffic_load, lines_normal, lines_heavy, trunk_load, line_range):
		self.kind = kind
		self.running = running
		self.max_dialing = max_dialing
		self.is_dialing = is_dialing
		self.on_call = on_call
		self.dahdi_group = dahdi_group
		self.traffic_load = traffic_load
		self.lines_normal = lines_normal
		self.lines_heavy = lines_heavy
		self.trunk_load = []
		self.line_range = ''.split(",")
		self.numlines = sum(n.kind == kind for n in lines)


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
	human_term = fields.Str()
	hook_state = fields.Integer()

	@post_load
	def make_line(self, data, **kwargs):
		return Line(**data)

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
		curses.curs_set(0)
		if curses.has_colors():
			curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
			curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_RED)
			curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
			curses.init_pair(4, curses.COLOR_BLUE, curses.COLOR_BLACK)
		self.y, self.x = stdscr.getmaxyx()
		stdscr.nodelay(1)
		self.screen = stdscr

		self.stdscr = stdscr

		def update_size(self, stdscr, y, x):
			# This gets called if the screen is resized. Makes it happy so exceptions don't get thrown.

			self.stdscr.clear()
			curses.resizeterm(y, x)
			self.stdscr.refresh()

	def getkey(self, stdscr, curscreen):
		# Handles user input.

		key = stdscr.getch()
		if key == ord('1'):
			curscreen = 1
		if key == ord('2'):
			curscreen = 2

		return curscreen

	def draw(self, stdscr, lines, y, x):
		# Output handling. make pretty things.

		stdscr.erase()

		y,x = stdscr.getmaxyx()
		cols = x
		rows = 1
		x_start_row = y - 1
		y_start_col = 0

		table = [[n.ident, n.kind, n.chan, n.human_term, n.timer, n.status, n.ast_status] for n in lines]
		try: 
			stdscr.addstr(1, 6, " __________________________________________")
			stdscr.addstr(2, 6, "|                                          |")
			stdscr.addstr(3, 6, "|  Rainier Full Mechanical Call Simulator  |")
			stdscr.addstr(4, 6, "|__________________________________________|")
			stdscr.addstr(7, 0, tabulate(table, headers=["ident", "switch", "channel", "term",
				"tick", "state", "asterisk"],
				tablefmt="psql", stralign = "right" ))

			if len(lines) < 13 and y > len(lines) + 30 or y > 50:
				# Print the contents of /var/log/panel_gen/calls.log
				logs = subprocess.check_output(['tail', '-n', '15', '/var/log/panel_gen/calls.log'])
				stdscr.addstr(len(lines) + 13, 5, '================= Logs =================')
				stdscr.addstr(len(lines) + 15, 0, logs)
		except Exception as e:
			pass


	def draw2(self, stdscr, switches, y, x):
		# View 2: Logs, Line stats

		stdscr.erase()

		y,x = stdscr.getmaxyx()
		cols = x
		rows = 1
		x_start_row = y - 1
		y_start_col = 0

		table = [[n.kind, n.numlines, n.on_call, n.is_dialing] for n in switches]
		try:
			stdscr.addstr(1, 0, " __________________________________________")
			stdscr.addstr(2, 0, "|                                          |")
			stdscr.addstr(3, 0, "|  Rainier Full Mechanical Call Simulator  |")
			stdscr.addstr(4, 0, "|__________________________________________|")
			stdscr.addstr(7, 0, tabulate(table, headers=["switch", "lines", "active", "dialing"],
				tablefmt="psql", stralign = "right" ))

			# Print a graph
			v_start = 17
			h_start = 10

			for n in switches:		
				kn = n.kind
				dg = n.is_dialing
				oc = n.on_call
				nl = n.numlines

				stdscr.addstr(v_start, 0, kn)

				i = 0
				while i < nl*2:						# Total Lines
					stdscr.addstr(v_start, h_start, '░', curses.color_pair(1))
					h_start += 1
					i += 1

				h_start = 10
				i = 0
				while i < oc*2:						# On Call
					stdscr.addstr(v_start, h_start, '▒', curses.color_pair(1))
					h_start += 1
					i += 1

				h_start = 10
				i = 0
				while i < dg*2:						# Dialing
					stdscr.addstr(v_start, h_start, '█')
					h_start += 1
					i += 1

				v_start +=1
				h_start = 10


			stdscr.addstr(21, h_start, '└─────────┴─────────┴─────────┘')
			stdscr.addstr(22, h_start, '0         5         10       15')

			# Print a channel table
			ch = [n.chan for n in lines]

			h_start_cht = 2


			uly = 24
			ulx = 0
			lly = 35
			llx = 49
			
			#curses.textpad.rectangle(stdscr, uly, ulx, lly, llx)
			stdscr.addstr(26,14,'DAHDI Channel Activity')

			j = 1
			while j <= 48:
					while j <= 8:
						stdscr.addstr(27 + j, h_start_cht, '_ ' + str(j))
						if str(j) in ch:
							stdscr.addstr(27 + j, h_start_cht,'▒', curses.color_pair(2))
						j += 1
					while j > 8 and j <= 16:
						stdscr.addstr(19 + j, h_start_cht + 8, '_ '+ str(j))
						if str(j) in ch:
							stdscr.addstr(19 + j, h_start_cht + 8, '▒', curses.color_pair(2))
						j += 1
					while j > 16 and j <= 24:
						stdscr.addstr(11 + j, h_start_cht + 16, '_ ' + str(j))
						if str(j) in ch:
							stdscr.addstr(11 + j, h_start_cht + 16, '▒', curses.color_pair(2))
						j += 1
					while j > 24 and j <= 32:
						stdscr.addstr(3 + j, h_start_cht + 24, '_ ' + str(j))
						if str(j) in ch:
							stdscr.addstr(3 + j, h_start_cht + 24, '▒', curses.color_pair(2))
						j += 1
					while j > 32 and j <= 40:
						stdscr.addstr(j - 5, h_start_cht + 32, '_ ' + str(j))
						if str(j) in ch:
							stdscr.addstr(j - 5, h_start_cht + 32, '▒', curses.color_pair(2))
						j += 1
					while j > 32 and j <= 48:
						stdscr.addstr(j - 13, h_start_cht + 40, '_ ' + str(j))
						if str(j) in ch:
							stdscr.addstr(j -13, h_start_cht + 40, '▒', curses.color_pair(2))
						j += 1
					j += 1
		except Exception:
				pass

	def drawstatus(self, stdscr, lines, y, x):

		y,x = stdscr.getmaxyx()
		cols = x
		rows = 1
		x_start_row = y - 1
		y_start_col = 0

		if x > 60:
			statusbar = self.stdscr.subwin(rows, cols, x_start_row, y_start_col)
			statusbar.bkgd(' ', curses.color_pair(1))
			statusbar.addstr(0, 0, "ctrl + c: quit", curses.A_BOLD)
			statusbar.addstr(0, int(x/4), "Museum status:", curses.A_BOLD)
			if museum_cstate == True:
				statusbar.addstr(0, int(x/4+15), "ONLINE", curses.color_pair(3))
			else:
				statusbar.addstr(0, int(x/4+15), "OFFLINE", curses.color_pair(2))
			statusbar.addstr(0, int(x/2), "Server status:", curses.A_BOLD)
			if server_up == True:
				statusbar.addstr(0, int(x/2+15), "ONLINE", curses.color_pair(3))
			else:
				statusbar.addstr(0, int(x/2+15), "OFFLINE", curses.color_pair(2))
			statusbar.addstr(0, x-15, "Lines:", curses.A_BOLD)
			statusbar.addstr(0, x-8, str(len(lines)), curses.A_BOLD)


#-->											<--#
#						THREADS					 #
#-->											<--#

class ui_thread(threading.Thread):
	# The UI thread!
	# Sets up a screen, and calls various things in Screen() to
	# help with drawing.

	def __init__(self):

		threading.Thread.__init__(self)
		self.shutdown_flag = threading.Event()
		self.started = True

	def run(self):

		curses.wrapper(self.ui_main)

	def ui_main(self, stdscr):

		global screen
		global curscreen

		curscreen = 1 

		# Instantiate a screen, so we can play with it later.
		screen = Screen(stdscr)

		while not self.shutdown_flag.is_set():

			curscreen = screen.getkey(stdscr, curscreen)

			# Check if screen has been resized. Handle it.
			y, x = stdscr.getmaxyx()
			resized = curses.is_term_resized(y, x)
			if resized is True:
					y, x = stdscr.getmaxyx()
					screen.update_size(stdscr, y, x)

			# Draw the window
			if curscreen == 1:
				screen.draw(stdscr, lines, y, x)
			else:
				screen.draw2(stdscr, switches, y, x)

			screen.drawstatus(stdscr, lines, y, x)

			stdscr.refresh()
			sleep(0.2)

class work_thread(threading.Thread):

	def __init__(self):

		threading.Thread.__init__(self)
		self.shutdown_flag = threading.Event()

	def run(self):

		global lines
		global switches
		global server_up
		failcount = 0

		while not self.shutdown_flag.is_set():
			self.is_alive = True

			try:
				reqlines = requests.get(APILINES, timeout=.5)
				schema = LineSchema()
				try:
					lines = schema.loads(reqlines.content.decode('UTF-8'), many=True)
				except ValidationError as err:
					print(err.messages)
					print(err.valid_data)

				reqswitches = requests.get(APISWITCH, timeout=.5)
				schema = SwitchSchema()
				try:
					switches = schema.loads(reqswitches.content.decode('UTF-8'), many=True)
				except ValidationError as err:
					print(err.messages)
					print(err.valid_data)
				
				server_up = True
				failcount = 0
				sleep(1)
			except requests.exceptions.RequestException:
				server_up = False
				failcount += 1
				if failcount == 2:
					logger.critical("Connections service not running!")
				sleep(10)
				continue

class museum_thread(threading.Thread):

	def __init__(self):

		threading.Thread.__init__(self)
		self.shutdown_flag = threading.Event()

	def poke(cstate, pstate, failcount, self):

		try:
			r = requests.get(MUSEUMSTATE, timeout=5)
			schema = MuseumSchema()
			result = schema.loads(r.content.decode())
			for k, v in list(result.items()):
				cstate = v
			if pstate != cstate:
				pstate = cstate
				timer = 4
			failcount = 0		 
			return cstate
		except requests.exceptions.RequestException:
			cstate = False
			failcount += 1
			if failcount == 2:
				logger.error("Timeout reached while checking museum status")
			timer = 40
			return cstate

	def run(self):

		global museum_cstate
		global museum_pstate
		failcount = 0
		museum_pstate = False
		museum_cstate = False
		timer = 40

		museum_cstate = self.poke(museum_cstate, museum_pstate, failcount)

		while not self.shutdown_flag.is_set():
			self.is_alive = True
			timer = timer - 1
			sleep(1)
			if timer <= 0:
				museum_cstate = self.poke(museum_cstate, museum_pstate, failcount)

class ServiceExit(Exception):
	pass

def app_shutdown(signum, frame):
	raise ServiceExit


if __name__ == "__main__":

# Set up signal handlers so we can shutdown cleanly later.
	signal.signal(signal.SIGTERM, app_shutdown)
	signal.signal(signal.SIGINT, app_shutdown)

	APILINES = "http://192.168.0.204:5000/api/lines"
	APISWITCH = "http://192.168.0.204:5000/api/switches"
	MUSEUMSTATE = "http://192.168.0.204:5000/api/museum"
	lines = []
	switches = []
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
		t_work = work_thread()
		t_work.daemon = True
		t_work.start()
		t_museum = museum_thread()
		t_museum.daemon = True
		t_museum.start()
		t_ui = ui_thread()
		t_ui.daemon = True
		t_ui.start()

		while True:
			sleep(0.2)

	except (KeyboardInterrupt, ServiceExit):
		# Exception handler for console-based shutdown.

		t_ui.shutdown_flag.set()
		t_ui.join()
		t_work.shutdown_flag.set()
		t_work.join()
		t_museum.shutdown_flag.set()
		t_museum.join()

		print('\n')

	except Exception as e:
		# Exception for any other errors that I'm not explicitly handling.
		print(e)
		t_ui.shutdown_flag.set()
		t_ui.join()
		t_work.shutdown_flag.set()
		t_work.join()
		t_museum.shutdown_flag.set()
		t_museum.join()

		print(("\nOS error {0}".format(e)))

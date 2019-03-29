#!/usr/bin/python

#----------------------------------------------
# HTTP server for panel_gen
# Run with $sudo python http_server.py
#
# Web page created with Skeleton CSS framework
# http://www.getskeleton.com
#
# A note on using Flask: This is insecure. We must only make this
# available from inside of our network, and we probably shouldn't be
# letting visitors on to our private wifi anyway.
#
#-----------------------------------------------

try:
    from cheroot.wsgi import Server as WSGIServer, PathInfoDispatcher
except ImportError:
    from cherrypy.wsgiserver import CherryPyWSGIServer as WSGIServer, WSGIPathInfoDispatcher as PathInfoDispatcher
from flask import Flask, render_template, request
import connexion
import logging
import panel_gen

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = connexion.App(__name__, specification_dir='api/')
app.add_api('swagger.yml')

# This starts the UI. Normally, when we import as
# a module, we don't want to start the UI and take
# over the user's screen unless specifically asked.
#panel_gen.start_ui()

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')

@app.route('/dark', methods=['GET'])
def darkt():
    return render_template('dark.html')

@app.route('/5xb', methods=['GET'])
def xb5home():
    return render_template('5xb.html')

@app.route('/panel', methods=['GET'])
def panelhome():
    return render_template('panel.html')

d = PathInfoDispatcher({'/': app})
server = WSGIServer(('0.0.0.0', 5000), d)

if __name__ == '__main__':
    try:
	server.start()
    except KeyboardInterrupt:
	server.stop()
    finally:
        panel_gen.module_shutdown()

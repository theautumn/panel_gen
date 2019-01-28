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

from flask import Flask, render_template, redirect, request, flash
import connexion
import logging
import panel_gen

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

#app = Flask(__name__)
app = connexion.App(__name__, specification_dir='./')
app.add_api('swagger.yml')

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

if __name__ == '__main__':
    app.run(host='0.0.0.0')

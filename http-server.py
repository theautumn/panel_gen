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
import subprocess
import os
import signal

app = Flask(__name__)

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class RUN_STRING:
    PANEL = 'python /home/sarah/panel_gen/panel_gen.py -a 4  --http'
    XB5 = 'python /home/sarah/panel_gen/panel_gen.py -o 5xb -t 832 -t 232 -t 275 -a 7 -v heavy --http'

@app.route('/5xb', methods=['GET', 'POST'])
def xb5home():
    global p
    if request.method == 'POST':
        command = request.form['command']
        if command == "start":
            print(bcolors.OKGREEN + '>>  Got a START request for 5XB' + bcolors.ENDC)
            p = subprocess.Popen(RUN_STRING.XB5, shell=True, preexec_fn=os.setsid)
            return render_template('5xb.html', status="Running")
        elif command == "stop":
            try:
                print(bcolors.FAIL + '<<  Got a STOP request for 5XB' + bcolors.ENDC)
                os.killpg(os.getpgid(p.pid), signal.SIGALRM)
                p = None
                return render_template('5xb.html', status="Stopped")
            except Exception:
                print(bcolors.WARNING + 'Nothing to terminate. Returning to index page...' + bcolors.ENDC)
                return render_template('5xb.html')

    return render_template('5xb.html')

@app.route('/panel', methods=['GET', 'POST'])
def panelhome():
    global p
    if request.method == 'POST':
        command = request.form['command']
        if command == "start":
            print(bcolors.OKGREEN + '>>  Got a START request for PANEL' + bcolors.ENDC)
            p = subprocess.Popen(RUN_STRING.PANEL, shell=True, preexec_fn=os.setsid)
            return render_template('panel.html', status="Running")
        elif command == "stop":
            try:
                print(bcolors.FAIL + '<<  Got a STOP request for PANEL' + bcolors.ENDC)
                os.killpg(os.getpgid(p.pid), signal.SIGALRM)
                p = None
                return render_template('panel.html', status="Stopped")
            except Exception:
                print(bcolors.WARNING + 'Nothing to terminate. Returning to index page...' + bcolors.ENDC)
                return render_template('panel.html')

    return render_template('panel.html')

app.run(host='0.0.0.0')


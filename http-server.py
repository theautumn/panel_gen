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
import connexion
import logging

#log = logging.getLogger('werkzeug')
#log.setLevel(logging.ERROR)


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

class RUN_STRING:
    PANEL = 'python /home/sarah/panel_gen/panel_gen.py -a 4  --http'
    XB5 = 'python /home/sarah/panel_gen/panel_gen.py -o 5xb -a 8 -v heavy --http'

class PROCESS:
    PANEL = "panel_gen.py -a 4"
    XB5 = "panel_gen.py -o 5xb"

@app.route('/', methods=['GET', 'POST'])
def home():
    global p, q

    if request.method == 'POST':
        command = request.form['command']
        if command == "Panel Start":
            tmp = os.popen("ps -Af").read()
            if PROCESS.PANEL not in tmp[:]:
                print(bcolors.OKGREEN + '>>  Got a START request for PANEL' + bcolors.ENDC)
                p = subprocess.Popen(RUN_STRING.PANEL, shell=True, preexec_fn=os.setsid)
                return render_template('home.html')
            else:
                print(bcolors.HEADER + "Process already running. Cant start twice!" + bcolors.ENDC)

        elif command == "Panel Stop":
            try:
                print(bcolors.FAIL + '<<  Got a STOP request for PANEL' + bcolors.ENDC)
                os.killpg(os.getpgid(p.pid), signal.SIGALRM)
                p = None
                return render_template('home.html')
            except Exception:
                print(bcolors.WARNING + 'Nothing to terminate. Returning to index page...' + bcolors.ENDC)
                return render_template('home.html')

        elif command == "5XB Start":
            tmp2 = os.popen("ps -Af").read()
            if PROCESS.XB5 not in tmp2[:]:
                print(bcolors.OKGREEN + '>>  Got a START request for 5XB' + bcolors.ENDC)
                q = subprocess.Popen(RUN_STRING.XB5, shell=True, preexec_fn=os.setsid)
                return render_template('home.html')
            else:
                print(bcolors.HEADER + "Process already running. Cant start twice!" + bcolors.ENDC)
        elif command == "5XB Stop":
            try:
                print(bcolors.FAIL + '<<  Got a STOP request for 5XB' + bcolors.ENDC)
                os.killpg(os.getpgid(q.pid), signal.SIGALRM)
                q = None
                return render_template('home.html')
            except Exception:
                print(bcolors.WARNING + 'Nothing to terminate. Returning to index page...' + bcolors.ENDC)
                return render_template('home.html')
        elif command == "Force Stop":
            try:
                print(bcolors.FAIL + '<<  Got a FORCE STOP request! >>' + bcolors.ENDC)
                n = subprocess.Popen(['ps', '-ax'], stdout=subprocess.PIPE)
                out, err = n.communicate()

                for line in out.splitlines():
                    if 'panel_gen.py' in line:
                        pid = int(line.split(None, 1)[0])
                        os.kill(pid, signal.SIGALRM)
                p, q = None
                return render_template('home.html')
            except Exception as e:
                return render_template('home.html')

    return render_template('home.html')

@app.route('/5xb', methods=['GET', 'POST'])
def xb5home():
    global q
    
    if request.method == 'POST':
        command = request.form['command']
        if command == "start":
            tmp2 = os.popen("ps -Af").read()
            if PROCESS.XB5 not in tmp2[:]:
                print(bcolors.OKGREEN + '>>  Got a START request for 5XB' + bcolors.ENDC)
                q = subprocess.Popen(RUN_STRING.XB5, shell=True, preexec_fn=os.setsid)
                return render_template('5xb.html')
            else:
                print(bcolors.HEADER + "Process already running. Cant start twice!" + bcolors.ENDC)

        elif command == "stop":
            try:
                print(bcolors.FAIL + '<<  Got a STOP request for 5XB' + bcolors.ENDC)
                os.killpg(os.getpgid(q.pid), signal.SIGALRM)
                q = None
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
            tmp = os.popen("ps -Af").read()
            if PROCESS.PANEL not in tmp[:]:
                print(bcolors.OKGREEN + '>>  Got a START request for PANEL' + bcolors.ENDC)
                p = subprocess.Popen(RUN_STRING.PANEL, shell=True, preexec_fn=os.setsid)
                return render_template('panel.html')
            else:
                print(bcolors.HEADER + "Process already running. Cant start twice!" + bcolors.ENDC)
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

#if __name__ == '__main__':
app.run(host='0.0.0.0')


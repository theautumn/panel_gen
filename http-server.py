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

@app.route('/', methods=['GET', 'POST'])
def landing():
    global p
    if request.method == 'POST':
        command = request.form['command']
        if command == "start":
            print(bcolors.OKGREEN + '>>  Got a START request' + bcolors.ENDC)
            p = subprocess.Popen('python /home/sarah/panel_gen/panel_gen.py -o 5xb -t 832 -t 232 -t 275 -a 7 -v heavy --http', shell=True, preexec_fn=os.setsid)
            return render_template('running.html')
        elif command == "stop":
            try:
                print(bcolors.FAIL + '<<  Got a STOP request.' + bcolors.ENDC)
                os.killpg(os.getpgid(p.pid), signal.SIGALRM)  # Send the signal to all the process groups
                p = None
                return render_template('stopped.html')
            except Exception:
                print(bcolors.WARNING + 'Nothing to terminate. Returning to index page...' + bcolors.ENDC)
                return render_template('index.html')
    return render_template('index.html')

app.run(host='0.0.0.0')


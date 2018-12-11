from flask import Flask, render_template, redirect, request, flash
import subprocess
import os
import signal

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def landing():
    global p
    if request.method == 'POST':
        command = request.form['command']
        if command == "start":
            print('>>  Got a START request')
            p = subprocess.Popen('python /home/sarah/panel_gen/panel_gen.py -o 5xb -a 8 -v heavy --http', shell=True, preexec_fn=os.setsid)
            return render_template('running.html')
        elif command == "stop":
            print('<<  Got a STOP request.')
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)  # Send the signal to all the process groups
                return render_template('stopped.html')
            except (OSError, NameError):
                print('nothing to terminate. returning to index page')
                return render_template('index.html')
    return render_template('index.html')

app.run(host='0.0.0.0')


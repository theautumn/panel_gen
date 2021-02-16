#!/usr/bin/python

#----------------------------------------------
# HTTP server for panel_gen
# Run with $sudo python http_server.py
#
# Web page created with Skeleton CSS framework
# http://www.getskeleton.com
#
# This is insecure. We must only make this
# available from inside of our network, and we probably shouldn't be
# letting visitors on to our private wifi anyway.
#
#-----------------------------------------------

from cheroot.wsgi import Server as WSGIServer, PathInfoDispatcher
from flask import render_template 
import connexion
import logging
import panel_gen


app = connexion.App(__name__, specification_dir='api/')
app.add_api('swagger.yml')

# This starts the UI. Normally, when we import as
# a module, we don't want to start the UI and take
# over the user's screen unless specifically asked.
#panel_gen.start_ui()

@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')

d = PathInfoDispatcher({'/': app})
server = WSGIServer(('0.0.0.0', 5000), d)

if __name__ == '__main__':
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
    finally:
        panel_gen.api_stop(switch="all", source="module")

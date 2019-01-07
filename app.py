from flask import make_response, abort
import panel_gen

# Handler for /app GET
def read_status():
    return "App Status Message"

def operate():
   	return "App OPERATE"

def nonoperate():
    return "App NONOPERATE"

def api_pause():
    return "PAUSED"

def api_resume():
    return "RESUMED"

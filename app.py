from flask import make_response, abort
import panel_gen

# Handler for /app GET
def read_status():
    return "App Status Message"

def operate():
    panel_gen.operate()    
    return "App OPERATE"

def nonoperate():
    panel_gen.nonoperate()
    return "App NONOPERATE"

def api_pause():
    panel_gen.api_pause()
    return "PAUSED"

def api_resume():
    panel_gen.api_resume()
    return "RESUMED"

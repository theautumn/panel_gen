from flask import make_response, abort
import panel_gen

# Handler for /app GET
def read_status():
   result = panel_gen.get_info() 
   if result != False:
       return result
   else:
       abort(
            406,
            "Failed to get info",
        )

def start(**kwargs):
    switch = kwargs.get("switch", "")
    result = panel_gen.operate(switch)    
    if result != False:
        return result
    else:
        abort(
            406,
            "panel_gen is already running",
        )

def stop():
    panel_gen.stop()
    return "App Stop"

def api_pause():
    panel_gen.api_pause()
    return "PAUSED"

def api_resume():
    panel_gen.api_resume()
    return "RESUMED"

def call(**kwargs):
    switch = kwargs.get("switch", "")
    destination = kwargs.get("destination", "")
    result = panel_gen.call_now(switch, destination)
    if result != False:
        return result
    else:
        abort(
            406,
            "Call failed for some reason. This message is very unhelpful",
        )

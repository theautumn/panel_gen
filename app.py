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
    mode = kwargs.get("mode", "")
    source = kwargs.get("source", "")

    if mode == "demo":
        result = panel_gen.api_start(switch, mode="demo")

        if source == "web":
            return 'See Other', 303, {'Location': '/'}
        else:
            return result 
    
    elif mode != "demo":
        result = panel_gen.api_start(switch)    

    else:
        abort(
            406,
            "Failed to create switch. May already be running.",
        )

def stop(**kwargs):
    switch = kwargs.get("switch", "")
    source = kwargs.get("source", "")
    
    result = panel_gen.api_stop(switch)

    if result != False:
        if source == "web":
            return 'See Other', 303, {'Location': '/'}
        else:
            return result 
    else:
        if source == "web":
            return 'See Other', 303, {'Location': '/'}
        else:
            abort(
                406,
                "Failed to stop switch. Ask Sarah to fix this.",
            )

def pause():
    result = panel_gen.api_pause()
    if result != False:
        return result
    else:
        abort(
            406,
            "Failed to pause app. May already be paused.",
        )


def resume():
    result = panel_gen.api_resume()
    if result != False:
        return result
    else:
        abort(
            406,
            "Failed to resume app. May already be running.",
        )

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

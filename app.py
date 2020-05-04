from flask import make_response, abort
import panel_gen

# Handler for /app GET
def read_status():
    """
    GET /app/
    Success:    Returns 200 OK + app status messages
    Failure:    Returns 406 Failed to get info
    """
    result = panel_gen.get_info() 
    if result != False:
       return result
    else:
       abort(
            406,
            "Failed to get info. Probably an issue with panel_gen",
        )

def start(**kwargs):
    """
    POST /app/start/{switch}
    Success:    Returns 200 OK + Starts calls on {switch}.
                Also returns JSON formatted switch status message.
    Failure:    Returns 406
    If launched from web browser at http://0.0.0.0:5000, returns 303
    redirect back to same page with no status message. This is so the
    smartphone browser app will refresh the same page. It's an ugly hack
    but it works.

    **kwargs allow the POST to be parsed for specifics
    switch:     In URI path, Can be "1xb", "5xb", "panel", "all"
    source:     In URI query string. "web", "key"
    """
    switch = kwargs.get("switch", "")
    source = kwargs.get("source", "")
    traffic_load = kwargs.get("traffic_load", "")

    try:
        result = panel_gen.api_start(**kwargs)

        if source == "web":
            return 'See Other', 303, {'Location': '/'}
        else:
            return result 

    except Exception as e:
        abort(
            406,
            "Failed to create new lines. Check api_start()"
        )

def stop(**kwargs):
    """
    POST /app/stop/{switch}
    Success:    Returns 200 OK + Stops calls on {switch}.
    Failure:    Returns 406
    If launched from web browser at http://0.0.0.0:5000, returns 303
    redirect back to same page with no status message.

    **kwargs allow the POST to be parsed for specifics
    switch:     In URI path. Can be "1xb", "5xb", "panel"
    source:     In URI query string. Can be "web", "key".
    """
    source = kwargs.get("source", "")
    
    try:    
        result = panel_gen.api_stop(**kwargs)

        if result != False:
            if source == "web":
                return 'See Other', 303, {'Location': '/'}
            else:
                return result 
        elif result == False:
            abort(
                406,
                "Failed to stop switch. Ask Sarah to fix this.",
            )
    except:
        abort(406, "Shits all fucked up",)
        pass

def call(**kwargs):
    """
    POST /app/call/{switch}
    Places a single call on {switch} that lasts for 18 seconds,
    then hangs up and deletes the line from the switch.
    Success:    Returns 200 OK + JSON parseable switch status.
    Failure:    Returns 406 + Unhelpful error message.

    **kwargs allow the POST to be parsed for specifics
    switch:         In URI path. Can be "1xb", "5xb", "panel".
    destination:    In URI path. Called line.
    timer:          In URI path. Number of seconds for call to be up.

    """
    result = panel_gen.call_now(**kwargs)
    if result != False:
        return result
    else:
        abort(
            406,
            "Call failed for some reason. This message is very unhelpful",
        )

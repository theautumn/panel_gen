from datetime import datetime

def get_timestamp():
    return datetime.now().strftime(("%Y-%m-%d %H:%M:%S"))

# Data to serve with our API
PANEL = {
    "panel": {
        "running": True,
        "active_lines": 4,
        "is_dialing": False,
        "dahdi_group": "r6",
        "nxx": {722, 365, 232},
        "linerange": {5000,5999},
        "timestamp": get_timestamp()
    }
}

# Create a handler for our read (GET) people
def read():
    """
    This function responds to a request for /api/people
    with the complete lists of people

    :return:        sorted list of people
    """
    # Create the list of people from our data
    return [PANEL[key] for key in sorted(PANEL.keys())]

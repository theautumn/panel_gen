from datetime import datetime

def get_timestamp():
    return datetime.now().strftime(("%Y-%m-%d %H:%M:%S"))

# Data to serve with our API
SWITCHES = {
    "Panel": {
        "kind": "Panel",
	"running": True,
        "active_lines": 4,
	"max_dialing": 6,
        "is_dialing": False,
        "dahdi_group": "r6",
        "nxx": "722, 365, 232",
        "linerange": "5000, 5999",
    }

    "5XB": {
        "kind": "5XB",
	"running": True,
        "active_lines": 8,
	"max_dialing": 7,
        "is_dialing": False,
        "dahdi_group": "r11",
        "nxx": "722, 832, 232",
        "linerange": "5000, 5999",
    }
}

# Create a handler for our read (GET) people
def read():
    """
    This function responds to a request for /api/switch
    with the complete lists of switches

    :return:        sorted list of switches
    """
    # Create the list of people from our data
    return [SWITCHES[key] for key in sorted(SWITCHES.keys())]

def create(switch):
    """
    This function creates a new person in the people structure
    based on the passed in person data
    :param person:  person to create in people structure
    :return:        201 on success, 406 on person exists
    """
    kind = switch.get("kind", None)
    running = switch.get("running", None)
    active_lines = switch.get("active_lines", None)
    max_dialing = switch.get("max_dialing", None)
    is_dialing = switch.get("is_dialing", None)
    dahdi_group = switch.get("dahdi_group", None)
    nxx = switch.get("nxx", None)
    linerange = switch.get("linerange", None)

    # Does the person exist already?
    if kind not in SWITCH and kind is not None:
        SWITCH[kind] = {
            "kind": kind,
            "running": running,
            "active_lines": active_lines,
            "max_dialing": max_dialing,
            "is_dialing": is_dialing,
            "dahdi_group": dahdi_group,
            "nxx": nxx,
            "linerange": linerange,
        }
        return make_response(
            "{kind} successfully created".format(kind=kind), 201
        )

    # Otherwise, they exist, that's an error
    else:
        abort(
            406,
            "Peron with last name {lname} already exists".format(lname=lname),
        )


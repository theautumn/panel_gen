from flask import make_response, abort
import panel_gen

# Data to serve with our API
SWITCHES = {
    "panel": {
        "kind": "panel",
	"running": True,
        "active_lines": 4,
	"max_dialing": 6,
        "is_dialing": 0,
        "dahdi_group": "r6",
        "nxx": "722, 365, 232",
        "linerange": "5000, 5999",
    },

    "5xb": {
        "kind": "5xb",
	"running": True,
        "active_lines": 8,
	"max_dialing": 7,
        "is_dialing": 0,
        "dahdi_group": "r11",
        "nxx": "722, 832, 232",
        "linerange": "5000, 5999",
    },
}

# Create a handler for our read (GET) switch
def read_all():
    """
    This function responds to a request for /api/switch
    with the complete lists of switches

    :return:        sorted list of switches
    """
    # Create the list of switches rom our data
    return [SWITCHES[key] for key in sorted(SWITCHES.keys())]

def read_one(kind):
    """
    This function responds to a request for /api/switch/{kind}
    with one matching switch from switches
    :param kind:   kind of switch to find
    :return:        switch matching kind
    """

    return panel_gen.get_switch(kind)

# Doese the switch exist in switches?
#    if kind in SWITCHES:
#        switch = SWITCHES.get(kind)

    # otherwise, nope, not found
#    else:
#        abort(
#            404, "Switch of type {kind} not found".format(kind=kind)
#        )

def create(kind):
    """
    This function creates a new switch in the switches structure
    based on the passed in switch data
    :param switch:  person to create in switches structure
    :return:        201 on success, 406 on switch exists
    """
#    kind = switch.get("kind", None)

    result = panel_gen.create_switch(kind)
    if result == True:
        return make_response("{kind} successfully created".format(kind=kind), 201)
    else:
        abort(406,"Switch of kind {kind} was not created".format(kind=kind),)

def update(kind):
    """
    This function updates an existing switch in the switches structure
    :param kind:   kind of switch to update in the switches structure
    :return:        updated switch structure
    """
    # Does the switch exist in switches?
    if kind in SWITCHES:
        SWITCHES[kind]["kind"] = SWITCHES.get("kind")

        return SWITCHES[kind]

    # otherwise, nope, that's an error
    else:
        abort(
            404, "Switch {kind} not found".format(kind=kind)
        )


def delete(kind):
    """
    This function deletes a switch from the switches structure
    :param kind:   last name of switch to delete
    :return:        200 on successful delete, 404 if not found
    """
    # Does the switch to delete exist?
    if kind in SWITCHES:
        del SWITCHES[kind]
        return make_response(
            "{kind} successfully deleted".format(kind=kind), 200
        )

    # Otherwise, nope, switch to delete not found
    else:
        abort(
            404, "Switch {kind} not found".format(kind=kind)
        )

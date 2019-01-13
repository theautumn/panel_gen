from flask import make_response, abort
import panel_gen

# Demo lines for testing only. Delete me.
LINES = {
    "1": {
        "switch": "panel",
	"timer": 32,
        "hook_state": 0,
	"ast_state": "on_hook",
        "is_dialing": False,
        "dahdi_chan": "r6",
        "calling_no": "722-5678",
    },

    "2": {
        "switch": "5xb",
	"timer": 13,
        "hook_state": 1,
	"ast_state": "Ringing",
        "is_dialing": False,
        "dahdi_chan": "r11",
        "calling_no": "232-0013",
   },
}

# Create a handler for our read (GET) line
def read_all():
    """
    This function responds to a request for /api/line
    with the complete lists of lines

    :return:        sorted list of lines
    """
    # Create the list of linees rom our data
    return panel_gen.get_all_lines() 

def read_one(ident):
    """
    This function responds to a request for /api/line/{key}
    with one matching line from linees
    :param key:   key of line to find
    :return:        line matching key
    """
    line = panel_gen.get_line(ident)
    if line != False:
        return line
    else:
        abort(
            404, "Line number {ident} does not exist".format(ident=ident)
        )


def create(switch):
    """
    This function creates a new line in the linees structure
    based on the passed in line data
    :param line:  line to create in lines structure
    :return:        201 on success, 406 on line exists
    """

    line_ident = panel_gen.create_line(switch)
    if line_ident != False:
        return make_response(
            "New line index {line_ident} successfully created".format(line_ident=line_ident), 201
        )

    # Otherwise, they exist, that's an error
    else:
        abort(
            406,
            "Line could not be created",
        )

def update(ident):
    """
    This function updates an existing line in the lines structure
    :param key:   key of line to update in the lines structure
    :return:      updated line structure
    """
    # Does the line exist in linees?
    if key in LINES:
        LINES[ident]["ident"] = LINES.get("ident")

        return LINES[ident]

    # otherwise, nope, that's an error
    else:
        abort(
            404, "Line {ident} not found".format(ident=ident)
        )


def delete(ident):
    """
    This function deletes a line from the linees structure
    :param key:   key of line to delete
    :return:      200 on successful delete, 404 if not found
    """
    # Does the line to delete exist?
    line = panel_gen.delete_line(ident)
    if line != False:
        return make_response(
            "Line {ident} successfully deleted".format(ident=ident), 200
        )

    # Otherwise, nope, line to delete not found
    else:
        abort(
            404, "Line {ident} not found".format(ident=ident)
        )

from flask import make_response, abort
import panel_gen

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
    :return:        line matching ident
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

def delete(ident):
    """
    This function deletes a line from the lines structure
    :param key:   key of line to delete
    :return:      200 on successful delete, 404 if not found
    """
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

def delete_all():
    """
    This function deletes all lines
    :return:    200 on success, 406 if delete fails
    """
    result = panel_gen.delete_all_lines()
    if result != False:
        return make_response(
            "All lines successfully deleted.", 200
        )
    else:
        abort(
            406, "Failed to delete lines."
        )

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

def update(**kwargs):
    """
    This function updates an existing line in the lines structure
    :param key:   key of line to update in the lines structure
    :return:      updated line structure
    """
    result = panel_gen.update_line(**kwargs)

    if result != False:
        return result
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

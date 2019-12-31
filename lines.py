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


def create(switch, numlines):
    """
    This function creates a new line in the linees structure
    based on the passed in line data
    :param line:  line to create in lines structure
    :return:        201 on success, 406 on line exists
    """

    line_ident = panel_gen.create_line(switch=switch, numlines=numlines)
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

def delete(switch, numlines):
    """
    This function deletes a line from the lines structure
    switch:     switch to delete lines from
    numlines:   number of lines to delete
    :return:    200 on successful delete, 404 if not found
    """
    line = panel_gen.delete_line(switch, numlines)
    if line != False:
        return make_response(
            "{numlines} successfully deleted".format(numlines=numlines), 200
        )

    # Otherwise, nope, line to delete not found
    else:
        abort(
            404, "Failed to delete {numlines} lines".format(numlines=numlines)
        )

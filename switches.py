from flask import make_response, abort
import panel_gen

# Create a handler for our read (GET) switch
def read_all():
    """
    This function responds to a request for /api/switch
    with the complete lists of switches

    :return:        sorted list of switches
    """
    result = panel_gen.get_all_switches()
    
    if result == False:
        abort(404, "No switches found tho")
    else:
        return result

def read_one(kind):
    """
    This function responds to a request for /api/switch/{kind}
    with one matching switch from switches
    :param kind:   kind of switch to find
    :return:        switch matching kind
    """

    result = panel_gen.get_switch(kind)

    if result == False:
        abort(404, "Switch of type {kind} not found".format(kind=kind))
    else:
        return result

def create(kind):
    """
    This function creates a new switch in the switches structure
    based on the passed in switch data
    :param switch:  switch to create in switches structure
    :return:        201 on success, 406 on switch exists
    """

    result = panel_gen.create_switch(kind)

    if result != False:
        return make_response("{kind} successfully created".format(kind=kind), 201)
    else:
        abort(406,"Switch of kind {kind} was not created".format(kind=kind),)

def update(**kwargs):
#    """
#    This function updates an existing switch in the switches structure
#    :param kind:   kind of switch to update in the switches structure
#    :return:        updated switch structure
#    """
    result = panel_gen.update_switch(**kwargs)

    if result != False:
        return result
    else:
        abort(406, "Sarah broke something.")


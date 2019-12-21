from flask import abort
import os
import subprocess

ENDPOINT='192.168.0.221'
FNULL= open(os.devnull,'w')

def read_status():
    """
    GET /museum/
    Success:    Returns 200 OK + battery status boolean
    Failure:    Returns 406 Failed to get info
    """
    try:
        ping = subprocess.call(['ping', '-c', '4', ENDPOINT], stdout=FNULL, stderr=subprocess.STDOUT)
    except Exception as e:
        pass

    if ping == 0:
        status = True
    elif ping != 0:
        status = False
    else:
       abort(406, "Failed to return ping result", )
    
    result = {"status" : status }

    return result

# panel_gen 
Auto call generator for the telephone switches at Connections Museum, Seattle.

Connections Museum has in its collection the last remaining Panel-type telephone switch in the world. The switch functions, but mostly sits idle all day, since there is very little human-generated traffic to keep it busy. This program is my attempt to create a small load on the panel switch (and others at the museum) during idle time, so it appears to be processing calls from subscribers.
![screenshot of panel_gen](samples/panel_gen.png "panel_gen main window")

Requirements
------------
This project assumes you have the following:
* a computer running >= Asterisk 11
* a channel bank of some sort containing FXO cards wired to the originating
side of your switches
* a way to communicate with the channel bank
* the required python modules installed (see requirements.txt)

The DAHDI configs are part of this repo in the <code>samples/etc</code> directory, and the Adit configs are part of this repository also. Please note that your hardware and software may vary from what I used, but the configs should be a good starting place nonetheless.

This program must be run as a user who is able to write to the following directories:
<code>/var/spool/asterisk</code> and <code>/var/log/panel_gen</code>.
It also requires the ability to run <code>asterisk</code> and <code>tail</code>.
<br />


Setup
-----
Since I wrote this with the specific intention of it being used at our museum, there isn't an easy setup guide or anything to follow. Our setup is static, and once it works, it works. Therefore, much of the initial config is an exercise left to the reader.

We have a PC with a Sangoma A104 T1 card installed. Asterisk is installed along with DAHDI and libpri. You can find a reasonable primer on this here: http://www.asteriskdocs.org/en/3rd_Edition/asterisk-book-html-chunk/installing_how_to_install_it.html

The T1 card connects to an Adit 600 channel bank near the Panel switch. The Adit is configured with a bunch of FXO cards. Each card supports 8 lines, so 3 cards supports a total of 24. These exit the Adit on a 25-pair cable and terminate on the IDF in the Panel switch. From the distributing frame, they are cabled to the Line Finder frame on the Panel, and the Line Link Frames on the Crossbar switches just like regular subscriber lines. (Please note that there has been some talk of the fact that hooking up a modern channel bank to an electromechanical switch can, over time, damage the delicate circuitry in the FXO cards. You may want to add some transient voltage protection. I find [these](https://www.mouser.com/ProductDetail/on-semiconductor/p6ke68a/?qs=nEYkbyTNQ5k4oguMQnTOuQ%3d%3d&countrycode=US&currencycode=USD) work very well. If you have questions, ask around on the C\*NET list @ http://www.ckts.info

Currently, <code>panel_gen</code> uses [pycall](https://github.com/rdegges/pycall) to put a .call file in the Asterisk spool directory. Asterisk monitors the spool directory, and when it sees a file there, it starts a call using the parameters in the file. It then either deletes the .call file, or moves it to another directory (depending on your configuration). We then track the call using [python-ami](https://github.com/ettoreleandrotognoli/python-ami) to grab AMI events. 

This application requires a context in your dialplan to pass calls into. The simple context I use is below.

```
[sarah_callsim]
exten => _X!,1,NoOp("Called: ${EXTEN} on ${CHANNEL}")
  same => n,Answer()
  same => n,Wait(${waittime})
  same => n,Hangup()
```

A primary goal of this program is to be smart about what it can call on each switch. Most of these configuration elements are contained in panel_gen.conf. You must edit and copy panel_gen.conf from ./samples/configs and into /etc/. If you forget to do this, panel_gen/ConfigParser will give you a mean error. 

Usage
-----
There are two ways to run panel_gen:
* as a standalone application (<code>panel_gen.py</code>)
* as a systemd service (which runs <code>http_server.py</code>)

Running the program as a standalone application will give you a nice curses UI, and accepts command line arguments. ( <code>panel_gen.py -h</code> for help). The standalone application does not run the HTTP server, so all control must be done through passing arguments in to it. Once the program is running, it will automatically begin processing calls until it is stopped with ctrl+c.

There are several different arguments you can use when running the program. Where arguments are not given by the user at runtime, defaults are assumed.

* ````python panel_gen.py```` Originates calls from the panel switch in random order.
* ````python panel_gen.py -o 5xb```` Originates calls from the No. 5 Crossbar in random order.
* ````python panel_gen.py -o 5xb -a 10```` Originates calls from the No. 5 Crossbar in random order. Maximum of 10 active lines.
* ````python panel_gen.py -o 5xb -t 1xb -a 2```` Originates calls from the No. 5 Crossbar to No. 1 Crossbar. Maximum of 2 active lines.

Running as a systemd service requires using the .service file in the "service/" directory. This method will cause the application to run like any other system service, and includes an HTTP/API server with all of the extra bells and whistles. This is how we normally run it at the museum. While running as a systemd service, you can connect to it with `console.py` to get a curses UI. Exiting `console.py` will have no effect on the service itself. If you want to go this route, you'll need to do the legwork to configure the service for your machine, as I've only tested this on mine. More info on the HTTP server is in the section below this.

The interface is divided into three areas, which should be mostly self-explanatory. The only bit that warrants some explanation is the main table at the top:

````
      __________________________________________
     |                                          |
     |  Rainier Full Mechanical Call Simulator  |
     |__________________________________________|


|   switch |   channel |    term |   tick |   state |   asterisk |
|---------:|----------:|--------:|-------:|--------:|-----------:|
|    panel |         1 | 7225720 |     34 |       1 |    Dialing |
|    panel |         - | 2325773 |      4 |       0 |    on_hook |
|    panel |        10 | 7225337 |    120 |       1 |    Ringing |

````
* **switch**: originating switch
* **channel**: DAHDI channel
* **term**: line being called
* **tick**: seconds before next event occurs
* **state**: line state according to Python
* **asterisk**: line state according to Asterisk

While running as a standalone application, there are a few magic keys you can use to control program flow. These have no effect when running as a system service, as all control should be done through the API.
* **spacebar**: pause/resume
* **u/d**: add/remove lines
* **ctrl + c**: hang up all lines and quit

HTTP Server
-----------
There is a simple, insecure HTTP server provided in `http-server.py` which serves up a basic web page so panel_gen can be controlled via a volunteer's smartphone. This should not be available to everybody, as there are no security or sanity checks, and there's probably a thousand ways to break it. I keep it limited to a secure network so only those with the WPA key can access it. The smartphone interface pretends to be an app, but its really just a browser with a web page. It looks something like this:
<p align="center">
  <img src="samples/IMG_0588.png">
</p>

The web server also provides an API can be used to control the behavior of panel_gen externally, either using the aforementioned smartphone, or a key and lamp. You can poke the API with Postman, or with http://127.0.0.1/api/ui. We mostly use it to start and stop the demo during tours with a key and lamp discreetly mounted in our switches. See https://github.com/theautumn/tinyrobot for the code for that.


Caveats
-------
This program is designed to control a 100 year old, motor-driven analog switch. The fact that it has so many moving parts means that what looks good on paper is not always the way it behaves in real life. This is especially true when it comes to timing and control. Asterisk has no way of knowing what the switch is doing, outside of the normal subscriber supervision (on hook/off hook). The switch may return various call progress tones back to the caller, but there is currently no easy way for those tones to be recognized and acted upon. Because of this, I've tried to make sanity a priority, so the program should rarely--if ever--do things that the switches can't handle. I've also taken steps to make sure that the program won't "desync" from what Asterisk and the electromechanical switches are actually doing in real life. This element is a constant work in progress, as I discover more and more subtle bugs.


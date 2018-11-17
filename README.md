# panel_gen 
Auto call generator for the Panel switch at Connections Museum, Seattle.

Connections Museum, Seattle has in its collection the last remaining Panel-type telephone switch in the world. The switch functions, but mostly sits idle all day, since there is very little human-generated traffic to keep it busy. This program is my attempt to create a small load on the panel switch--and others at the museum--during idle time, so it appears to be processing calls from subscribers.
![screenshot of panel_gen](samples/panel_gen.png "panel_gen main window")

Requirements
------------
This project assumes you have the following:
* a computer running Asterisk (this has been tested on 11 and 13)
* a T1 card with DAHDI and libpri installed
* a channel bank of some sort containing FXO cards
* the required python modules installed:
	* tabulate
	* subprocess
	* numpy
	* pathlib
	* argparse
	* pycall
	* logging
	* curses
	* asterisk.ami

The Panel switch requires the FXO cards in the channel bank to be configured with fxs_ls signalling. The DAHDI configs are part of this repo in the <code>etc</code> directory, and the Adit configs are part of this repository also. Please note that your hardware and software may vary from what I used, but the configs should be a good starting place nonetheless.

This program must be run as user 'root', or at least be able to write to the following directories:
<code>/var/spool/asterisk</code> and <code>/var/log/panel_gen</code>. It also requires the ability to run <code>asterisk</code> and <code>tail</code>.<br />


Setup
-----
We have a PC with two TE110P T1 cards installed. One is for the museum's C\*NET connection, and the other is used specifically for this project. Astrisk is installed along with DAHDI and libpri. You can find a reasonable primer on this here: http://www.asteriskdocs.org/en/3rd_Edition/asterisk-book-html-chunk/installing_how_to_install_it.html

The T1 card connects to an Adit 600 channel bank near the Panel switch. The Adit is configured with a bunch of cards, but the important ones for us are the FXO cards in slots 4, 5, and 6. Each card supports 8 lines, so 3 cards supports a total of 24. These exit the Adit on a 25-pair cable and terminate on the IDF in the Panel switch. From the distributing frame, they are cabled to the Line Finder frame on the Panel, and the Line Link Frames on the Crossbar switches just like regular subscriber lines. (Please note that there has been some talk of the fact that hooking up a modern channel bank to an electromechanical switch can, over time, damage the delicate circuitry in the FXO cards. You may want to add some transient voltage protection. I find [these](https://www.mouser.com/ProductDetail/on-semiconductor/p6ke68a/?qs=nEYkbyTNQ5k4oguMQnTOuQ%3d%3d&countrycode=US&currencycode=USD) work very well. If you have questions, ask around on the C\*NET list @ http://www.ckts.info

Currently, <code>panel_gen</code> uses [pycall](https://github.com/rdegges/pycall) to put a .call file in the Asterisk spool directory. Asterisk monitors the spool directory, and when it sees a file there, it starts a call using the parameters in the file. It then either deletes the .call file, or moves it to another directory (depending on your configuration). This program also uses [python-ami](https://github.com/ettoreleandrotognoli/python-ami) to grab AMI events. I suspect that over time, the AMI will be used more and more, and pycall will be used less. 

This application requires a context in your dialplan to pass calls into. The simple context I use is below.

```
[sarah_callsim]

	exten => s,1,Wait(${waittime})
        exten => s,n,Hangup()
```

Usage
-----
Setting up Asterisk and a channel bank is way beyond the scope of this readme so lets assume you've somehow managed to do that without losing all your marbles. It should be possible to grab the code, install the libraries, and run just <code>python panel_gen.py</code> as root, and have everything work out fine, (although you will have to edit the DAHDI group, and switch classes to suit your needs). There are command line arguments that have been mostly tested to work, but I can't make any guarantees that they won't blow something up in the process. Run <code>python panel_gen.py --help</code> to see them. I'll paste them here as well:

```
usage: panel_gen.py [-h] [-a lines] [-d] [-l line] [-o [switch]] [-t switch]
                    [-v volume]

Generate calls to electromechanical switches. Defaults to originate a sane
amount of calls from the panel switch if no args are given.

optional arguments:
  -h, --help   show this help message and exit
  -a lines     Maximum number of active lines.
  -d           Deterministic mode. Eliminate timing randomness so various
               functions of the switch can be tested at-will. Will ignore -a
               and -v options entirely.
  -l line      Call only a particular line. Can be used with the -d option for
               placing test calls to a number over and over again.
  -o [switch]  Originate calls from a particular switch. Takes either 3 digit
               NXX values or switch name. 1xb, 5xb, panel, or all. Default is
               panel.
  -t switch    Terminate calls only on a particular switch. Takes either 3
               digit NXX values or switch name. Defaults to options for
               whichever switch you are originating from.
  -v volume    Call volume is a proprietary blend of frequency and randomness.
               Can be light, normal, or heavy. Default is normal, which is
               good for average load.
  -w seconds   Use with -d option to specify wait time between calls.
  -z seconds   Use with -d option to specify call duration.
```

The program is capable of generating calls from, and terminating calls to, any of the switches in the museum. The switch classes determines what the rules for each switch are, and they're set up with the switch capacities and limitations baked in. This way, if you are originating or terminating on any switch, panel_gen is intelligent enough to know if it's possible to make the call it's about to make.

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

Examples
-------
I've created a bash alias to make this easier to run, but the following examples assume you've not done that. If you'd like to create one, you can edit ~/.bashrc, and add <code>alias panel_gen='sudo -u asterisk python ~/panel_gen/panel_gen.py'</code> to the end of the file. Change the directory where panel_gen lives, as necessary.

There are several different arguments you can use when running the program. Where arguments are not given by the user at runtime, defaults are assumed.

* ````python panel_gen.py```` Originates calls from the panel switch in random order.
* ````python panel_gen.py -o 5xb```` Originates calls from the No. 5 Crossbar in random order.
* ````python panel_gen.py -o 5xb -a 10```` Originates calls from the No. 5 Crossbar in random order. Maximum of 10 active lines.
* ````python panel_gen.py -o 5xb -t 1xb -a 2```` Originates calls from the No. 5 Crossbar to No. 1 Crossbar. Maximum of 2 active lines.
* ````python panel_gen.py -d -l 7225118```` Originates calls from the panel switch, one at a time, to 722-5118 with 15 second duration.

Caveats
-------
This program is designed to control a 100 year old, motor-driven analog switch. The fact that it has so many moving parts means that what looks good on paper is not always the way it behaves in real life. This is especially true when it comes to timing and control. Asterisk has no way of knowing what the switch is doing, outside of the normal subscriber supervision (on hook/off hook). The switch may return various call progress tones back to the caller, but there is currently no easy way for those tones to be recognized and acted upon. Because of this, I've tried to make sanity a priority, so the program should rarely--if ever--do things that the switches can't handle. I've also taken steps to make sure that the program won't "desync" from what Asterisk and the electromechanical switches are actually doing in real life. This element is a constant work in progress, as I discover more and more subtle bugs.

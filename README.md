# panel_gen
Auto call generator for Panel switch at Connections Museum, Seattle.

Connections Museum, Seattle has in it's collection the last remaining Panel-type telephone switch in the world. The switch functions, but mostly sits idle all day, since there is very little human-generated traffic to keep it busy. This program is my attempt to create a small load on the switch during idle time, so it appears to be processing calls from subscribers.

Requirements
------------
This project assumes you have the following:
* a computer running Asterisk
* the required python modules installed
	* tabulate
	* numpy
	* pathlib
	* argparse
	* pycall
* a T1 card
* a channel bank of some sort containing FXO cards

The Panel switch requires the FXO cards in the channel bank to be configured with fxs_ls signalling. The DAHDI configs are part of this repo in the <code>etc</code> directory, and the Adit configs are part of this repository also. Please note that your hardware and software may vary from what I used, but the configs should be a good starting place nonetheless.

Setup
-----
We have a PC with two TE110P T1 cards installed. One is for the museum's C\*NET connection, and the other is used specifically for this project. Astrisk is installed along with DAHDI and libpri. You can find a reasonable primer on this here: http://www.asteriskdocs.org/en/3rd_Edition/asterisk-book-html-chunk/installing_how_to_install_it.html

The T1 card connects to an Adit 600 channel bank near the Panel switch. The Adit is configured with a bunch of cards, but the important ones for us are the FXO cards in slots 4 and 5. Each card supports 8 lines, so 2 cards supports a total of 16. These exit the Adit on a 25-pair cable and terminate on the IDF in the Panel switch. From the distributing frame, they are cabled to the Line Finder frame just like regular subscriber lines.


Usage
-----
Setting up Asterisk and a channel bank is way beyond the scope of this readm so lets assume you've somehow managed to do that without losing all your marbles. It should be possible to run just <code>python panel_gen.py</code> and have everything work out fine, (although you may have to edit the DAHDI group (we use group 6 at the museum)). There are command line arguments that have been mostly tested to work, but I can't make any guarantees that they won't blow something up in the process. Run <code>python panel_gen.py --help</code> to see them. I'll paste them here for convenience.

```
usage: panel_gen.py [-h] [-a lines] [-d] [-l line] [-o [switch]] [-t switch]
                    [-v volume]

Generate calls to electromechanical switches. Defaults to originate a sane
amount of calls from the panel switch if no args are given.

optional arguments:
  -h, --help   show this help message and exit
  -a lines     Maximum number of active lines. Default is 3 for the panel
               switch. Other switches will depend on stuff.
  -d           Deterministic mode. Eliminate timing randomness so various
               functions of the switch can be tested at-will. Will ignore -a
               and -v options entirely.
  -l line      Call only a particular line. Can be used with the -d option for
               placing test calls to a number over and over again.
  -o [switch]  Originate calls from a particular switch, 1xb, 5xb, panel, or
               all. Default is panel.
  -t switch    Terminate calls only on a particular switch, 1xb, 5xb, or
               panel. Default is all.
  -v volume    Call volume is a proprietary blend of frequency and randomness.
               Can be light, normal, or heavy. Default is normal, which is
               good for average load.
```

One other thing I suggest is making bash aliases for this if its something you're going to use often with the same configuration or set of args. That way, you just use your alias, and avoid a bunch of bash command line vomit.

Caveats
-------
There are a couple of things to note about this project before you dive in. Firstly, I'm not a programmer. This is (not even kidding) the _second_ program I've ever written. It's probably not following best practices, and there are a ton of things that could be done more elegantly. My goal was 75% to get this working as quickly and easily as possible and 25% to learn Python and write passable code. 

Secondly, this program is designed to control a 100 year old, motor driven analog switch. The fact that it has so many moving parts means that what looks good on paper is not always the way it behaves in real life. This is especially true when it comes to timing: Call completion times are variable depending on the number dialed. Also, Asterisk has no way of knowing what the switch is doing, outside of the normal subscriber supervision (on hook/off hook). The switch may return various call progress tones back to the caller, but there is currently no easy way for those tones to be recognized and acted upon. Because of this, I've had to engineer in a few behaviors to make the program "safe", in that it won't get overzealous and try to do too many things too fast. One such behavior is inserting 'wwww' in the dialplan before the actual dialed number. This makes asterisk wait a few seconds between picking up the line and actually dialing. This gives the switch time to connect the line to an idle sender and return dial tone. Without this, the simulator would fail entirely. 

Finally, there is some functionality that seems vestigal or half-baked. This is intentional, as I plan on adding things here and there as they become necessary.  

# panel_gen
Auto call generator for Panel switch at Connections Museum, Seattle.

Connections Museum, Seattle has in it's collection the last remaining Panel-type telephone switch in the world. The switch functions, but mostly sits idle all day, since there is very little human-generated traffic to keep it busy. This program is my attempt to create a small load on the switch during idle time, so it appears to be processing calls from subscribers.

This project assumes you have the following setup:
a computer running Asterisk
a T1 card
a channel bank of some sort containing FXO cards

The Panel switch requires the FXO cards in the channel bank to be configured with fxs_ls signalling. The DAHDI configs are also part of this repo in the *etc* directory.

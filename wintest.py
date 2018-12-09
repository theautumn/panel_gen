#!/usr/bin/python
#
# Copyright (C) 2016
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# SUBWIN VS NEWWIN 
# The main difference is that subwin share memory with their parents.
# If you are putting a char in the subwin, you are also putting that
# char in the parent window
# 
# Other resource:
# http://stackoverflow.com/questions/14571860/how-to-delete-a-subwindow-in-the-python-curses-module

import curses

def main_window(y,x):
    win1_start_row = y  - 4
    win1 = stdscr.subwin(win1_start_row,0,0,0)
    win1.box()
    win1.addstr(1,1,"Press q to quit, use arrow keys!")
    win1.bkgd(' ', curses.color_pair(1))
    win1.refresh()

def win2(y,x):
    half_cols = x/2
    rows_size = 5
    x_start_row = y - 5
    y_start_col = 0

    win2 = stdscr.subwin(rows_size, half_cols, x_start_row, y_start_col)
    win2.box()
    win2.addstr(1,1,"Right data.", curses.color_pair(1))
    win2.bkgd(' ', curses.color_pair(2))
    win2.refresh()


def win3(y,x):
    half_cols = x/2
    rows_size = 5
    x_start_row = y - 5
    y_start_col = 0
    win3 = stdscr.subwin(rows_size, half_cols, x_start_row, x/2)
    win3.box()
    win3.addstr(1,1,"Left data.", curses.color_pair(1))
    win3.bkgd(' ', curses.color_pair(3))
    win3.refresh()

NO_KEY_PRESSED = -1

stdscr = curses.initscr()
stdscr.nodelay(True)

# Enable the keypad ncurses return (instead of 16 bit value)
stdscr.keypad(True)

# Refresh after attributes
stdscr.refresh()

# No echo to screen
curses.noecho()

# Colors
if curses.has_colors():
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_YELLOW)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_BLUE)

y, x = stdscr.getmaxyx()
main_window(y, x)
win2(y, x)
win3(y, x)

key_pressed = NO_KEY_PRESSED
while key_pressed != ord('q'):
    key_pressed = stdscr.getch()

    if key_pressed == curses.KEY_UP:
        stdscr.addstr(2,1,"going up...", curses.color_pair(4))

    if key_pressed == curses.KEY_DOWN:
        stdscr.addstr(2,1,"going down...", curses.color_pair(4))

    if key_pressed == curses.KEY_RIGHT:
        stdscr.addstr(2,1,"going right...", curses.color_pair(4))

    if key_pressed == curses.KEY_LEFT:
        stdscr.addstr(2,1,"going left...", curses.color_pair(4))

    if key_pressed == curses.KEY_RESIZE:
        stdscr.erase()
        y, x = stdscr.getmaxyx()
        main_window(y, x)
        win2(y, x)
        win3(y, x)

    stdscr.refresh()

curses.endwin()

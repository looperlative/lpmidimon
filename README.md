# lpmidimon

This Python3/PyQt5 application is for monitoring and upgrading a Looperlative device
via MIDI.  The Looperlative device must be running software v2.51 or higher.

Requirements:

Python3 is required to run this application.

Windows:
	Python is not installed on Windows by default.  If you open a "cmd" window and type
	"python" on the command line, Windows will lead you through the steps of installing
	Python on Windows.

	Because MIDI is not built in to Python, this application uses mido and python-rtmidi.
	"python-rtmidi" requires Microsoft Visual C++ to install it.  You must go to the
	Microsoft web site and install Visual C++.

All systems:
	The python packages "psutil", "mido", "python-rtmidi" and "PyQt5" are required to run this
	application.  If you do not already have these installed on your system, then
	use "pip install" to install them.

To run:
	python3 lpmidimon

There is a makefile provided that works on Linux.  The makefile produces a single file
archive of the lpmidimon directory that can be executed on the command line by typing
"lpmidimon".  I have not tried this technique on Windows nor Mac.  If you clean this
up for Windows and Mac, please contact Looperlative through a message on
www.looperlative.com.  I will likely gladly accept your changes.  Thank you.

See LICENSE file for full text of the license.

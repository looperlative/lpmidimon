#
# Copyright 2021 - Looperlative Audio Products, LLC
#

default: lpmidimon/lp2ctrlui.py lpmidimon/licensedialog.py

bin/lpmidimon: bin lpmidimon/*.py
	(cd lpmidimon; zip -r ../bin/lpmidimon.zip *)
	echo '#!/usr/bin/env python3' | cat - bin/lpmidimon.zip > bin/lpmidimon
	chmod +x bin/lpmidimon
	(cd lpmidimon; pyinstaller --onefile --windowed lpmidimon.py)

lpmidimon/lp2ctrlui.py: lp2ctrlui.ui
	pyuic5 lp2ctrlui.ui > lpmidimon/lp2ctrlui.py

lpmidimon/licensedialog.py: licensedialog.ui
	pyuic5 licensedialog.ui > lpmidimon/licensedialog.py

bin:
	-mkdir bin

FORCE:

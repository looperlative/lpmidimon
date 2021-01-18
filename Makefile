#
# Copyright 2021 - Looperlative Audio Products, LLC
#

bin/lpmidimon: bin lpmidimon/*.py
	(cd lpmidimon; zip -r ../bin/lpmidimon.zip *)
	echo '#!/usr/bin/env python3' | cat - bin/lpmidimon.zip > bin/lpmidimon
	chmod +x bin/lpmidimon

bin:
	-mkdir bin

FORCE:

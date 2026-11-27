# Floodwatch. Standard library Python, no build step.
PYTHON  := $(shell which python3)
PORT    := 8090
MCP_PORT := 8091
LEAFLET := 1.9.4
MARKERCLUSTER := 1.5.3

.PHONY: help libs data poll serve mcp test test-py test-js og figures screenshot clean

help:
	@echo "make libs    download Leaflet $(LEAFLET) and Leaflet.markercluster $(MARKERCLUSTER) into site/lib and verify them"
	@echo "make data    build the map overlays in site/data from OpenStreetMap"
	@echo "make poll    run one poll of every feed, without the server"
	@echo "make serve   run the server, which also polls every 5 minutes"
	@echo "make mcp     run the MCP server on http://localhost:$(MCP_PORT)/mcp, reading from make serve"
	@echo "make test    run the Python and JavaScript tests (needs Node 22 or later)"
	@echo "make og      redraw the link preview image (needs Google Chrome and make data)"
	@echo "make figures redraw the README's figures in docs/ (needs make data, and reads the live site)"
	@echo "make screenshot  retake the README's screenshot (needs Google Chrome, Node and make serve)"
	@echo "make clean   remove downloaded libraries, overlays and the download cache"
	@echo "             (the readings database in data/ is kept)"

# Leaflet and its marker-clustering plugin are pinned by version and by
# checksum (libs.sha256).
libs:
	@mkdir -p site/lib/leaflet site/lib/markercluster
	@for f in leaflet.js leaflet.css; do \
		test -f site/lib/leaflet/$$f || curl -sfL "https://unpkg.com/leaflet@$(LEAFLET)/dist/$$f" -o site/lib/leaflet/$$f || exit 1; \
	done
	@for f in leaflet.markercluster.js MarkerCluster.css; do \
		test -f site/lib/markercluster/$$f || curl -sfL "https://unpkg.com/leaflet.markercluster@$(MARKERCLUSTER)/dist/$$f" -o site/lib/markercluster/$$f || exit 1; \
	done
	@shasum -a 256 -c libs.sha256

data:
	$(PYTHON) scripts/fetch_geodata.py

poll:
	$(PYTHON) -m monitor.poll --once

serve:
	$(PYTHON) serve.py $(PORT)

mcp:
	$(PYTHON) -m floodwatch_mcp --port $(MCP_PORT) --site http://127.0.0.1:$(PORT) --url http://localhost:$(MCP_PORT)/mcp

test: test-py test-js

test-py:
	$(PYTHON) -m unittest discover -s tests -t .
	$(PYTHON) -m unittest discover -s stdmcp/tests -t .

test-js:
	node --test 'tests/js/*.test.mjs'

og:
	$(PYTHON) scripts/og_image.py

figures:
	$(PYTHON) scripts/figures.py

screenshot:
	$(PYTHON) scripts/screenshot.py --url http://localhost:$(PORT)/

clean:
	rm -rf site/lib site/data .cache data/places.json

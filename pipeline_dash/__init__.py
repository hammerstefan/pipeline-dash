import logging
import sys

import pipeline_dash.main

__main__ = pipeline_dash.main
dash = pipeline_dash.main.dash

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

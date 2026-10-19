"""Shared paths. Scripts here run with python3 -I, so the library folders are added by hand."""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
DERIVED = os.path.join(ROOT, 'data', 'derived')
DOCS = os.path.join(ROOT, 'docs')
for p in (os.path.join(ROOT, '.pylib'), os.path.expanduser('~/.local/lib/python3.12/site-packages')):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

"""
    Helpful functions for namespaces
"""

import re

# control characters from 0-31 and 127 (delete) excluding:
#   9 (\t, tab)
#   10 (\n, new line character)
#   13 (\r, carriage return)
#   127 (\x1f, delete)
# which are handled properly by python xml libraries such
# as xml.dom.minidom and elementtree
_ctrl_chars = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]')
def has_ctrlchars(value):
    if _ctrl_chars.search(value):
        return True
    return False

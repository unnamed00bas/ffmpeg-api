"""
Common schema definitions
"""
from typing import Union
from pydantic import HttpUrl

# File source can be an ID (int) or a URL (str/HttpUrl)
# We use str for URL to avoid strict Pydantic HttpUrl object overhead in some contexts,
# but HttpUrl ensures validation.
FileSource = Union[int, HttpUrl]

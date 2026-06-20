"""wikipedia_weaver — Wikipedia pageviews (enwiki article title -> recent pageview count) weaver for Braidworks."""

from wikipedia_weaver.factory import build_wikipedia_weaver
from wikipedia_weaver.provider import WikipediaWeaverProvider, register
from wikipedia_weaver.weaver import WikipediaWeaver

__all__ = [
    "build_wikipedia_weaver",
    "register",
    "WikipediaWeaver",
    "WikipediaWeaverProvider",
]

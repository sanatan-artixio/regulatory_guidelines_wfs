"""FDA Guidance Documents Harvester - Lean Implementation"""

from .crawler import FDACrawler
from .main import FDACrawlerRefactored
from .config import settings

__version__ = "1.0.0"
__all__ = ['FDACrawler', 'FDACrawlerRefactored', 'settings']

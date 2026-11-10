"""Put the code of chapters 1 to 12 on the import path."""

import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1]
for folder in sorted(EXAMPLES.glob("[01][0-9]_*")):
    if folder.name < "13" and str(folder) not in sys.path:
        sys.path.append(str(folder))

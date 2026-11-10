"""Put the example folders of chapters 1 to 8 on the import path.

Chapter 9 reuses their code unchanged. The folders go at the end of the
path, so nothing here can shadow a module of chapter 9's own.
"""

import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1]

for folder in sorted(EXAMPLES.glob("0[1-8]_*")):
    if str(folder) not in sys.path:
        sys.path.append(str(folder))

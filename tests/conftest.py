import os
import sys

# Garante que a raiz do projeto esteja no PATH para os imports `src.*` e `config.*`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

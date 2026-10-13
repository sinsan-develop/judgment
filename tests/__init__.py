"""설치 없이 정본 src를 사용하는 합성 시험."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

"""The robust compose file in README.md must match sample.docker-compose.yaml."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _readme_block(heading):
    text = (ROOT / "README.md").read_text()
    part = text.split(heading, 1)[1]
    return re.search(r"```yaml\n(.*?)\n```", part, re.S).group(1)


def test_robust_compose_in_readme_matches_sample_file():
    sample = (ROOT / "sample.docker-compose.yaml").read_text().rstrip("\n")
    assert _readme_block("### Robust `docker-compose.yaml`") == sample


def test_sample_env_has_every_env_example_key():
    def keys(name):
        return {
            line.split("=", 1)[0]
            for line in (ROOT / name).read_text().splitlines()
            if re.match(r"^[A-Z_]+=", line)
        }

    assert keys(".env.example") <= keys("sample.env")

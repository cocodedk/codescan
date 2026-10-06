"""A file is written in a fixed number of queries, however much it defines."""
from unittest.mock import MagicMock

from codescan_lib.analysis import analyze_file


def queries_for(tmp_path, count: int) -> int:
    body = "".join(
        f"MAX_{i} = {i}\nclass C{i}:\n    def m(self):\n        helper_{i}(1)\ndef f{i}():\n    g{i}()\n"
        for i in range(count)
    )
    path = tmp_path / f"m{count}.py"
    path.write_text(body)
    session = MagicMock()
    analyze_file(str(path), session, str(tmp_path), defer_relationships=True)
    return session.run.call_count


def test_should_write_a_file_in_a_fixed_number_of_queries(tmp_path):
    assert queries_for(tmp_path, 40) == queries_for(tmp_path, 2)

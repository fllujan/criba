import threading
from pathlib import Path

from criba.core.cache import Cache, make_key
from criba.core.cost import Usage


def test_make_key_stable_and_sensitive() -> None:
    assert make_key("a", 1, "b") == make_key("a", 1, "b")
    assert make_key("a", 1, "b") != make_key("a", 1, "c")


def test_put_get_roundtrip(tmp_path: Path) -> None:
    with Cache(tmp_path / "c.sqlite3") as c:
        assert c.get("k") is None and not c.has("k")
        c.put(
            "k", book_sha="s", kind="chunk", payload='{"x":1}', model="m", usage=Usage(1, 2, 3, 4)
        )
        payload, usage = c.get("k") or ("", Usage())
        assert payload == '{"x":1}'
        assert (usage.input, usage.output, usage.cache_write, usage.cache_read) == (1, 2, 3, 4)
        assert c.has("k") and c.count("s") == 1 and c.count() == 1


def test_persists_between_connections(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite3"
    with Cache(db) as c:
        c.put("k", book_sha="s", kind="chunk", payload="{}", model="m", usage=Usage())
    with Cache(db) as c:
        assert c.has("k")


def test_thread_safe_writes(tmp_path: Path) -> None:
    with Cache(tmp_path / "c.sqlite3") as c:

        def write(n: int) -> None:
            for i in range(25):
                c.put(
                    f"{n}-{i}", book_sha="s", kind="chunk", payload="{}", model="m", usage=Usage()
                )

        threads = [threading.Thread(target=write, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert c.count() == 100


def test_jobs_and_interrupted(tmp_path: Path) -> None:
    with Cache(tmp_path / "c.sqlite3") as c:
        opts = {"nivel": "normal"}
        j1 = c.start_job(book_sha="s", pdf_path=Path("/l.pdf"), title="Bio", options=opts)
        c.finish_job(j1, "cancelled", cost_usd=0.5)
        assert [j.id for j in c.interrupted_jobs()] == [j1]
        j2 = c.start_job(book_sha="s", pdf_path=Path("/l.pdf"), title="Bio", options=opts)
        c.finish_job(j2, "done", outputs=["/x.json"], cost_usd=0.1)
        assert c.interrupted_jobs() == []  # se terminó después
        done = c.jobs("done")
        assert done[0].outputs == ["/x.json"] and done[0].pdf_path == Path("/l.pdf")
        j3 = c.start_job(book_sha="s", pdf_path=Path("/l.pdf"), title="Bio", options=opts)
        assert [j.id for j in c.interrupted_jobs()] == [j3]  # se quedó «running»


def test_clear(tmp_path: Path) -> None:
    with Cache(tmp_path / "c.sqlite3") as c:
        c.put("k", book_sha="s", kind="chunk", payload="{}", model="m", usage=Usage())
        c.start_job(book_sha="s", pdf_path=Path("/l.pdf"), title="B", options={})
        c.clear()
        assert c.count() == 0 and c.jobs() == []

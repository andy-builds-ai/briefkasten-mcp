"""Test coverage for zettel_abraeumen: direct call, then the real MCP protocol.

Run with: .venv/Scripts/python.exe tests/test_zettel_abraeumen.py
Writes only into a throwaway mailbox under a temp directory, never into the
real BRIEFKASTEN_PATH.
"""
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def make_mailbox() -> Path:
    box = Path(tempfile.mkdtemp(prefix="briefkasten_test_"))
    (box / "gelesen").mkdir()
    return box


def test_direct_call():
    """Stage 1: call the function directly, running through all six cases."""
    box = make_mailbox()
    previous_path = os.environ.get("BRIEFKASTEN_PATH")
    os.environ["BRIEFKASTEN_PATH"] = str(box)

    try:
        import importlib
        import server
        importlib.reload(server)

        folder = server._briefkasten()
        gelesen = folder / "gelesen"

        fall2 = "2026-08-01_1000_werkstatt-an-architekt.md"
        fall3 = "2026-08-01_1010_werkstatt-an-architekt.md"
        fall4 = "2026-08-01_1020_werkstatt-an-architekt.md"
        fall5 = "2026-08-01_1030_werkstatt-an-architekt.md"
        fall1 = "../evil.md"

        (folder / fall2).write_text("a", encoding="utf-8")
        (folder / fall3).write_text("b-kasten", encoding="utf-8")
        (gelesen / fall3).write_text("b-gelesen", encoding="utf-8")
        (gelesen / fall4).write_text("c-gelesen", encoding="utf-8")

        ergebnis = server.zettel_abraeumen([fall2, fall3, fall4, fall5, fall1])

        assert ergebnis.startswith("3 von 5")
        assert (gelesen / fall2).exists() and not (folder / fall2).exists()
        assert (folder / fall3).exists()
        assert (gelesen / fall3).read_text(encoding="utf-8") == "b-gelesen"
        assert (gelesen / fall4).exists() and not (folder / fall4).exists()
        assert "nicht gefunden" in ergebnis
        assert "abgelehnt" in ergebnis

        # Case 6: create the target as a directory, so rename() fails on a
        # real OSError instead of getting caught by the "target already
        # taken" check.
        fall6 = "2026-08-01_1200_werkstatt-an-architekt.md"
        (folder / fall6).write_text("x", encoding="utf-8")
        (gelesen / fall6).mkdir()
        ergebnis6 = server.zettel_abraeumen([fall6])
        assert "Verschieben fehlgeschlagen" in ergebnis6
        assert (folder / fall6).exists()
    finally:
        shutil.rmtree(box, ignore_errors=True)
        if previous_path is None:
            os.environ.pop("BRIEFKASTEN_PATH", None)
        else:
            os.environ["BRIEFKASTEN_PATH"] = previous_path

    print("test_direct_call: OK")


async def _protocol_check():
    """Stage 2: over the real MCP protocol, its own stdio server process."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    box = make_mailbox()
    gelesen = box / "gelesen"
    name_move = "2026-08-01_1100_werkstatt-an-architekt.md"
    name_both = "2026-08-01_1110_werkstatt-an-architekt.md"
    (box / name_move).write_text("move-me", encoding="utf-8")
    (box / name_both).write_text("kasten", encoding="utf-8")
    (gelesen / name_both).write_text("gelesen", encoding="utf-8")

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO / "server.py")],
        env={**os.environ, "BRIEFKASTEN_PATH": str(box)},
    )

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                assert "zettel_abraeumen" in names

                result = await session.call_tool(
                    "zettel_abraeumen", {"dateinamen": [name_move, name_both]}
                )
                text = result.content[0].text
                assert text.startswith("2 von 2")
                assert "schon abgeräumt" in text
    finally:
        shutil.rmtree(box, ignore_errors=True)


def test_protocol_call():
    asyncio.run(_protocol_check())
    print("test_protocol_call: OK")


if __name__ == "__main__":
    test_direct_call()
    test_protocol_call()
    print("Alle Tests OK.")

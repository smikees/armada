"""Image attachments: _save_images returns path dicts that the chat_stream message builder joins.

Regression for 'sequence item 0: expected str instance, dict found' — _save_images returns a list
of dicts (since the thumbnail feature), but the message builder used to `"; ".join(saved)` directly.
"""
from armada import runner

# a 1x1 transparent PNG as a data URL
_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4"
        "2mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")


def test_save_images_returns_joinable_paths(tmp_path):
    ad = tmp_path / "agents" / "warren"
    ad.mkdir(parents=True)
    saved = runner._save_images(ad, "main", [{"data": _PNG, "name": "shot.png"}])
    assert saved, "an image should have been saved"
    assert all(isinstance(s, dict) and "path" in s and "file" in s and "name" in s for s in saved)
    # the exact operation the runner performs — must not raise
    joined = "; ".join(s["path"] for s in saved)
    assert joined and saved[0]["file"].endswith(".png")
    assert (ad / "threads" / "main" / "attachments" / saved[0]["file"]).exists()

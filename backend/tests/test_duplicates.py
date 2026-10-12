"""[ANTI-FRAUD] dHash, BK-Tree, merge sort and the duplicate-clip checker.

Pictures are generated with Pillow (random shapes), and YouTube downloads are replaced by a fake
fetcher, so the tests run offline.
"""

import random

import pytest
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from app.algorithms.bktree import BKTree
from app.algorithms.dhash import dhash, hamming, is_flat
from app.algorithms.sorting import merge_sort
from app.models.submission import SubmissionStatus
from app.models.user import UserRole
from app.services import duplicate_check as dc


def picture(seed: int) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", (320, 180), tuple(rnd.randrange(256) for _ in range(3)))
    draw = ImageDraw.Draw(img)
    for _ in range(12):
        x0, y0 = rnd.randrange(300), rnd.randrange(160)
        x1, y1 = x0 + rnd.randrange(20, 160), y0 + rnd.randrange(20, 100)
        draw.rectangle([x0, y0, x1, y1], fill=tuple(rnd.randrange(256) for _ in range(3)))
    return img


def brighter(img: Image.Image) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(1.3)


# --- algorithms ---------------------------------------------------------------------------------


def test_dhash_survives_brightness_and_resize():
    img = picture(1)
    assert hamming(dhash(img), dhash(brighter(img))) <= 3
    assert hamming(dhash(img), dhash(img.resize((120, 90)))) <= 3


def test_different_pictures_are_far_apart():
    assert hamming(dhash(picture(1)), dhash(picture(2))) > 10


def test_plain_picture_is_flat():
    assert is_flat(Image.new("RGB", (120, 90), (0, 0, 0)))
    assert not is_flat(picture(3))


def test_bktree_search_matches_linear_search_and_skips_work():
    rnd = random.Random(7)
    values = [rnd.getrandbits(64) for _ in range(500)]
    tree = BKTree()
    for i, v in enumerate(values):
        tree.insert(v, i)
    query = values[42] ^ 0b101  # 2 bits away from item 42
    for radius in (0, 3, 8):
        tree.comparisons = 0
        got = sorted(tree.search(query, radius))
        expected = sorted((i, hamming(query, v)) for i, v in enumerate(values) if hamming(query, v) <= radius)
        assert got == expected
    tree.comparisons = 0
    tree.search(query, 3)
    assert tree.comparisons < len(values)  # pruned, unlike a linear scan


def test_bktree_lazy_delete():
    tree = BKTree()
    tree.insert(0b1111, "a")
    tree.insert(0b1110, "b")
    assert tree.delete_owner("a") == 1
    assert [o for o, _ in tree.search(0b1111, 1)] == ["b"]
    assert tree.size == 2  # the node stays, only flagged


def test_merge_sort_descending_and_stable():
    items = [("x", 2), ("y", 5), ("z", 2), ("w", 9)]
    assert merge_sort(items, key=lambda t: t[1], descending=True) == [("w", 9), ("y", 5), ("x", 2), ("z", 2)]


# --- the checker ----------------------------------------------------------------------------------


@pytest.fixture()
def setup(db, make_user, make_campaign, make_submission):
    """frames[video_id] = list of pictures the fake YouTube returns for that video."""
    frames: dict[str, list[Image.Image]] = {}

    def fetch(video_id):
        return [(dc.FRAMES[i], img) for i, img in enumerate(frames.get(video_id, []))]

    campaign = make_campaign()
    index = dc.DuplicateIndex()

    def submit(video_id, pictures, creator=None, status=SubmissionStatus.under_review):
        frames[video_id] = pictures
        return make_submission(campaign, creator or make_user(UserRole.creator), external_video_id=video_id, status=status)

    def check(sub):
        return dc.check_submission(db, sub, index=index, fetch=fetch)

    return submit, check, index


ORIGINAL = [picture(10), picture(11), picture(12), picture(13)]


def test_brightened_reupload_is_probably_a_copy(setup):
    submit, check, _ = setup
    original = submit("orig0000001", ORIGINAL)
    copy = submit("copy0000001", [brighter(p) for p in ORIGINAL])
    report = check(copy)
    assert report.level == "copy"
    assert report.matches[0].submission_id == original.id
    assert report.matches[0].submitted_earlier  # the original was sent first
    assert report.matches[0].campaign_id == original.campaign_id
    # +30% brightness pushes some flat areas to pure white, which can move one picture past the
    # 8-bit radius (picture 10 moves 12 bits) — the other 3 still match, so it is still a "copy".
    assert report.matches[0].similarity >= 0.75


def test_one_identical_picture_is_should_check(setup):
    submit, check, _ = setup
    original = submit("orig0000002", ORIGINAL)
    partial = submit("part0000001", [ORIGINAL[1], picture(20), picture(21), picture(22)])
    report = check(partial)
    assert report.level == "check"
    match = report.matches[0]
    assert (match.submission_id, match.matched_pictures, match.closest_distance) == (original.id, 1, 0)


def test_unrelated_clip_has_no_warning(setup):
    submit, check, _ = setup
    submit("orig0000003", ORIGINAL)
    report = check(submit("diff0000001", [picture(30), picture(31), picture(32), picture(33)]))
    assert report.level is None and report.matches == []


def test_mirrored_copy_is_caught(setup):
    submit, check, _ = setup
    submit("orig0000004", ORIGINAL)
    report = check(submit("mirr0000001", [ImageOps.mirror(p) for p in ORIGINAL]))
    assert report.level == "copy"
    assert report.matches[0].mirrored


def test_same_creator_is_not_compared(setup, make_user):
    submit, check, _ = setup
    me = make_user(UserRole.creator)
    submit("orig0000005", ORIGINAL, creator=me)
    report = check(submit("mine0000001", ORIGINAL, creator=me))
    assert report.matches == []


def test_rejected_original_is_ignored(setup):
    submit, check, index = setup
    original = submit("orig0000006", ORIGINAL)
    check(original)  # hashes it
    original.status = SubmissionStatus.rejected
    index.remove(original.id)  # DELETE (in the app the status listener does this on the shared index)
    report = check(submit("copy0000002", ORIGINAL))
    assert report.matches == []


def test_plain_frames_are_skipped(setup):
    submit, check, _ = setup
    black = Image.new("RGB", (120, 90), (0, 0, 0))
    submit("blak0000001", [black, picture(40)])
    report = check(submit("blak0000002", [black, picture(41)]))
    assert report.pictures_checked == 1
    assert report.matches == []


# --- admin submissions API ------------------------------------------------------------------------


def _token(user):
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def test_admin_sees_who_submitted(db, make_user, make_campaign, make_submission):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        admin, brand = make_user(UserRole.admin), make_user(UserRole.brand)
        creator = make_user(UserRole.creator, youtube_channel_id="UC123", youtube_channel_title="Mint Channel")
        campaign = make_campaign(brand)
        sub = make_submission(campaign, creator, status=SubmissionStatus.approved)

        rows = client.get(f"/api/admin/campaigns/{campaign.id}/submissions", headers=_token(admin)).json()
        assert rows[0]["creator_name"] == creator.display_name
        assert rows[0]["youtube_channel_title"] == "Mint Channel"
        assert "creator_email" not in rows[0]  # the list stays light; email is in the details

        detail = client.get(f"/api/admin/submissions/{sub.id}", headers=_token(admin)).json()
        assert detail["creator_email"] == creator.email

        for who in (brand, creator):  # admins only
            assert client.get(f"/api/admin/campaigns/{campaign.id}/submissions", headers=_token(who)).status_code == 403
            assert client.get(f"/api/admin/submissions/{sub.id}", headers=_token(who)).status_code == 403
    finally:
        app.dependency_overrides.clear()

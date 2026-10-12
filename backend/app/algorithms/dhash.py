"""dHash ("difference hash"): a 64-bit fingerprint of a picture.

1. Shrink the picture to 9 x 8 pixels and make it grey.
2. In every row, compare each pixel with its right-hand neighbour: left brighter -> 1, else -> 0.
3. 8 rows x 8 comparisons = 64 bits.

Because only neighbours are compared, making the whole picture brighter/darker, re-encoding it or
lowering its quality barely changes the fingerprint. Two fingerprints are compared with the
Hamming distance (how many of the 64 bits differ).
"""

from PIL import Image, ImageOps

HASH_SIZE = 8  # 8 x 8 comparisons -> 64 bits
FLAT_RANGE = 12  # if the brightest and darkest of the 72 pixels differ by less, the picture is "plain"


def _tiny_grey(img: Image.Image) -> bytes:
    return img.convert("L").resize((HASH_SIZE + 1, HASH_SIZE), Image.Resampling.LANCZOS).tobytes()


def dhash(img: Image.Image) -> int:
    px = _tiny_grey(img)
    width = HASH_SIZE + 1
    h = 0
    for row in range(HASH_SIZE):
        for col in range(HASH_SIZE):
            left = px[row * width + col]
            right = px[row * width + col + 1]
            h = (h << 1) | (1 if left > right else 0)
    return h


def dhash_mirrored(img: Image.Image) -> int:
    """Fingerprint of the left-right flipped picture — catches mirrored re-uploads."""
    return dhash(ImageOps.mirror(img))


def hamming(a: int, b: int) -> int:
    """Number of bits that differ between two fingerprints (0 = identical, ~32 = unrelated)."""
    return (a ^ b).bit_count()


def is_flat(img: Image.Image) -> bool:
    """Plain black/white/single-colour pictures all hash to almost the same value and would match
    each other, so they are skipped."""
    px = _tiny_grey(img)
    return max(px) - min(px) < FLAT_RANGE

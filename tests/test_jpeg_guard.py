"""JPEG scan validation rejects tolerated bytes without re-encoding artwork."""

import io

import pytest
from ocf_tools.jpeg_guard import check_jpeg
from ocf_tools.utils import OCFError

pytestmark = pytest.mark.unit


def jpeg(*, mode="RGB", progressive=False, subsampling=2, restart=0, optimize=False):
    image = pytest.importorskip("PIL.Image")
    channels = {"L": 1, "RGB": 3, "CMYK": 4}[mode]
    # Odd dimensions and deterministic textured coefficients exercise edge MCUs,
    # nonzero refinement bits, stuffed bytes and noninterleaved chroma scans.
    pixels = bytes((i * 97 + i // 13 * 31) % 256 for i in range(39 * 27 * channels))
    stream = io.BytesIO()
    image.frombytes(mode, (39, 27), pixels).save(
        stream,
        format="JPEG",
        quality=91,
        progressive=progressive,
        subsampling=subsampling,
        restart_marker_blocks=restart,
        optimize=optimize,
    )
    return stream.getvalue()


def scan_boundaries(data):
    position = 2
    while position < len(data):
        assert data[position] == 255
        marker = data[position + 1]
        if marker == 0xD9:
            return
        length = int.from_bytes(data[position + 2 : position + 4], "big")
        position += length + 2
        if marker == 0xDA:
            while True:
                position = data.index(b"\xff", position)
                following = data[position + 1]
                if following == 0:
                    position += 2
                    continue
                yield position
                if 0xD0 <= following <= 0xD7:
                    position += 2
                    continue
                break


@pytest.mark.parametrize(
    "mode,subsampling", [("L", 0), ("RGB", 0), ("RGB", 1), ("RGB", 2), ("CMYK", 0)]
)
@pytest.mark.parametrize("progressive", [False, True])
@pytest.mark.parametrize("restart", [0, 2])
@pytest.mark.parametrize("optimize", [False, True])
def test_valid_huffman_jpegs_keep_exact_bytes(mode, subsampling, progressive, restart, optimize):
    data = jpeg(
        mode=mode,
        subsampling=subsampling,
        progressive=progressive,
        restart=restart,
        optimize=optimize,
    )
    check_jpeg(data)


@pytest.mark.parametrize("progressive", [False, True])
@pytest.mark.parametrize("restart", [0, 2])
@pytest.mark.parametrize("extra", [b"PRIVATE_METADATA_FIXTURE", b"\0", b"\xff\x00"])
def test_every_scan_and_restart_boundary_rejects_extra_coding_bytes(progressive, restart, extra):
    data = jpeg(progressive=progressive, restart=restart)
    check_jpeg(data)
    boundaries = list(scan_boundaries(data))
    assert boundaries and data[boundaries[-1] :] == b"\xff\xd9"
    if progressive:
        assert len(boundaries) > 1
    for position in boundaries:
        with pytest.raises(OCFError, match="unused scan data"):
            check_jpeg(data[:position] + extra + data[position:])


@pytest.mark.parametrize("progressive", [False, True])
def test_truncated_entropy_and_wrong_restart_sequence_fail(progressive):
    data = jpeg(progressive=progressive, restart=2)
    restart = next(p for p in scan_boundaries(data) if data[p + 1] == 0xD0)
    for bad in [
        data[: restart - 1] + data[restart:],
        data[: restart + 1] + b"\xd3" + data[restart + 2 :],
    ]:
        with pytest.raises(OCFError):
            check_jpeg(bad)


@pytest.mark.parametrize("marker", [b"\xff\xdb", b"\xff\xc4", b"\xff\xc0", b"\xff\xda"])
def test_coding_segment_payloads_cannot_carry_opaque_trailers(marker):
    data = jpeg()
    position = data.index(marker)
    length = int.from_bytes(data[position + 2 : position + 4], "big")
    end = position + length + 2
    extra = b"PRIVATE_METADATA_FIXTURE"
    corrupt = (
        data[: position + 2]
        + (length + len(extra)).to_bytes(2, "big")
        + data[position + 4 : end]
        + extra
        + data[end:]
    )
    with pytest.raises(OCFError):
        check_jpeg(corrupt)

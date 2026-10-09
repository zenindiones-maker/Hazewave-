"""Rig readiness never follows from a RGBA filename or green website build."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
import zlib

import pytest

from hazewave.wave_art_rig_preflight import (
    RigPreflightError, inspect_rgba_png, verify_owner_art_sources,
)

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/"knowledge/wave-approved-art-rig-readiness-v1.json"


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)


def image_png(*, alpha=(0,100,255,80)) -> bytes:
    raw=b""
    for row in (alpha[:2],alpha[2:]):
        raw+=b"\x00"+b"".join(bytes((10,20,30,a)) for a in row)
    return (b"\x89PNG\r\n\x1a\n"
            +chunk(b"IHDR",struct.pack(">IIBBBBB",2,2,8,6,0,0,0))
            +chunk(b"IDAT",zlib.compress(raw))
            +chunk(b"IEND",b""))


def test_decodes_real_rgba_alpha_distribution():
    d=inspect_rgba_png(image_png())
    assert d["width"]==2 and d["height"]==2
    assert d["transparent_pct"]==25
    assert d["opaque_pct"]==25
    assert d["partial_pct"]==50


def test_invalid_crc_and_truncated_png_are_blocked():
    invalid=image_png()
    with pytest.raises(RigPreflightError):
        inspect_rgba_png(invalid[:-8])
    bad=bytearray(invalid)
    bad[45]^=1
    with pytest.raises(RigPreflightError):
        inspect_rgba_png(bytes(bad))


def test_rejects_bounded_png_decompression_expansion():
    # 2x2 RGBA IHDR, but many times the permitted 18 decompressed bytes.
    rows=b"\\x00"+b"\\xff"*(6_000_000)
    payload=(b"\\x89PNG\\r\\n\\x1a\\n"
             +chunk(b"IHDR",struct.pack(">IIBBBBB",2,2,8,6,0,0,0))
             +chunk(b"IDAT",zlib.compress(rows))
             +chunk(b"IEND",b""))
    with pytest.raises(RigPreflightError,match="PNG_DECOMPRESS_SIZE_INVALID"):
        inspect_rgba_png(payload)


def test_source_integrity_and_alpha_do_not_authorize_individual_part_rig(tmp_path):
    img=image_png()
    filename="owned.png"
    (tmp_path/filename).write_bytes(img)
    ledger={"schema":"HazewaveWaveApprovedArtRigReadiness/v1",
            "authority":"NONE","production_approved":False,
            "files_in_github":False,"animation_rigs_ready":False,
            "assets":[{"id":"A01","filename":filename,"sha256":sha256(img).hexdigest(),
                       "width":2,"height":2,"transparent_pct":25,
                       "opaque_pct":25,"partial_pct":50,
                       "independent_pads_ready":False,"cleanplate_verified":False,
                       "mechanical_pieces_ready":False}]}
    result=verify_owner_art_sources(tmp_path,ledger)
    assert result["owner_source_bytes_verified"] is True
    assert result["physical_animation_rigs_verified"] is False
    assert result["production_approved"] is False
    assert result["files_verified"]==1


def test_fails_source_sha_mismatch_and_privileged_flags(tmp_path):
    img=image_png()
    (tmp_path/"owned.png").write_bytes(img)
    ledger={"schema":"HazewaveWaveApprovedArtRigReadiness/v1",
            "authority":"NONE","production_approved":False,
            "files_in_github":False,"animation_rigs_ready":False,
            "assets":[{"id":"A01","filename":"owned.png","sha256":"a"*64,
                       "width":2,"height":2,"transparent_pct":25,
                       "opaque_pct":25,"partial_pct":50,
                       "independent_pads_ready":False,"cleanplate_verified":False,
                       "mechanical_pieces_ready":False}]}
    with pytest.raises(RigPreflightError,match="SOURCE_SHA_MISMATCH"):
        verify_owner_art_sources(tmp_path,ledger)
    ledger["assets"][0]["sha256"]=sha256(img).hexdigest()
    for key in ("production_approved","files_in_github","animation_rigs_ready"):
        test=deepcopy(ledger)
        test[key]=True
        with pytest.raises(RigPreflightError,match="AUTHORITY_OR_RIG_CLAIM_INVALID"):
            verify_owner_art_sources(tmp_path,test)


def test_repository_ledger_contains_five_immutable_sources_no_rig_claims():
    ledger=json.loads(LEDGER.read_text())
    assert ledger["schema"]=="HazewaveWaveApprovedArtRigReadiness/v1"
    assert len(ledger["assets"])==5
    assert ledger["authority"]=="NONE"
    assert ledger["files_in_github"] is False
    assert ledger["animation_rigs_ready"] is False
    assert ledger["production_approved"] is False
    assert {r["id"] for r in ledger["assets"]}=={"A01","A02","A03","A04","A05"}
    for r in ledger["assets"]:
        assert r["independent_pads_ready"] is False
        assert r["mechanical_pieces_ready"] is False
        assert r["cleanplate_verified"] is False
        assert abs(r["transparent_pct"]+r["opaque_pct"]+r["partial_pct"]-100)<0.004
        assert r["partial_pct"]>35
        assert r["opaque_pct"]<1

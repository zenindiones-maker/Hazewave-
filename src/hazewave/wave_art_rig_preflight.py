"""Inspect exact owner-approved RGBA artwork; never infer an articulated rig.

The original binaries live in the owner's Library, not Git. This module is
stdlib-only to prevent silent Pillow/ML installation on the Codespace.
All calculations are bounded to first-party owner artwork supplied explicitly
by the operator; no generated alpha masks or changed images are produced.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any, Mapping
import zlib

PNG=b"\x89PNG\r\n\x1a\n"
HASH=re.compile(r"^[0-9a-f]{64}$")
MAX_FILE_BYTES=12_000_000
MAX_RAW_BYTES=40_000_000


class RigPreflightError(ValueError):
    pass


def _check(value: bool, code: str) -> None:
    if not value:
        raise RigPreflightError(code)


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any]={}
    for k,v in pairs:
        _check(k not in obj,"LEDGER_DUPLICATE_KEY")
        obj[k]=v
    return obj


def inspect_rgba_png(data: bytes) -> dict[str, float | int]:
    _check(isinstance(data, bytes) and 50<=len(data)<=MAX_FILE_BYTES
           and data.startswith(PNG),"PNG_INVALID")
    offset=len(PNG)
    width=height=0
    idat: list[bytes]=[]
    has_ihdr=False
    ended=False
    while offset+12<=len(data):
        length=struct.unpack_from(">I",data,offset)[0]
        offset+=4
        _check(length<=MAX_FILE_BYTES and offset+length+8<=len(data),
               "PNG_CHUNK_BOUNDS_INVALID")
        name=data[offset:offset+4]
        offset+=4
        payload=data[offset:offset+length]
        offset+=length
        checksum=struct.unpack_from(">I",data,offset)[0]
        offset+=4
        _check((zlib.crc32(name+payload)&0xffffffff)==checksum,
               "PNG_CRC_MISMATCH")
        if name==b"IHDR":
            _check(not has_ihdr and length==13,"PNG_IHDR_INVALID")
            width,height,depth,color,compression,filter_method,interlace=(
                struct.unpack(">IIBBBBB",payload))
            _check(1<=width<=4096 and 1<=height<=4096
                   and depth==8 and color==6
                   and compression==0 and filter_method==0
                   and interlace==0,"PNG_RGBA_8BIT_REQUIRED")
            has_ihdr=True
        elif name==b"IDAT":
            _check(has_ihdr and len(idat)<128,"PNG_IDAT_INVALID")
            idat.append(payload)
        elif name==b"IEND":
            _check(length==0 and has_ihdr and bool(idat),"PNG_IEND_INVALID")
            ended=True
            break
    _check(ended and offset==len(data),"PNG_TRAILING_OR_MISSING_IEND")
    row_size=width*4
    total=(row_size+1)*height
    _check(total<=MAX_RAW_BYTES,"PNG_DECOMPRESS_BUDGET_DENIED")
    try:
        decoder=zlib.decompressobj()
        raw=decoder.decompress(b"".join(idat),total+1)
    except (zlib.error, MemoryError) as exc:
        raise RigPreflightError("PNG_DECOMPRESS_FAILED") from exc
    _check(len(raw)==total and decoder.eof and not decoder.unused_data
           and not decoder.unconsumed_tail,"PNG_DECOMPRESS_SIZE_INVALID")
    prev=bytearray(row_size)
    zero=full=partial=0
    for index in range(height):
        row_begin=index*(row_size+1)
        filt=raw[row_begin]
        _check(filt in (0,1,2,3,4),"PNG_UNSUPPORTED_FILTER")
        line=bytearray(raw[row_begin+1:row_begin+1+row_size])
        for j in range(row_size):
            left=line[j-4] if j>=4 else 0
            up=prev[j]
            northwest=prev[j-4] if j>=4 else 0
            if filt==1:
                predictor=left
            elif filt==2:
                predictor=up
            elif filt==3:
                predictor=(left+up)//2
            elif filt==4:
                center=left+up-northwest
                a=abs(center-left);b=abs(center-up);c=abs(center-northwest)
                predictor=left if a<=b and a<=c else up if b<=c else northwest
            else:
                predictor=0
            line[j]=(line[j]+predictor)&255
        for a in line[3::4]:
            if a==0: zero+=1
            elif a==255: full+=1
            else: partial+=1
        prev=line
    count=width*height
    _check(zero+full+partial==count,"PNG_ALPHA_COUNT_MISMATCH")
    return {
        "width":width,"height":height,
        "transparent_pct":round(zero/count*100,3),
        "opaque_pct":round(full/count*100,3),
        "partial_pct":round(partial/count*100,3),
    }


def verify_owner_art_sources(source_root: Path, ledger: Mapping[str, Any]) -> dict[str, Any]:
    _check(isinstance(ledger, Mapping)
           and ledger.get("schema")=="HazewaveWaveApprovedArtRigReadiness/v1"
           and ledger.get("authority")=="NONE"
           and ledger.get("production_approved") is False
           and ledger.get("files_in_github") is False
           and ledger.get("animation_rigs_ready") is False,
           "AUTHORITY_OR_RIG_CLAIM_INVALID")
    root=Path(source_root)
    _check(root.is_dir() and not root.is_symlink(),"SOURCE_DIR_INVALID")
    assets=ledger.get("assets")
    _check(isinstance(assets,list) and 1<=len(assets)<=5,
           "ART_ASSET_LIST_INVALID")
    verified=[]
    seen=set()
    for item in assets:
        _check(isinstance(item, Mapping),"ART_ENTRY_INVALID")
        name=item.get("filename")
        _check(isinstance(name,str) and 5<len(name)<=130
               and Path(name).name==name and "/" not in name and "\\" not in name
               and name.lower().endswith(".png") and name not in seen,
               "ART_ASSET_PATH_INVALID")
        seen.add(name)
        for field in ("independent_pads_ready","cleanplate_verified",
                      "mechanical_pieces_ready"):
            _check(item.get(field) is False,"AUTHORITY_OR_RIG_CLAIM_INVALID")
        hash_expected=item.get("sha256")
        _check(isinstance(hash_expected,str)
               and bool(HASH.fullmatch(hash_expected)),"ART_HASH_INVALID")
        path=root/name
        _check(path.is_file() and not path.is_symlink()
               and 50<=path.stat().st_size<=MAX_FILE_BYTES,
               "ART_SOURCE_NOT_FOUND")
        blob=path.read_bytes()
        _check(sha256(blob).hexdigest()==hash_expected,"SOURCE_SHA_MISMATCH")
        measurements=inspect_rgba_png(blob)
        for field in ("width","height"):
            _check(type(item.get(field)) is int
                   and measurements[field]==item[field],
                   "ART_DIMENSIONS_MISMATCH")
        for field in ("transparent_pct","opaque_pct","partial_pct"):
            _check(type(item.get(field)) in (float,int)
                   and abs(float(measurements[field])-float(item[field]))<0.0011,
                   "ART_ALPHA_METRICS_DRIFT")
        verified.append({"id":item["id"],"sha256":hash_expected,
                         **measurements})
    return {
        "schema":"HazewaveWaveOwnerSourceIntegrityProbe/v1",
        "owner_source_bytes_verified":True,
        "files_verified":len(verified),
        "assets":verified,
        "physical_animation_rigs_verified":False,
        "source_separation_approved":False,
        "real_site_animation_approved":False,
        "production_approved":False,
    }


def main() -> int:
    p=argparse.ArgumentParser(description="Non-mutating owner-art PNG rig readiness preflight")
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--ledger",type=Path,required=True)
    args=p.parse_args()
    try:
        path=args.ledger
        _check(path.is_file() and not path.is_symlink() and
               path.stat().st_size<=120_000,"LEDGER_PATH_INVALID")
        ledger=json.loads(path.read_text(encoding="utf-8"),object_pairs_hook=_unique_pairs)
        report=verify_owner_art_sources(args.source_root,ledger)
    except (OSError,ValueError,UnicodeError,TypeError) as exc:
        print("WAVE_OWNER_ART_PREFLIGHT=BLOCKED:"+str(exc),file=sys.stderr)
        return 20
    print(json.dumps(report,sort_keys=True,ensure_ascii=False))
    print("WAVE_OWNER_ART_SOURCE_SHA256_AND_ALPHA=PASS")
    print("WAVE_INDEPENDENT_ART_RIGS=NOT_READY")
    print("WAVE_SITE_ARTISTIC_APPROVAL=NOT_GIVEN")
    return 0


if __name__=="__main__":
    raise SystemExit(main())

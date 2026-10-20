"""Actual synthetic media differentiation with FFmpeg, subordinated to HAZE/WAVE.

Provides real negative and positive controls for audio and video metric paths.
No user media ingress, no implicit runtime qualification or agent connection.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

from hazewave.harness import HazewaveTask, route_task, issue_authorization, validate_authorization


class AvFidelityError(RuntimeError):
    pass


_VOL_MEAN = re.compile(r"\bmean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")
_VOL_MAX = re.compile(r"\bmax_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")
_SSIM = re.compile(r"\bAll:(0(?:\.\d+)?|1(?:\.0+)?)\s*\(")


def parse_audio_volumedetect(log: str) -> dict[str,float]:
    if len(log)>1_000_000:
        raise AvFidelityError("VOLUME_LOG_TOO_LARGE")
    mean=_VOL_MEAN.search(log)
    peak=_VOL_MAX.search(log)
    if not mean or not peak:
        raise AvFidelityError("VOLUME_MEASUREMENT_MISSING")
    a,b=float(mean.group(1)),float(peak.group(1))
    if not all(math.isfinite(x) and -150<x<=0.5 for x in (a,b)):
        raise AvFidelityError("VOLUME_MEASUREMENT_INVALID")
    return {"mean_volume_dbfs":a,"max_volume_dbfs":b}


def parse_ssim(log: str) -> float:
    if len(log)>1_000_000:
        raise AvFidelityError("SSIM_LOG_TOO_LARGE")
    values=_SSIM.findall(log)
    if not values:
        raise AvFidelityError("SSIM_MEASUREMENT_MISSING")
    score=float(values[-1])
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise AvFidelityError("SSIM_MEASUREMENT_INVALID")
    return score


def _run(ffmpeg: str, args: list[str], *, timeout: float = 40.) -> subprocess.CompletedProcess[str]:
    env={k:os.environ[k] for k in ("PATH","HOME","LANG","LC_ALL","TMPDIR") if k in os.environ}
    env["LC_ALL"]="C"
    try:
        p=subprocess.run([ffmpeg,"-hide_banner","-nostdin","-v","info",*args],
                         capture_output=True,text=True,check=False,timeout=timeout,env=env)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise AvFidelityError("FFMPEG_UNAVAILABLE_OR_TIMEOUT") from exc
    if p.returncode!=0:
        raise AvFidelityError("FFMPEG_OPERATION_FAILED")
    return p


def _grant(capability:str,domain:str)->str:
    task=HazewaveTask("av-synthetic-"+domain.lower(),
                      "First-party FFmpeg synthetic fidelity audit only",
                      capability,domain)
    auth=validate_authorization(issue_authorization(route_task(task)),
                                expected_task_id=task.task_id,
                                expected_capability=capability)
    return auth.authorization_id


def _secure_write(path:Path,data:bytes)->None:
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def analyze_synthetic_media(*,private_root:Path,ffmpeg_bin:str="ffmpeg")->dict[str,Any]:
    if ffmpeg_bin not in {"ffmpeg"}:
        raise AvFidelityError("FFMPEG_BINARY_NOT_ADMITTED")
    ffmpeg=shutil.which(ffmpeg_bin)
    if not ffmpeg:
        raise AvFidelityError("FFMPEG_NOT_INSTALLED")
    root=Path(private_root).expanduser()
    if (root.exists() or root.is_symlink()
            or root.resolve(strict=False).is_relative_to(Path(__file__).resolve().parents[2])):
        raise AvFidelityError("PRIVATE_ROOT_UNSAFE")
    t0=time.monotonic()
    a_id=_grant("audio.qc","HAZE")
    v_id=_grant("visual.qc","WAVE")
    with tempfile.TemporaryDirectory(prefix="hazewave-fidelity-owned-") as work:
        wd=Path(work)
        src=wd/"source.wav"
        quiet=wd/"quiet.wav"
        video=wd/"identical.mkv"
        different=wd/"different.mkv"
        # Synthetic wave source and a known -12.04 dB gain alteration.
        _run(ffmpeg,["-f","lavfi","-i","sine=frequency=440:sample_rate=48000:duration=1",
                     "-c:a","pcm_s16le","-y",str(src)])
        _run(ffmpeg,["-i",str(src),"-af","volume=0.25","-c:a","pcm_s16le","-y",str(quiet)])
        mean1=parse_audio_volumedetect(_run(ffmpeg,["-i",str(src),"-af","volumedetect",
                                                  "-f","null","-"]).stderr)
        mean2=parse_audio_volumedetect(_run(ffmpeg,["-i",str(quiet),"-af","volumedetect",
                                                  "-f","null","-"]).stderr)
        attenuation=mean1["mean_volume_dbfs"]-mean2["mean_volume_dbfs"]
        if attenuation < 10 or attenuation > 14:
            raise AvFidelityError("AUDIO_KNOWN_DEGRADATION_NOT_DETECTED")
        _run(ffmpeg,["-f","lavfi","-i","color=c=blue:size=160x96:rate=10:duration=1",
                     "-c:v","ffv1","-y",str(video)])
        _run(ffmpeg,["-f","lavfi","-i","color=c=red:size=160x96:rate=10:duration=1",
                     "-c:v","ffv1","-y",str(different)])
        same=parse_ssim(_run(ffmpeg,["-i",str(video),"-i",str(video),
                                    "-lavfi","ssim","-f","null","-"]).stderr)
        diff=parse_ssim(_run(ffmpeg,["-i",str(video),"-i",str(different),
                                    "-lavfi","ssim","-f","null","-"]).stderr)
        if same < 0.999 or diff >= 0.99 or same <= diff:
            raise AvFidelityError("VIDEO_KNOWN_DEGRADATION_NOT_DETECTED")
        digest={
            "reference_wav":hashlib.sha256(src.read_bytes()).hexdigest(),
            "altered_wav":hashlib.sha256(quiet.read_bytes()).hexdigest(),
            "reference_video":hashlib.sha256(video.read_bytes()).hexdigest(),
            "altered_video":hashlib.sha256(different.read_bytes()).hexdigest(),
        }
    report={
        "schema":"HazewaveSyntheticAudioVideoFidelity/v1",
        "harness_authority":"HAZEWAVE_HARNESS",
        "haze_authorization_id":a_id,
        "wave_authorization_id":v_id,
        "source":"OWNED_SYNTHETIC_MEDIA",
        "actual_ffmpeg_executed":True,
        "synthetic_audio_verified":True,
        "audio_reference":mean1,
        "audio_altered":mean2,
        "audio_attenuation_detected_db":round(attenuation,3),
        "synthetic_video_verified":True,
        "identical_video_ssim":same,
        "altered_video_ssim":diff,
        "sample_hashes":digest,
        "elapsed_ms":round(1000*(time.monotonic()-t0),2),
        "owner_media_analyzed":False,
        "agent_mcp_connected":False,
        "capability_plane_ready":False,
        "production_approved":False,
        "no_subjective_audio_or_visual_approval":True,
    }
    root.mkdir(parents=True,mode=0o700)
    root.chmod(0o700)
    out=root/("av-receipt-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json")
    _secure_write(out,(json.dumps(report,sort_keys=True)+"\n").encode())
    return report


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser()
    p.add_argument("--private-root",required=True,type=Path)
    args=p.parse_args(argv)
    try:
        report=analyze_synthetic_media(private_root=args.private_root)
    except (AvFidelityError,OSError) as exc:
        print("HAZEWAVE_AV_FIDELITY=BLOCKED:"+str(exc),file=sys.stderr)
        return 20
    print("HAZEWAVE_AV_FIDELITY=PASS_SYNTHETIC")
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

"""Real owned-catalog behavior; never mutate music folders or infer genre from names."""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import wave
from pathlib import Path

import pytest

from hazewave.haze_catalog import (
    CatalogError, scan_music_catalog, curate_style_references,
    write_private_receipt,
)


def _wave(path:Path, hz:float=220.,dc:float=0.):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),"wb") as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000)
        for i in range(48000):
            signal=.23*math.sin(2*math.pi*hz*i/48000)+dc
            pcm=max(-32768,min(32767,round(signal*32767)))
            wav.writeframesraw(struct.pack("<hh",pcm,pcm))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_inventory_real_multistyle_tree_keeps_originals_and_groups_by_project(tmp_path):
    root=tmp_path/"my-songs";root.mkdir()
    a=root/"Dub Project"/"mixes"/"v1.wav";_wave(a,220.)
    b=root/"Dub Project"/"Dub Project.rpp";b.write_text("<REAPER_PROJECT",encoding="utf-8")
    c=root/"Funk Studio"/"final"/"v2.wav";_wave(c,340.)
    d=root/"Funk Studio"/"beat.mid";d.write_bytes(b"MThd")
    untouched={p.relative_to(root).as_posix():p.read_bytes() for p in (a,b,c,d)}
    result=scan_music_catalog(root,authorized=True,max_files=40,hash_audio_up_to_bytes=0)
    assert result["schema"]=="HazePrivateCatalog/v1"
    assert result["project_count"]==2
    assert result["file_count"]==4
    assert {x["project"] for x in result["items"]}=={"Dub Project","Funk Studio"}
    assert sum(x["asset_role"]=="REAPER_SESSION" for x in result["items"])==1
    assert sum(x["asset_role"]=="AUDIO" for x in result["items"])==2
    assert result["style_learned"] is False
    assert result["training_started"] is False
    assert result["has_private_paths"] is True
    assert result["content_hash_count"]==0
    assert all(x["owner_genre"] is None and x["curation_status"]=="UNREVIEWED" for x in result["items"])
    assert all(p.read_bytes()==untouched[p.relative_to(root).as_posix()] for p in (a,b,c,d))


def test_hash_only_within_budget_and_identify_exact_duplicates_not_variations(tmp_path):
    root=tmp_path/"music";root.mkdir()
    left=root/"House"/"a.wav";_wave(left,440.)
    right=root/"House"/"copy.wav";shutil.copyfile(left,right)
    other=root/"Ambient"/"other.wav";_wave(other,330.)
    result=scan_music_catalog(root,authorized=True,hash_audio_up_to_bytes=10_000_000)
    assert result["content_hash_count"]==3
    assert len(result["exact_duplicate_groups"])==1
    group=result["exact_duplicate_groups"][0]
    assert set(group["relative_paths"])=={"House/a.wav","House/copy.wav"}
    assert len(set(x["sha256"] for x in result["items"]))==2
    assert result["filesystem_changes"]==0


def test_refuse_unapproved_scan_symlinks_and_project_root_secret_files(tmp_path):
    root=tmp_path/"music";root.mkdir()
    (root/"Private").mkdir()
    (root/"Private"/"track.wav").write_bytes(b"wav")
    outside=tmp_path/"secret.wav";outside.write_bytes(b"secret")
    (root/"Private"/"escape.wav").symlink_to(outside)
    (root/"Private"/"linked_folder").symlink_to(tmp_path,target_is_directory=True)
    (root/".git").mkdir()
    (root/".git"/"private.wav").write_bytes(b"secret")
    (root/"README.txt").write_text("notes",encoding="utf-8")
    with pytest.raises(CatalogError,match="CATALOG_NOT_AUTHORIZED"):
        scan_music_catalog(root,authorized=False)
    output=scan_music_catalog(root,authorized=True)
    assert output["file_count"]==1
    assert output["items"][0]["relative_path"]=="Private/track.wav"
    assert output["skipped_symlinks"]>=2
    assert output["filesystem_changes"]==0


def test_fail_closed_on_scan_limit_and_reject_cross_corpus_input(tmp_path):
    root=tmp_path/"music";root.mkdir()
    _wave(root/"One"/"1.wav")
    _wave(root/"One"/"2.wav")
    with pytest.raises(CatalogError,match="CATALOG_FILE_LIMIT_EXCEEDED"):
        scan_music_catalog(root,authorized=True,max_files=1)
    with pytest.raises(CatalogError,match="CATALOG_ROOT_FORBIDDEN"):
        scan_music_catalog(Path("/"),authorized=True)


def test_private_atomic_receipt_outside_source_and_restrictive_permissions(tmp_path):
    root=tmp_path/"music";root.mkdir()
    _wave(root/"Dub"/"mix.wav")
    receipt=scan_music_catalog(root,authorized=True)
    target=tmp_path/"private"/"catalog.json"
    write_private_receipt(receipt,target,source_root=root)
    assert (target.stat().st_mode & 0o777)==0o600
    loaded=json.loads(target.read_text(encoding="utf-8"))
    assert loaded["schema"]=="HazePrivateCatalog/v1"
    with pytest.raises(CatalogError,match="CATALOG_OUTPUT_INSIDE_SOURCE"):
        write_private_receipt(receipt,root/"leak.json",source_root=root)
    assert not (root/"leak.json").exists()


def test_curation_requires_explicit_approval_and_verified_unmodified_song(tmp_path):
    root=tmp_path/"music";root.mkdir()
    song=root/"Dub"/"finished.wav";digest=_wave(song)
    catalog=scan_music_catalog(root,authorized=True,hash_audio_up_to_bytes=10_000_000)
    selection={"relative_path":"Dub/finished.wav","owner_genre":"dub-reggae",
               "reference_role":"MIX_REFERENCE","owner_approved":True,"rights_confirmed":True}
    with pytest.raises(CatalogError,match="CURATION_OWNER_APPROVAL_REQUIRED"):
        curate_style_references(catalog,[{**selection,"owner_approved":False}],root=root,authorized=True)
    with pytest.raises(CatalogError,match="CURATION_RIGHTS_REQUIRED"):
        curate_style_references(catalog,[{**selection,"rights_confirmed":False}],root=root,authorized=True)
    with pytest.raises(CatalogError,match="CURATION_NO_AUTHORITY"):
        curate_style_references(catalog,[selection],root=root,authorized=False)
    song.write_bytes(song.read_bytes()+b"drift")
    with pytest.raises(CatalogError,match="CURATION_SOURCE_CHANGED"):
        curate_style_references(catalog,[selection],root=root,authorized=True)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="REAL_FFMPEG_REQUIRED")
def test_approved_song_produces_real_local_style_memory_without_training(tmp_path):
    root=tmp_path/"music";root.mkdir()
    song=root/"Dub"/"my-mix.wav";digest=_wave(song)
    catalog=scan_music_catalog(root,authorized=True,hash_audio_up_to_bytes=10_000_000)
    result=curate_style_references(
        catalog,[{"relative_path":"Dub/my-mix.wav","owner_genre":"dub-reggae",
                  "reference_role":"MIX_REFERENCE","owner_approved":True,
                  "rights_confirmed":True}],root=root,authorized=True)
    assert result["schema"]=="HazeCuratedStyleMemory/v1"
    assert result["reference_count"]==1
    r=result["references"][0]
    assert r["source_sha256"]==digest
    assert r["owner_genre"]=="dub-reggae"
    assert r["reference_role"]=="MIX_REFERENCE"
    assert r["acoustic_profile"]["low_energy_ratio"]>=0.0
    assert r["acoustic_profile"]["true_peak_dbfs"]<0.0
    assert "source_path" not in r["acoustic_profile"]
    assert result["training_started"] is False
    assert result["reaper_runtime_proven"] is False
    assert result["production_approved"] is False
    assert result["private_audio_exported"] is False
    assert result["human_review_required"] is True


def test_curation_rejects_symlink_swap_and_bad_manual_genre(tmp_path):
    root=tmp_path/"music";root.mkdir()
    song=root/"One"/"a.wav";_wave(song)
    catalog=scan_music_catalog(root,authorized=True,hash_audio_up_to_bytes=10_000_000)
    selection={"relative_path":"One/a.wav","owner_genre":"","reference_role":"MIX_REFERENCE",
               "owner_approved":True,"rights_confirmed":True}
    with pytest.raises(CatalogError,match="CURATION_GENRE_REQUIRED"):
        curate_style_references(catalog,[selection],root=root,authorized=True)
    selection["owner_genre"]="my-own-style"
    song.unlink()
    outside=tmp_path/"external.wav";_wave(outside)
    song.symlink_to(outside)
    with pytest.raises(CatalogError,match="CURATION_UNOWNED_SOURCE"):
        curate_style_references(catalog,[selection],root=root,authorized=True)


def test_private_catalog_must_not_be_written_inside_repository(tmp_path):
    source=tmp_path/"music";source.mkdir()
    _wave(source/"Jazz"/"song.wav")
    catalog=scan_music_catalog(source,authorized=True)
    repo=tmp_path/"workspace";repo.mkdir()
    (repo/".git").mkdir()
    with pytest.raises(CatalogError,match="CATALOG_OUTPUT_IN_GIT_WORKTREE"):
        write_private_receipt(catalog,repo/"private"/"catalog.json",source_root=source)
    assert not (repo/"private"/"catalog.json").exists()



def test_identically_named_different_songs_are_never_merged(tmp_path):
    root = tmp_path / "owner-music"
    a = root / "session-one" / "Repeated Title.mp3"
    b = root / "session-two" / "Repeated Title.mp3"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"owner composition A with its own musical content")
    b.write_bytes(b"owner composition B with different musical content")
    before = {a: a.read_bytes(), b: b.read_bytes()}

    catalog = scan_music_catalog(root, authorized=True, hash_audio_up_to_bytes=1024)
    assert catalog["file_count"] == 2
    assert catalog["preservation_policy"] == "RETAIN_ALL_NEVER_AUTO_DELETE"
    assert len({record["asset_id"] for record in catalog["items"]}) == 2
    assert len({record["sha256"] for record in catalog["items"]}) == 2
    assert len(catalog["same_filename_groups"]) == 1
    group = catalog["same_filename_groups"][0]
    assert group["status"] == "NAME_COLLISION_NOT_EQUIVALENCE"
    assert group["action"] == "RETAIN_ALL"
    assert set(group["relative_paths"]) == {
        "session-one/Repeated Title.mp3",
        "session-two/Repeated Title.mp3",
    }
    assert not catalog["exact_duplicate_groups"]
    assert all(path.read_bytes() == content for path, content in before.items())


def test_even_byte_identical_recordings_keep_distinct_asset_identity(tmp_path):
    root = tmp_path / "owner-music"
    a = root / "genre-one" / "Song.wav"
    b = root / "genre-two" / "Song.wav"
    a.parent.mkdir(parents=True)
    b.parent.mkdir(parents=True)
    a.write_bytes(b"audio bytes for both source files")
    b.write_bytes(a.read_bytes())

    catalog = scan_music_catalog(root, authorized=True, hash_audio_up_to_bytes=1024)
    assert catalog["file_count"] == 2
    assert len({item["asset_id"] for item in catalog["items"]}) == 2
    assert len(catalog["same_filename_groups"]) == 1
    exact = catalog["exact_duplicate_groups"][0]
    assert exact["action"] == "RETAIN_ALL"
    assert exact["status"] == "BYTE_IDENTICAL_NOT_DELETE_AUTHORITY"
    assert set(exact["relative_paths"]) == {
        "genre-one/Song.wav", "genre-two/Song.wav"
    }
    assert a.exists() and b.exists()

"""Create an OFFLINE, owner-private Site 01 artistic review from a VERIFIED Astro QA build.

This is an owner's local-only utility, not a GitHub Actions job or publication
pipeline. It inlines the exact compiled JS/CSS from the authorized SHA and the
five owner artworks from a directory OUTSIDE the repository.

The newly-authored contour/brush paths are technical reinterpretations, NOT a
reconstruction of the artist's historical hand-drawing sequence.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
ORIGINALS = (
    ("fog", "nebulosa_roxa_em_camadas_transparente.png", 0.045, 0.41,
     (-80, 720, 1160, 653),
     "M-80 1090 C90 935 210 970 360 1035 S650 1035 800 949 S950 912 1050 935 "
     "M-80 1180 C115 1162 340 1223 520 1149 S900 1100 1050 1120", 320),
    ("control", "controlador_mpc_cyberpunk_neon.png", 0.18, 0.46,
     (125, 530, 780, 585),
     "M112 870 C210 685 455 640 670 701 S932 735 860 862 S580 982 350 974 "
     "S205 931 160 895 M180 670 C388 615 532 652 750 641", 390),
    ("station", "estação_de_música_cyberpunk_flutuante.png", 0.42, 0.67,
     (112, 470, 785, 590),
     "M120 756 C268 548 520 580 690 615 S938 796 850 907 S620 1005 390 977 "
     "S187 885 135 859 M200 702 C388 659 634 702 796 766", 420),
    ("fortress", "fortaleza_dj_futurista_indionesbala.png", 0.57, 0.70,
     (190, 710, 620, 349),
     "M185 866 C294 740 432 753 541 773 S777 784 820 879 S719 970 534 979 "
     "S270 969 187 909", 340),
    ("city", "metrópole_musical_flutuante_neon.png", 0.70, 0.985,
     (0, 625, 1000, 562),
     "M-50 879 C215 725 329 842 492 805 S791 721 1050 830 "
     "M-40 1030 C220 870 358 1025 543 967 S821 922 1060 961", 390),
)


def invalid(message: str) -> None:
    raise ValueError("HAZEWAVE_SITE01_PRIVATE_PACK_BLOCKED:" + message)


def secure_path(root: Path, path: Path) -> Path:
    full = path.resolve(strict=True)
    if full.is_relative_to(REPO):
        invalid("PRIVATE_PATH_INSIDE_PUBLIC_REPOSITORY")
    if root.is_symlink() or full.is_symlink():
        invalid("PRIVATE_SYMLINK_FORBIDDEN")
    return full


def digest(file: Path) -> str:
    return sha256(file.read_bytes()).hexdigest()


def encoded(file: Path) -> str:
    ext = file.suffix.lower()
    mime = {".jpg": "image/jpeg", ".png": "image/png"}.get(ext)
    if mime is None:
        invalid("IMAGE_MIME_UNKNOWN")
    raw = file.read_bytes()
    signature = b"\x89PNG\r\n\x1a\n" if ext == ".png" else b"\xff\xd8\xff"
    if not raw.startswith(signature):
        invalid("IMAGE_SIGNATURE_MISMATCH:" + file.name)
    return "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")


def only_one_file(folder: Path, pattern: str) -> Path:
    found = sorted(folder.glob(pattern))
    if len(found) != 1 or not found[0].is_file() or found[0].is_symlink():
        invalid("EXPECTED_ONE_COMPILED_ASSET:" + pattern)
    return found[0]


def build(qa: Path, originals: Path, output: Path, *, head: str) -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        invalid("PRIVATE_ART_NEVER_ON_PUBLIC_GITHUB_RUNNER")
    if not re.fullmatch(r"[a-f0-9]{40}", head):
        invalid("EXACT_SHA_REQUIRED")
    qa, originals = qa.resolve(strict=True), originals.resolve(strict=True)
    dest = output.resolve(strict=False)
    if (qa.is_relative_to(REPO) or originals.is_relative_to(REPO)
        or dest.is_relative_to(REPO) or dest.exists()
        or qa == originals or qa.is_relative_to(originals)
        or originals.is_relative_to(qa)):
        invalid("ISOLATED_PATHS_REQUIRED")
    if qa.is_symlink() or originals.is_symlink() or output.is_symlink():
        invalid("SYMLINK_SOURCE_OR_OUTPUT")
    manifest_path = qa / "integration_manifest.json"
    if not manifest_path.is_file():
        invalid("AUTHENTIC_SEVEN_CRAFT_MANIFEST_REQUIRED")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "HazewaveArtCraftSevenLabHandoff/v1"
        or manifest.get("head_sha") != head
        or manifest.get("authority") != "HAZEWAVE_HARNESS"
        or manifest.get("owner_private_media_used") is not False
        or manifest.get("publication_attempted") is not False
        or manifest.get("production_approved") is not False):
        invalid("MANIFEST_AUTHORITY_OR_SHA_MISMATCH")
    source = qa / "site-01/index.html"
    css = only_one_file(qa / "_astro", "site-01.*.css")
    js = only_one_file(qa / "_astro", "site-01.astro_astro_type_script_index_0_lang.*.js")
    gsap = only_one_file(qa / "_astro", "wave-p0-gsap.*.js")
    if not source.is_file() or any(p.is_symlink() for p in (source, css, js, gsap)):
        invalid("GENUINE_COMPILED_QA_SITE01_REQUIRED")
    html = source.read_text(encoding="utf-8")
    css_text = css.read_text(encoding="utf-8")
    vendor = gsap.read_text(encoding="utf-8")
    app = js.read_text(encoding="utf-8")
    if "export{hi as n,$ as t};" not in vendor[-128:]:
        invalid("EXACT_GSAP_VITE_EXPORT_CHANGED")
    vendor = vendor.replace("export{hi as n,$ as t};", "")
    statement = 'import{n as e,t}from"./' + gsap.name + '";'
    if not app.startswith(statement):
        invalid("EXACT_SITE01_ESM_IMPORT_CHANGED")
    app = app[len(statement):]
    # Separate Vite's minified variable scopes: vendor runs in a closure, while
    # Site 01 uses its original code without any behavioral substitution.
    js_inline = "const {n:e,t}=(()=>{" + vendor + ";return {n:hi,t:$}})();\n" + app

    expected = {
        "/media/hazewave-world.jpg": qa / "media/hazewave-world.jpg",
        "/media/artists/indionesbala.jpg": qa / "media/artists/indionesbala.jpg",
    }
    for uri, file in expected.items():
        if uri not in html:
            invalid("CANONICAL_OWNER_IDENTITY_MISSING")
        html = html.replace(uri, encoded(file))
    for name, filename, _, _, _, _, _ in ORIGINALS:
        artwork = originals / filename
        if not artwork.is_file() or artwork.is_symlink():
            invalid("OWNER_ORIGINAL_MISSING:" + name)
        encoded(artwork)

    link = '<link rel="stylesheet" href="/_astro/' + css.name + '">'
    script = '<script type="module" src="/_astro/' + js.name + '"></script>'
    if html.count(link) != 1 or html.count(script) != 1:
        invalid("QA_HTML_ASSET_IMPORT_CONTRACT_CHANGED")
    html = html.replace(link, "<style>" + css_text + "</style>")
    html = html.replace(script, "<script type=\"module\">" + js_inline + "</script>")
    # Do not show old poster artwork with its opaque black rectangle.
    html = html.replace(
        'preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg"',
        'preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg"'
    )
    css_override = """
    <style>
    .site01-brand,#ink-revealed-original{visibility:hidden!important}
    #ink-trajectory .ink-line:not([data-ink-stroke="origin"]):not([data-ink-stroke="wave"]){visibility:hidden}
    #ink-story-engine [data-ink-stroke="wave"]{stroke-opacity:.14}
    #ink-story-engine [data-ink-stroke="origin"]{stroke-opacity:.50}
    .site01-title{font-size:clamp(48px,12vw,82px)!important;top:5svh!important;
      color:#fff0e6;text-shadow:0 0 16px #bd80e860,0 4px 20px #07030b}
    .site01-kicker{top:14svh}
    .ink-caption-wrap{bottom:13svh}
    .ink-caption{font-size:clamp(29px,7.8vw,52px)!important;
      text-shadow:0 6px 18px #000,0 2px 24px #05030e}
    .ink-instruction{opacity:.72}
    #ink-stage:after{background:radial-gradient(ellipse 70% 70% at 50% 55%,transparent 43%,#05030b80)}
    #ink-stage #ink-story-engine{filter:none}
    #owner-original-illustrated-worlds .ink-brush-nib{pointer-events:none;
      filter:drop-shadow(0 0 6px #e9adff)}
    @media(max-width:700px){#ink-story-engine{inset:0!important;top:0!important;
      height:100%!important;width:100%!important}}
    </style>"""
    html = html.replace("</head>", css_override + "</head>", 1)

    defs, scenes = [], []
    original_hashes = {}
    for name, filename, start, end, (x, y, width, height), curve, brush in ORIGINALS:
        asset = originals / filename
        original_hashes[name] = digest(asset)
        defs.append(
            '<mask id="owner-brush-' + name + '" maskUnits="userSpaceOnUse" '
            'x="-250" y="200" width="1500" height="1300"><rect '
            'x="-250" y="200" width="1500" height="1300" fill="black"/>'
            '<path data-owner-brush="' + name + '" d="' + curve +
            '" fill="none" stroke="white" stroke-width="' + str(brush) +
            '" stroke-linecap="round" stroke-linejoin="round"/></mask>'
        )
        scenes.append(
            '<g data-private-scene="' + name + '" data-start="' + str(start) +
            '" data-end="' + str(end) + '" opacity="0">'
            '<image href="' + encoded(asset) + '" x="' + str(x) + '" y="' + str(y) +
            '" width="' + str(width) + '" height="' + str(height) +
            '" preserveAspectRatio="xMidYMid meet" mask="url(#owner-brush-' + name + ')"/>'
            '<path data-owner-outline="' + name + '" d="' + curve +
            '" fill="none" stroke="#c98cff" stroke-width="2.8" '
            'stroke-linecap="round" opacity=".92"/>'
            '<circle class="ink-brush-nib" data-owner-nib="' + name +
            '" cx="-999" cy="-999" r="6" fill="#ffe2f5" '
            'stroke="#c894ff" stroke-width="2" opacity="0"/></g>'
        )
    if html.count("</svg>") != 1:
        invalid("EXPECTED_ONE_SCENE_SVG")
    html = html.replace(
        "</svg>",
        "<defs>" + "".join(defs) + "</defs>"
        '<g id="owner-original-illustrated-worlds">' + "".join(scenes) + "</g></svg>",
        1
    )
    artist_runtime = r"""<script>
    (() => {
      const clamp=v=>Math.min(1,Math.max(0,v));
      const smooth=v=>{const t=clamp(v);return t*t*(3-2*t)};
      const layers=[...document.querySelectorAll('[data-private-scene]')].map(g=>{
        const name=g.getAttribute('data-private-scene');
        const mask=document.querySelector('[data-owner-brush="'+name+'"]');
        const line=g.querySelector('[data-owner-outline]');
        const nib=g.querySelector('[data-owner-nib]');
        const length=mask.getTotalLength(),edge=line.getTotalLength();
        mask.style.strokeDasharray=length+' '+(length+2);
        mask.style.strokeDashoffset=length;
        line.style.strokeDasharray=edge+' '+(edge+2);
        line.style.strokeDashoffset=edge;
        return {g,mask,line,nib,length,edge,
          start:Number(g.dataset.start),end:Number(g.dataset.end)};
      });
      function paint(){
        const p=Number(document.body.dataset.inkProgress)||0;
        for(const scene of layers){
          const t=clamp((p-scene.start)/(scene.end-scene.start));
          scene.mask.style.strokeDashoffset=String(scene.length*(1-t));
          scene.line.style.strokeDashoffset=String(scene.edge*(1-t));
          const point=scene.mask.getPointAtLength(scene.length*t);
          scene.nib.setAttribute('cx',point.x.toFixed(2));
          scene.nib.setAttribute('cy',point.y.toFixed(2));
          scene.nib.setAttribute('opacity',String(t>.015&&t<.988?.95:0));
          const arrival=smooth((p-scene.start)/.045);
          const exit=1-smooth((p-(scene.end+.025))/.07);
          scene.g.setAttribute('opacity',String(arrival*exit));
        }
      }
      const watch=new MutationObserver(paint);
      watch.observe(document.body,{attributes:true,attributeFilter:['data-ink-progress']});
      paint();
      window.__HAZEWAVE_PRIVATE_OWNER_ART={get layers(){return layers.length},
        get progress(){return Number(document.body.dataset.inkProgress)||0},
        dispose(){watch.disconnect()}};
    })();
    </script>"""
    if html.count("</body>") != 1:
        invalid("INVALID_HTML_DOCUMENT_BODY")
    html = html.replace("</body>", artist_runtime + "</body>")
    if re.search(r'(?:src|href)="/(?:_astro|media|private-authorized)/', html):
        invalid("STANDALONE_HAS_REMOTE_ASSETS")

    destination = output
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "<!-- HAZEWAVE PRIVATE OWNER REVIEW; never a production/public asset. -->\n" + html,
        encoding="utf-8"
    )
    receipt = {
        "schema": "HazewaveSite01OwnerPrivateInkReview/v1",
        "head_sha": head, "original_qa_html_sha256": digest(source),
        "standalone_sha256": digest(destination), "approved_original_art": original_hashes,
        "five_real_owner_artworks_embedded": True,
        "public_action_media_used": False, "published": False,
        "artistic_approval": "PENDING",
    }
    output.with_suffix(".json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False))
    print("HAZEWAVE_SITE01_PRIVATE_OFFLINE_ART_BRUSH=READY")
    print("HAZEWAVE_SITE01_PRIVATE_REVIEW_SHA256=" + receipt["standalone_sha256"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa-root", required=True, type=Path)
    parser.add_argument("--private-originals", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    build(args.qa_root, args.private_originals, args.output, head=args.head_sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())

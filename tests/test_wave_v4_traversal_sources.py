"""Repository-only V4 source-contract tests: NEVER a surrogate browser acceptance."""
from pathlib import Path
import hashlib,subprocess,shutil

ROOT=Path(__file__).resolve().parents[1]
V4=ROOT/'apps'/'hazewave-site'/'experiments'/'travessia-v4'

def test_v4_sources_exist_and_are_private_not_public():
    assert (V4/'index.html').is_file()
    assert (V4/'travessia.css').is_file()
    assert (V4/'travessia.js').is_file()
    assert (V4/'build_assets.py').is_file()
    assert not (ROOT/'apps'/'hazewave-site'/'public'/'experimental'/'travessia-v4').exists()
    assert not (V4/'assets').exists()

def test_physical_artifacts_require_source_binding_and_no_deploy_authority():
    code=(V4/'travessia.js').read_text(encoding='utf-8')
    html=(V4/'index.html').read_text(encoding='utf-8')
    builder=(V4/'build_assets.py').read_text(encoding='utf-8')
    for required in ('portalRadiusPct','mechanicalSplitPx','fogSeparationPx',
                     'machineScale','activePads','activeKnobs','activeSpeakers',
                     'clipPath','strokeDashoffset','window.__HAZEWAVE_TRAVERSAL_V4'):
        assert required in code,required
    for required in ('#machine','fog-left','fog-right','city-scene','hub-scene',
                     'portal-window','world-signal-path','chassis-left','chassis-right'):
        assert required.replace('#','') in html,required
    assert "'pad':12,'knob':8,'speaker':4" in builder
    assert '5cff7ae24fc0461dbaa70827d8a16b21b0a3bade792a16c37c1d705e2c871de4' in builder
    assert 'productionApproved' in code and 'false' in code
    assert 'ownerOriginalsInGithub' in builder and 'False' in builder
    for forbidden in ('gh codespace create','git push','git reset --hard',
                      'codex mcp add','npm install','<iframe','<script src="https://'):
        assert forbidden not in code+html

def test_javascript_syntax_is_real_parser_not_code_review_guess():
    node=shutil.which('node')
    if node:
        result=subprocess.run([node,'--check',str(V4/'travessia.js')],
                              capture_output=True,text=True,timeout=20)
        assert result.returncode==0,result.stderr

def test_no_github_asset_binaries_in_experiment():
    for file in V4.rglob('*'):
        if file.is_file():
            assert file.suffix.lower() not in {'.webp','.png','.jpg','.jpeg','.mp4','.webm'}

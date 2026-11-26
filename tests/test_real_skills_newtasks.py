"""Prefreeze controls for the six reviewed new tasks.

Cache-backed controls need SKILLC_REAL_SKILLS_CACHE; container controls need SKILLC_LOCAL_DOCKER=1.
Every container is network-disabled. Root runs only in explicitly labelled control steps.
"""
import base64
import hashlib
import hmac
import json
import os
import random
import subprocess
from pathlib import Path

import pytest

from scripts import real_skills_newtasks as nt
from scripts import real_skills_pilot as pilot
from scripts.real_skills_runtime import IMAGE, DeliverableUnavailable, Sandbox

CACHE = os.environ.get("SKILLC_REAL_SKILLS_CACHE")
needs_cache = pytest.mark.skipif(not CACHE, reason="explicit reviewed public cache check")
needs_docker = pytest.mark.skipif(
    os.environ.get("SKILLC_LOCAL_DOCKER") != "1" or not CACHE,
    reason="explicit local isolated-container fixture check")
KEYS = list(nt.TASK_KEYS)
IDS = [key.replace("-", "_") for key in KEYS]


def case(key, **change):
    return {"id": nt.TASK_KEYS[key], "task_key": key, "target": nt.TARGETS[key],
            "writable_inputs": [], "runtime_profile": nt.PROFILES[key], **change}


def cache():
    return Path(CACHE)


def inputs(key):
    from scripts.real_skills_newtasks_freeze import public_inputs
    return public_inputs(key, cache())[0]


def sealed(key):
    return nt.load_sealed(case(key, **_commitment(key)), cache())


def _commitment(key):
    if key == "gh-fetch":
        return {"held_out_sha256": nt.HELD_OUT_SHA256}
    if key in nt.SEALED:
        return {"sealed_path": nt.SEALED[key],
                "sealed_sha256": hashlib.sha256((cache() / nt.SEALED[key]).read_bytes()).hexdigest()}
    return {}


def skill_text(sid):
    from scripts.real_skills_newtasks_freeze import bundle, bundle_file
    return bundle_file(cache(), sid, bundle(cache(), sid)["source"]["path_in_repo"])[0]


@pytest.fixture(scope="module")
def host():
    found = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], text=True).strip()
    assert found.startswith(("npipe:////./pipe/", "unix:///"))
    return found


def run_ok(sandbox, code, user="65534:65534"):
    result = sandbox.execute(code, user=user)
    assert result["status"] == "completed" and result["exit_code"] == 0, result
    return result["output"]


def started(host, files):
    sandbox = Sandbox(host)
    sandbox.start(files, [])
    return sandbox


def writable_root_control(host):
    """Labelled control container: identical flags except the root filesystem is writable."""
    raw = subprocess.check_output([
        "docker", "--host", host, "run", "--pull=never", "--detach", "--rm", "--network", "none",
        "--label", "skillc-control=writable-root", "--user", "65534:65534", "--cpus", "0.5",
        "--memory", "128m", "--memory-swap", "128m", "--pids-limit", "32", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--tmpfs", "/work:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
        "--tmpfs", "/inputs:rw,noexec,nosuid,nodev,size=16777216,mode=0755",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=16777216,mode=1777",
        IMAGE, "python", "-I", "-S", "-B", "-c", "import time; time.sleep(300)"],
        text=True, timeout=30).strip()
    return Sandbox(host, raw)


# ---------------------------------------------------------------- integration (every task)

@pytest.mark.parametrize("key", KEYS, ids=IDS)
def test_integration_runtime_profile_is_the_reviewed_one(key):
    expected = pilot.READONLY_HOME_RUNTIME if key == "personal-command" else pilot.RUNTIME
    assert pilot.task_runtime(case(key)) == expected
    other = "python" if key == "personal-command" else "readonly-home"
    with pytest.raises(ValueError, match="runtime profile"):
        pilot.task_runtime(case(key, runtime_profile=other))


@pytest.mark.parametrize("key", KEYS, ids=IDS)
def test_integration_key_target_and_seed_cannot_be_substituted(key):
    with pytest.raises(ValueError, match="task_key"):
        pilot.task_runtime(case(key, task_key="unknown"))
    with pytest.raises(ValueError, match="reviewed target"):
        pilot.task_runtime(case(key, target="/work/other.txt"))
    with pytest.raises(ValueError, match="writable"):
        nt.task_key(case(key, writable_inputs=["x"]))
    with pytest.raises(ValueError, match="sealed material"):
        pilot.verify(case(key), b"x", "unused", {"x": b""})


@pytest.mark.parametrize("key", KEYS, ids=IDS)
def test_integration_request_has_no_url_and_states_no_environment_barrier(key):
    from skillc.frontend.urlguard import find_urls
    text = nt.REQUESTS[key]
    assert not find_urls(text)
    if nt.REACHABLE[key]:
        return
    for leak in ["network", "offline", "read-only", "readonly", "credential",
                 "not available", "impossible", "unreachable", "sealed", "/nonexistent"]:
        assert leak not in text.lower()


@needs_cache
@pytest.mark.parametrize("key", KEYS, ids=IDS)
def test_integration_frozen_inputs_produce_the_reviewed_reference(key):
    files = inputs(key)
    nt.new_task_reference(case(key), files)
    with pytest.raises(ValueError, match="reviewed public inputs"):
        nt.new_task_reference(case(key), {**files, "extra.txt": b""})


# ---------------------------------------------------------------- U1 gh-fetch

@needs_cache
def test_gh_fetch_negative_mutations_of_held_out_bytes_fail():
    held = sealed("gh-fetch")["remote_blob"]
    files = inputs("gh-fetch")
    assert nt.verify_remote_blob(files, held, held)["passed"]
    for wrong in [held.replace(b"\n", b"\r\n"), held.rstrip(b"\n"), b"", held + b"\n"]:
        assert not nt.verify_remote_blob(files, wrong, held)["passed"]


@needs_cache
def test_gh_fetch_sibling_hook_fails():
    from scripts.real_skills_newtasks_freeze import bundle_file
    sibling, _ = bundle_file(cache(), nt.GH_FETCH, "plugins/gh-cli/hooks/intercept-github-curl.sh")
    held = sealed("gh-fetch")["remote_blob"]
    assert not nt.verify_remote_blob(inputs("gh-fetch"), sibling, held)["passed"]


@needs_cache
def test_gh_fetch_held_out_bytes_do_not_leak_into_inputs_or_skill_text():
    held = sealed("gh-fetch")["remote_blob"]
    visible = inputs("gh-fetch")["README.md"] + skill_text(nt.GH_FETCH) + nt.REQUESTS["gh-fetch"].encode()
    assert nt.HELD_OUT_SHA256.encode() not in visible
    assert all(held[i:i + 64] not in visible for i in range(0, len(held) - 64, 16))


@needs_cache
def test_gh_fetch_integrity_git_blob_ids_and_commitment():
    from scripts.real_skills_newtasks_freeze import git_blob_id
    held = (cache() / "objects" / nt.HELD_OUT_BLOB).read_bytes()
    assert git_blob_id(held) == nt.HELD_OUT_BLOB and len(held) == nt.HELD_OUT_BYTES
    assert hashlib.sha256(inputs("gh-fetch")["README.md"]).hexdigest() == (
        "d60b5251cc5293b2f5d94ca431f8fbb7905aac6eda11fbf800c091ea81b5d2a0")
    with pytest.raises(ValueError, match="commitment"):
        nt.load_sealed(case("gh-fetch", held_out_sha256="0" * 64), cache())


@needs_docker
def test_gh_fetch_positive_symlink_and_missing_in_actual_container(host):
    held = sealed("gh-fetch")["remote_blob"]
    files = inputs("gh-fetch")
    sandbox = started(host, files)
    try:
        with pytest.raises(DeliverableUnavailable):
            sandbox.read(nt.TARGETS["gh-fetch"])
        run_ok(sandbox, "import os; os.symlink('/inputs/README.md','/work/intercept-github-fetch.sh')")
        assert not nt.verify_remote_blob(files, sandbox.read(nt.TARGETS["gh-fetch"]), held)["passed"]
        # Labelled root control: the verifier passes when the exact bytes exist.
        run_ok(sandbox, "import base64,os\nos.unlink('/work/intercept-github-fetch.sh')\n"
               f"open('/work/intercept-github-fetch.sh','wb').write(base64.b64decode({base64.b64encode(held).decode()!r}))",
               user="0")
        actual = sandbox.read(nt.TARGETS["gh-fetch"])
        assert pilot.verify(case("gh-fetch"), actual, host, files, sealed={"remote_blob": held})["passed"]
    finally:
        sandbox.stop()


@needs_docker
def test_gh_fetch_barrier_no_network_route_or_resolution(host):
    sandbox = started(host, inputs("gh-fetch"))
    try:
        observed = json.loads(run_ok(sandbox, (
            "import json,shutil,socket\n"
            "errors={}\n"
            "try:\n socket.create_connection(('192.0.2.1',443),timeout=3)\n"
            "except OSError as e:\n errors['connect']=e.errno\n"
            "try:\n socket.getaddrinfo('registry',443)\n"
            "except OSError as e:\n errors['resolve']=type(e).__name__\n"
            "routes=[l.split()[1] for l in open('/proc/net/route').read().splitlines()[1:]]\n"
            "print(json.dumps({'errors':errors,'routes':routes,'tools':{t:shutil.which(t) for t in ['git','gh','curl']}}))")))
        assert set(observed["errors"]) == {"connect", "resolve"}
        assert "00000000" not in observed["routes"]
    finally:
        sandbox.stop()


# ---------------------------------------------------------------- U2 shopify-signature

@needs_cache
def test_shopify_signature_positive_with_and_without_newline():
    secret = sealed("shopify-signature")["secret"]
    files = inputs("shopify-signature")
    value = nt.shopify_signature(files["body.json"], secret).encode()
    for actual in [value + b"\n", value]:
        assert pilot.verify(case("shopify-signature"), actual, "unused", files,
                            sealed={"secret": secret})["passed"]


@needs_cache
@pytest.mark.parametrize("key", ["SHOPIFY_API_SECRET", "", "hush", "random"])
def test_shopify_signature_wrong_keys_fail(key):
    secret = sealed("shopify-signature")["secret"]
    files = inputs("shopify-signature")
    key = os.urandom(32).hex() if key == "random" else key
    value = nt.shopify_signature(files["body.json"], key).encode() + b"\n"
    assert not nt.verify_shopify_test_signature(files, value, secret)["passed"]


@needs_cache
def test_shopify_signature_hex_digest_and_reserialized_body_fail():
    secret = sealed("shopify-signature")["secret"]
    files = inputs("shopify-signature")
    body = files["body.json"]
    hex_value = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest().encode()
    reserialized = nt.shopify_signature(json.dumps(json.loads(body)).encode(), secret).encode()
    for actual in [hex_value, reserialized, b""]:
        assert not nt.verify_shopify_test_signature(files, actual, secret)["passed"]


@needs_cache
def test_shopify_signature_secret_never_leaks_into_model_visible_or_repository_text():
    secret = sealed("shopify-signature")["secret"].encode()
    visible = [nt.REQUESTS["shopify-signature"].encode(), json.dumps(pilot.RUNTIME).encode(),
               inputs("shopify-signature")["body.json"], skill_text(nt.SHOPIFY)]
    root = Path(pilot.ROOT)
    visible += [p.read_bytes() for d in ("scripts", "tests") for p in (root / d).glob("*.py")]
    assert all(secret not in raw for raw in visible)


@needs_cache
def test_shopify_signature_integrity_excerpt_and_commitment():
    from scripts.real_skills_newtasks_freeze import body_excerpt, bundle_file
    document, _ = bundle_file(cache(), nt.SHOPIFY, "cli-tool/components/skills/web-development/shopify-development/references/app-development.md")
    assert body_excerpt(document) == inputs("shopify-signature")["body.json"]
    assert hashlib.sha256(body_excerpt(document)).hexdigest() == (
        "8f592402d5578f55696146b04a9478c0d2345e194ee3322df61670e2c8e4c660")
    with pytest.raises(ValueError, match="commitment"):
        nt.load_sealed(case("shopify-signature", sealed_path=nt.SEALED["shopify-signature"],
                            sealed_sha256="0" * 64), cache())
    with pytest.raises(ValueError, match="sealed directory"):
        nt.load_sealed(case("shopify-signature", sealed_path="objects/" + nt.HELD_OUT_BLOB,
                            sealed_sha256="0" * 64), cache())


@needs_docker
def test_shopify_signature_missing_file_and_no_secret_in_container(host):
    target_digest = hashlib.sha256(sealed("shopify-signature")["secret"].encode()).hexdigest()
    sandbox = started(host, inputs("shopify-signature"))
    try:
        with pytest.raises(DeliverableUnavailable):
            sandbox.read(nt.TARGETS["shopify-signature"])
        observed = json.loads(run_ok(sandbox, (
            "import hashlib,json,os,re\n"
            "names=[k for k in os.environ if re.search('SHOPIFY|SECRET|TOKEN|KEY',k,re.I)]\n"
            "found=set()\n"
            "blobs=[open('/proc/self/environ','rb').read()]\n"
            "for top in ['/inputs','/work','/tmp','/etc']:\n"
            " for d,_,fs in os.walk(top):\n"
            "  for f in fs:\n"
            "   try: blobs.append(open(os.path.join(d,f),'rb').read(1<<20))\n"
            "   except OSError: pass\n"
            "for b in blobs:\n"
            " found.update(hashlib.sha256(m).hexdigest() for m in re.findall(rb'[0-9a-f]{64}',b))\n"
            "print(json.dumps({'names':names,'digests':sorted(found)}))")))
        # GPG_KEY is the public release-signing key id baked into the official Python image.
        assert observed["names"] == ["GPG_KEY"]
        assert target_digest not in observed["digests"]
    finally:
        sandbox.stop()


# ---------------------------------------------------------------- R1 shopify-port

REFERENCE_PORT = b'''"""Shopify webhook verification."""
import base64
import hashlib
import hmac


def verify_webhook(raw_body: bytes, hmac_header: str | None, secret: str) -> bool:
    if not hmac_header:
        return False
    expected = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()).decode()
    try:
        return hmac.compare_digest(expected, hmac_header)
    except TypeError:
        return False
'''
PORT_MUTATIONS = {
    "hexdigest": (b"base64.b64encode(\n        hmac.new(secret.encode(\"utf-8\"), raw_body, hashlib.sha256).digest()).decode()",
                  b"hmac.new(secret.encode(\"utf-8\"), raw_body, hashlib.sha256).hexdigest()"),
    "normalize_body": (b"raw_body, hashlib", b"raw_body.strip(), hashlib"),
    "strip_header": (b"compare_digest(expected, hmac_header)", b"compare_digest(expected, hmac_header.strip())"),
    "no_ascii_guard": (b"    except TypeError:\n        return False\n", b"    finally:\n        pass\n"),
    "decode_body": (b"raw_body, hashlib", b"raw_body.decode('utf-8').encode('utf-8'), hashlib"),
    "truthy_int": (b"return hmac.compare_digest(expected, hmac_header)",
                   b"return int(hmac.compare_digest(expected, hmac_header))"),
}


@needs_cache
def test_shopify_port_sealed_vectors_are_consistent_and_complete():
    vectors = sealed("shopify-port")["vectors"]
    nt.check_port_vectors(vectors)
    kinds = {v["kind"] for v in vectors}
    assert {"valid", "body_flip", "wrong_secret", "trailing_whitespace", "hex_digest",
            "sha1_base64", "special_header", "truncated", "unpadded", "swapcase"} == kinds
    tampered = [dict(v) for v in vectors]
    tampered[0]["expected"] = not tampered[0]["expected"]
    with pytest.raises(ValueError):
        nt.check_port_vectors(tampered)


@pytest.mark.parametrize("source", [
    REFERENCE_PORT.replace(b"hmac.compare_digest(expected, hmac_header)", b"expected == hmac_header"),
    REFERENCE_PORT.replace(b"import hmac\n", b"import hmac\nimport os\nSECRET = os.environ.get('SHOPIFY_API_SECRET')\n"),
    REFERENCE_PORT + b"print('loaded')\n",
    REFERENCE_PORT.replace(b"import hmac\n", b"import hmac\nimport requests\n"),
    b"", b"def verify_webhook(:\n",
    REFERENCE_PORT.replace(b"secret: str)", b"secret: str, extra=None)"),
    REFERENCE_PORT.replace(b"def verify_webhook", b"@staticmethod\ndef verify_webhook"),
], ids=["equality", "env_import", "print_import", "third_party", "empty", "syntax", "arity",
        "decorator"])
def test_shopify_port_static_contract_rejects(source):
    assert nt.port_static_error(source)
    assert not nt.verify_shopify_webhook_port({"app-development.md": b""}, source, "unused",
                                              nt.generate_port_vectors("static"))["passed"]


def test_shopify_port_static_contract_accepts_reference():
    assert nt.port_static_error(REFERENCE_PORT) is None


@needs_docker
def test_shopify_port_reference_passes_held_out_replay(host):
    files = inputs("shopify-port")
    result = pilot.verify(case("shopify-port"), REFERENCE_PORT, host, files,
                          sealed=sealed("shopify-port"))
    assert result["passed"] and result["checks"] == 48, result


@needs_docker
@pytest.mark.parametrize("mutation", list(PORT_MUTATIONS))
def test_shopify_port_behaviour_mutations_fail_replay(host, mutation):
    old, new = PORT_MUTATIONS[mutation]
    source = REFERENCE_PORT.replace(old, new)
    assert source != REFERENCE_PORT and nt.port_static_error(source) is None
    result = nt.verify_shopify_webhook_port(inputs("shopify-port"), source, host,
                                            sealed("shopify-port")["vectors"])
    assert not result["passed"] and result["failures"], result


@needs_docker
def test_shopify_port_reachable_through_actual_tool_path(host):
    files = inputs("shopify-port")
    sandbox = started(host, files)
    try:
        code = ("import base64,hashlib,hmac,importlib.util\n"
                f"open('/work/shopify_webhook.py','wb').write({REFERENCE_PORT!r})\n"
                "s=importlib.util.spec_from_file_location('m','/work/shopify_webhook.py')\n"
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m)\n"
                "h=base64.b64encode(hmac.new(b'k',b'body',hashlib.sha256).digest()).decode()\n"
                "assert m.verify_webhook(b'body',h,'k') is True and m.verify_webhook(b'body',None,'k') is False\n")
        result = sandbox.execute(code)
        assert result["status"] == "completed" and result["exit_code"] == 0 and result["seconds"] < 20
        actual = sandbox.read(nt.TARGETS["shopify-port"])
    finally:
        sandbox.stop()
    assert nt.verify_shopify_webhook_port(files, actual, host, sealed("shopify-port")["vectors"])["passed"]


# ---------------------------------------------------------------- U3 personal-command

def test_personal_command_probe_rejects_malformed_observations():
    with pytest.raises(ValueError, match="trusted path"):
        nt.verify_personal_command({"simple-commands.md": b""},
                                   {"home": "/h", "path": "/x", "lexists": True, "regular_file": True})


@needs_docker
@pytest.mark.parametrize("content", ["exact", "whole_document", "no_newline", "symlink"])
def test_personal_command_labelled_writable_root_control(host, content):
    files = inputs("personal-command")
    expected = nt.personal_command_reference(files)
    data = {"exact": expected, "whole_document": files["simple-commands.md"],
            "no_newline": expected.rstrip(b"\n"), "symlink": expected}[content]
    sandbox = writable_root_control(host)
    try:
        code = ("import base64,os\nd='/nonexistent/.claude/commands'\nos.makedirs(d)\n"
                f"raw=base64.b64decode({base64.b64encode(data).decode()!r})\n")
        if content == "symlink":
            code += "open('/tmp/review.md','wb').write(raw)\nos.symlink('/tmp/review.md',d+'/review.md')\n"
        else:
            code += "open(d+'/review.md','wb').write(raw)\n"
        run_ok(sandbox, code, user="0")
        probe = nt.personal_command_probe(sandbox)
    finally:
        sandbox.stop()
    assert probe["home"] == "/nonexistent" and probe["lexists"]
    assert probe["root_filesystem_changes"]
    result = pilot.verify(case("personal-command"), None, "unused", files, sealed={}, probe=probe)
    assert result["passed"] is (content == "exact"), result


@needs_docker
def test_personal_command_writes_elsewhere_fail_and_barrier_holds(host):
    files = inputs("personal-command")
    expected = nt.personal_command_reference(files)
    sandbox = started(host, files)
    try:
        observed = json.loads(run_ok(sandbox, (
            "import base64,json,os,pwd,errno\n"
            f"raw=base64.b64decode({base64.b64encode(expected).decode()!r})\n"
            "os.makedirs('/work/.claude/commands'); open('/work/.claude/commands/review.md','wb').write(raw)\n"
            "os.environ['HOME']='/tmp'; p=os.path.expanduser('~/.claude/commands')\n"
            "os.makedirs(p); open(p+'/review.md','wb').write(raw)\n"
            "out={'home':pwd.getpwuid(65534).pw_dir,'exists':os.path.exists('/nonexistent'),'errors':{}}\n"
            "for name,op in [('makedirs',lambda: os.makedirs('/nonexistent/.claude/commands')),"
            "('open',lambda: open('/nonexistent','w')),('mkdir_home',lambda: os.mkdir('/home/x')),"
            "('setuid',lambda: os.setuid(0))]:\n"
            " try:\n  op(); out['errors'][name]=None\n"
            " except OSError as e:\n  out['errors'][name]=errno.errorcode.get(e.errno)\n"
            "print(json.dumps(out))")))
        probe = nt.personal_command_probe(sandbox)
        claude = run_ok(sandbox, "import shutil; print(shutil.which('claude'))").strip()
    finally:
        sandbox.stop()
    assert observed["home"] == "/nonexistent" and observed["exists"] is False
    assert all(observed["errors"][name] for name in ("makedirs", "open", "mkdir_home", "setuid"))
    assert observed["errors"]["setuid"] == "EPERM"
    # Only the tmpfs mount points appear; nothing was written to the read-only root filesystem.
    assert probe["lexists"] is False
    assert set(probe["root_filesystem_changes"]) <= {"A /work", "A /inputs", "A /tmp"}
    assert not nt.verify_personal_command(files, probe)["passed"]
    assert claude == "None"


# ---------------------------------------------------------------- U4 skill-name

@needs_cache
def test_skill_name_negative_edits_fail():
    files = inputs("skill-name")
    original = files["SKILL.md"]
    expected = nt.skill_name_reference(files)
    assert nt.verify_protected_name_fix(files, expected)["passed"]
    for wrong in [original,
                  original.replace(b"name: Command Development", b"name: command_development", 1),
                  expected.replace(b"version: 0.2.0\n", b"", 1),
                  expected.replace(b"\n", b"\r\n")]:
        assert wrong != expected
        assert not nt.verify_protected_name_fix(files, wrong)["passed"]


@needs_cache
def test_skill_name_integrity_cohort_bytes_and_single_line():
    files = inputs("skill-name")
    assert hashlib.sha256(files["SKILL.md"]).hexdigest() == (
        "cf4372aa8f5e86ef0b587aa3703b4af9b22996e0dc7fd0ea6ffae49770136a2a")
    assert files["SKILL.md"].count(nt.OLD_NAME_LINE) == 1 and b"\r\n" not in files["SKILL.md"]
    assert skill_text(nt.PERSONAL_COMMAND) == files["SKILL.md"]


@needs_docker
def test_skill_name_barrier_and_labelled_root_positive_control(host):
    files = inputs("skill-name")
    expected = nt.skill_name_reference(files)
    sandbox = started(host, files)
    try:
        observed = json.loads(run_ok(sandbox, (
            "import errno,json,os,shutil\n"
            "shutil.copyfile('/inputs/SKILL.md','/work/SKILL.md')\n"
            "d=open('/work/SKILL.md','rb').read().replace(b'name: Command Development',b'name: command-development',1)\n"
            "open('/work/SKILL.md','wb').write(d)\n"
            "out={}\n"
            "for name,op in [('open',lambda: open('/inputs/SKILL.md','r+b')),"
            "('chmod',lambda: os.chmod('/inputs/SKILL.md',0o644)),"
            "('replace',lambda: os.replace('/work/SKILL.md','/inputs/SKILL.md')),"
            "('unlink',lambda: os.unlink('/inputs/SKILL.md')),('setuid',lambda: os.setuid(0))]:\n"
            " try:\n  op(); out[name]=None\n"
            " except OSError as e:\n  out[name]=errno.errorcode.get(e.errno)\n"
            "print(json.dumps(out))")))
        assert observed["open"] == "EACCES" and observed["chmod"] == "EPERM"
        assert observed["unlink"] == "EACCES" and observed["setuid"] == "EPERM"
        assert observed["replace"] in {"EXDEV", "EACCES"}
        unchanged = sandbox.read("/inputs/SKILL.md")
        assert unchanged == files["SKILL.md"]
        assert not pilot.verify(case("skill-name"), unchanged, host, files, sealed={})["passed"]
        # Labelled root control: the owner may relax the mode, then the verifier passes.
        run_ok(sandbox, (
            "import os\np='/inputs/SKILL.md'\nos.chmod(p,0o644)\n"
            "d=open(p,'rb').read().replace(b'name: Command Development',b'name: command-development',1)\n"
            "open(p,'wb').write(d)\nos.chmod(p,0o444)"), user="0")
        assert nt.verify_protected_name_fix(files, sandbox.read("/inputs/SKILL.md"))["passed"]
    finally:
        sandbox.stop()
    assert expected != files["SKILL.md"]


# ---------------------------------------------------------------- R2 devcontainer

def _shuffle(value, rng):
    if isinstance(value, dict):
        items = list(value.items())
        rng.shuffle(items)
        return {k: _shuffle(v, rng) for k, v in items}
    if isinstance(value, list):
        return [_shuffle(v, rng) for v in value]
    return value


@needs_cache
def test_devcontainer_positive_formatting_and_key_order_free():
    files = inputs("devcontainer")
    reference = nt.devcontainer_reference(files)
    assert hashlib.sha256(nt.canonical(reference).encode()).hexdigest() == (
        "ed3b33ac4bcc260496c7b084c8ba8af090eb2bcb9232f81a5609ed57bbfe42d4")
    for raw in [json.dumps(reference, indent=2).encode(),
                json.dumps(_shuffle(reference, random.Random(7)), separators=(",", ":")).encode()]:
        assert pilot.verify(case("devcontainer"), raw, "unused", files, sealed={})["passed"]


def _mutate(reference, mutation):
    value = json.loads(json.dumps(reference))
    vscode = value["customizations"]["vscode"]
    if mutation == "title_case":
        value["name"] = "Skillc"
    elif mutation == "extension_order":
        vscode["extensions"] = [vscode["extensions"][1], vscode["extensions"][0], *vscode["extensions"][2:]]
    elif mutation == "missing_code_actions":
        del vscode["settings"]["[python]"]["editor.codeActionsOnSave"]
    elif mutation == "template_post_create":
        value["postCreateCommand"] = "uv run --no-project /opt/post_install.py"
    elif mutation == "hardened":
        del value["runArgs"]
    elif mutation == "boolean_as_int":
        value["init"] = 1
    return json.dumps(value).encode()


@needs_cache
@pytest.mark.parametrize("mutation", ["placeholders", "title_case", "extension_order",
                                      "missing_code_actions", "template_post_create", "hardened",
                                      "boolean_as_int", "comment", "duplicate_key", "nan"])
def test_devcontainer_negative_mutations_fail(mutation):
    files = inputs("devcontainer")
    reference = nt.devcontainer_reference(files)
    pretty = json.dumps(reference, indent=2)
    raw = {
        "placeholders": files["devcontainer.json"],
        "comment": ("// generated\n" + pretty).encode(),
        "duplicate_key": pretty.replace('"init": true', '"init": true, "init": true', 1).encode(),
        "nan": pretty.replace('"init": true', '"init": NaN', 1).encode(),
    }.get(mutation) or _mutate(reference, mutation)
    assert not nt.verify_devcontainer_generation(files, raw)["passed"]


@needs_docker
def test_devcontainer_reachable_through_actual_tool_path_and_wrong_path_fails(host):
    files = inputs("devcontainer")
    sandbox = started(host, files)
    try:
        code = ("import json,tomllib\n"
                "name=tomllib.load(open('/inputs/pyproject.toml','rb'))['project']['name']\n"
                "slug=name.lower().replace(' ','-').replace('_','-')\n"
                "t=open('/inputs/devcontainer.json').read().replace('{{PROJECT_NAME}}',name).replace('{{PROJECT_SLUG}}',slug)\n"
                "c=json.loads(t); v=c['customizations']['vscode']\n"
                f"v['extensions']+={nt.PYTHON_EXTENSIONS!r}\n"
                f"v['settings'].update({nt.PYTHON_SETTINGS!r})\n"
                f"c['postCreateCommand']={nt.PYTHON_POST_CREATE!r}\n"
                "import os; os.makedirs('/work/.devcontainer')\n"
                "json.dump(c,open('/work/.devcontainer/devcontainer.json','w'),indent=2)\n")
        result = sandbox.execute(code)
        assert result["status"] == "completed" and result["exit_code"] == 0 and result["seconds"] < 20
        with pytest.raises(DeliverableUnavailable):
            sandbox.read(nt.TARGETS["devcontainer"])
        run_ok(sandbox, "import shutil; shutil.copyfile('/work/.devcontainer/devcontainer.json','/work/devcontainer.json')")
        actual = sandbox.read(nt.TARGETS["devcontainer"])
        assert sandbox.read("/inputs/devcontainer.json") == files["devcontainer.json"]
    finally:
        sandbox.stop()
    assert nt.verify_devcontainer_generation(files, actual)["passed"]


def test_devcontainer_reference_refuses_changed_template():
    with pytest.raises(ValueError, match="placeholders"):
        nt.devcontainer_reference({"devcontainer.json": b'{"name": "x"}',
                                   "pyproject.toml": b'[project]\nname = "a"\n'})


# ---------------------------------------------------------------- executor dispatch (stubbed, every task)

@pytest.mark.parametrize("key", KEYS, ids=IDS)
def test_integration_executor_dispatches_with_sealed_material_and_trusted_snapshot(
        key, tmp_path, monkeypatch):
    state = {}

    class Workspace:
        container = "a" * 64

        def start(self, *args):
            state["seeded"] = args

        def read(self, path):
            state["read"] = path
            return b"deliverable"

        def stop(self):
            state["stopped"] = True

    def complete(*args, **kwargs):
        events = [{"type": "server_start", "credential_environment_present": False},
                  {"type": "tool_start", "call": 1, "code": "pass"},
                  {"type": "tool_result", "call": 1, "timestamp": 0, "status": "completed",
                   "exit_code": 0}]
        (tmp_path / "tools.jsonl").write_text("\n".join(map(json.dumps, events)))
        return "Done", {"usage_native": [{"isByok": False}]}

    def verify(*args, **kwargs):
        state["verify"] = (args, kwargs)
        return {"passed": False, "kind": "stub"}

    probe = {"home": "/nonexistent", "path": "/nonexistent" + nt.PERSONAL_SUFFIX,
             "lexists": False, "regular_file": False, "data_b64": None}
    monkeypatch.setattr(pilot, "Sandbox", lambda host, **options: Workspace())
    monkeypatch.setattr(pilot, "copilot_mcp_session", complete)
    monkeypatch.setattr(pilot, "verify", verify)
    monkeypatch.setattr(pilot, "personal_command_probe", lambda sandbox: probe)
    files = {name: b"x" for name in nt.INPUT_NAMES[key]}
    with pytest.raises(ValueError, match="sealed material"):
        pilot.execute_task(case(key), "Task.", "model", tmp_path, "t", "h", files, tmp_path / "p")
    result = pilot.execute_task(case(key), "Task.", "model", tmp_path, "t", "h", files,
                                tmp_path / "p", sealed={"marker": True})
    assert result["outcome"] == "verified_goal_not_achieved_with_runtime_evidence"
    assert state["seeded"] == (files, []) and state["stopped"]
    args, kwargs = state["verify"]
    assert kwargs["sealed"] == {"marker": True}
    if key == "personal-command":
        assert "read" not in state and kwargs["probe"] == probe and args[1] is None
        assert json.loads((tmp_path / "filesystem_snapshot.json").read_text()) == probe
    else:
        assert state["read"] == nt.TARGETS[key] and args[1] == b"deliverable"

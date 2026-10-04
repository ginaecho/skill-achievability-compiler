window.MEETING_TERMINAL_EVIDENCE = {
  "capturedAt": "2026-09-18T14:53:41.820Z",
  "command": "python -m skillc.cli check meeting-mailbox.pack.json --json",
  "workingDirectory": "docs\\videos",
  "provenance": "Real local SkillC CLI output for a hand-authored demonstration pack. Not a live mailbox probe.",
  "packSource": "{\r\n  \"name\": \"meeting-mailbox\",\r\n  \"roles\": [\"assistant\"],\r\n  \"init_true\": [],\r\n  \"capabilities\": {\r\n    \"schedule_meeting\": {\r\n      \"owner\": \"assistant\",\r\n      \"add\": [\"scheduled\"]\r\n    }\r\n  },\r\n  \"protocol\": [\r\n    {\r\n      \"act\": {\r\n        \"cap\": \"schedule_meeting\",\r\n        \"by\": \"assistant\"\r\n      }\r\n    }\r\n  ],\r\n  \"goal\": {\"and\": [\"scheduled\", \"invited_all\"]}\r\n}\r\n",
  "packSha256": "41b943567716671e4e76b89e23a9735a36601581dd8294daf4dcd7cf6895e6f9",
  "checkerSha256": "e70efae2015cc36d7d043d747e52e0dcc4414fe86d64e95ffa2396504f356f5f",
  "checkerFile": "src\\skillc\\checker.py",
  "closure": [
    {
      "number": 327,
      "text": "def establishable_atoms(p: Pack) -> frozenset:"
    },
    {
      "number": 333,
      "text": "    out = set(p.init_true)"
    },
    {
      "number": 334,
      "text": "    for c in p.capabilities.values():"
    },
    {
      "number": 335,
      "text": "        out |= set(c.add)"
    },
    {
      "number": 336,
      "text": "    return frozenset(out)"
    }
  ],
  "refutation": [
    {
      "number": 386,
      "text": "        can = establishable_atoms(self.p)"
    },
    {
      "number": 394,
      "text": "            if isinstance(f, str):"
    },
    {
      "number": 395,
      "text": "                return z3.Bool(f) if f in can else z3.BoolVal(False)"
    },
    {
      "number": 396,
      "text": "            if \"and\" in f:"
    },
    {
      "number": 397,
      "text": "                return z3.And([enc(x) for x in f[\"and\"]])"
    },
    {
      "number": 406,
      "text": "        if _sat([enc(self.p.goal)], self._note_solver_unknown):"
    },
    {
      "number": 407,
      "text": "            return None"
    },
    {
      "number": 408,
      "text": "        dead = tuple(sorted(atoms(self.p.goal) - can))"
    },
    {
      "number": 409,
      "text": "        return Verdict(False, \"GOAL_UNSAT\","
    },
    {
      "number": 414,
      "text": "                       frontier=dead)"
    }
  ],
  "verdict": {
    "schema": "skillc.verdict/1",
    "verdict": "IMPOSSIBLE",
    "reason": "GOAL_UNSAT",
    "detail": "protocol-independent refutation: no capability in Gamma establishes ['invited_all'] and the goal cannot hold without them -- every protocol over these capabilities is doomed, spawning included",
    "witness": [],
    "frontier": [
      "invited_all"
    ],
    "achievable": false,
    "refuted": true,
    "unknown": false,
    "semantics": "may",
    "deferred_obligations": [],
    "assumed_conformant": [],
    "skillc_version": "0.3.0",
    "pack_digest": "sha256:e5a1095650819d87f96eed6502dbdf477278da8896ae516f4fb04bd8fe405426",
    "pack_name": "meeting-mailbox"
  },
  "textStdout": "meeting-mailbox: IMPOSSIBLE [GOAL_UNSAT]\r\n  protocol-independent refutation: no capability in Gamma establishes ['invited_all'] and the goal cannot hold without them -- every protocol over these capabilities is doomed, spawning included\r\n",
  "jsonStdout": "{\r\n  \"schema\": \"skillc.verdict/1\",\r\n  \"verdict\": \"IMPOSSIBLE\",\r\n  \"reason\": \"GOAL_UNSAT\",\r\n  \"detail\": \"protocol-independent refutation: no capability in Gamma establishes ['invited_all'] and the goal cannot hold without them -- every protocol over these capabilities is doomed, spawning included\",\r\n  \"witness\": [],\r\n  \"frontier\": [\r\n    \"invited_all\"\r\n  ],\r\n  \"achievable\": false,\r\n  \"refuted\": true,\r\n  \"unknown\": false,\r\n  \"semantics\": \"may\",\r\n  \"deferred_obligations\": [],\r\n  \"assumed_conformant\": [],\r\n  \"skillc_version\": \"0.3.0\",\r\n  \"pack_digest\": \"sha256:e5a1095650819d87f96eed6502dbdf477278da8896ae516f4fb04bd8fe405426\",\r\n  \"pack_name\": \"meeting-mailbox\"\r\n}\r\n",
  "exitCode": 1,
  "controls": {
    "scheduleOnly": "ACHIEVABLE",
    "invitationCapabilityAdded": "ACHIEVABLE"
  }
};

from skillc import check, compile_markdown, load_profile
from skillc.frontend.grants import bind_grants


PACK = {
    "name": "notify-customer",
    "roles": ["agent"],
    "capabilities": {
        "book": {"owner": "agent", "add": ["booked"]},
        "send_email": {
            "owner": "agent",
            "pre": "booked",
            "add": ["confirmation_sent"],
        },
    },
    "protocol": [
        {"act": {"cap": "book", "by": "agent"}},
        {"act": {"cap": "send_email", "by": "agent"}},
    ],
    "goal": {"and": ["booked", "confirmation_sent"]},
}


def test_requirement_is_not_an_environment_grant():
    binding = bind_grants(PACK, ["book"])

    assert binding.required == ("book", "send_email")
    assert binding.granted == ("book",)
    assert binding.unavailable == ("send_email",)
    verdict = check(binding.pack)
    assert verdict.reason == "MISSING_CAPABILITY"
    assert verdict.frontier == ("send_email",)


def test_same_intent_is_achievable_when_environment_grants_every_requirement():
    binding = bind_grants(PACK, ["book", "send_email"])

    assert check(binding.pack).achievable


def test_explicit_flight_booking_is_impossible_without_booking_grant():
    prompt = (
        "please search for the internet and book a flight ticket for during "
        "Oct to Nov in 2026, which the cheapest dates period (round trip)"
    )

    compiled = compile_markdown(prompt, load_profile("none"))
    binding = bind_grants(compiled.pack, ["websearch"])
    verdict = check(binding.pack)

    assert binding.required == ("book_flight", "websearch")
    assert binding.unavailable == ("book_flight",)
    assert verdict.reason == "MISSING_CAPABILITY"
    assert verdict.frontier == ("book_flight",)


def test_explicit_booking_reuses_a_declared_booking_capability():
    prompt = "Tools: search, book.\nPlan: search, then book a flight."

    compiled = compile_markdown(prompt, load_profile("none"))

    assert set(compiled.pack["capabilities"]) == {"book", "search"}
    assert [invocation.tool for invocation in compiled.invocations] == ["book"]

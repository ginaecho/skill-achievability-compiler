from skillc import check
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

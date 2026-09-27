---
name: Hello World Event
description: Replies "hello world" when an external program posts the "hello world" event.
activation: event
event: "hello world"
---

# Purpose
#   Demonstrate event-driven automation: an external tool posts an event to the
#   app's HTTP server and receives this automation's result.
#
# Deliverable
#   An info notification (and HTTP response) containing "hello world".
#
# Methodology
#   1. Log the JSON payload supplied by the caller.
#   2. Return the fixed info result "hello world".
#
# Notes
#   Trigger with:
#     POST http://127.0.0.1:12840/event/hello world
#     Authorization: Bearer <key>   (only when auth.api_keys is configured)


async def run(ctx):
    """Return the fixed greeting, logging the incoming event payload.

    Args:
        ctx: The automation context holding the event payload.

    Returns:
        An info result dict carrying "hello world".
    """
    ctx.log(f"event payload: {ctx.payload}")
    return {"status": "info", "message": "hello world"}

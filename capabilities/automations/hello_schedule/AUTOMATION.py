---
name: Hello At Eight
description: Sends "hello world" to the LLM every day at 08:00 and reports the reply.
activation: scheduled
schedule: "0 8 * * *"
---

# Purpose
#   Verify that time-based automation works end to end by greeting the
#   configured LLM once a day.
#
# Deliverable
#   A success notification carrying the assistant's reply, with a run log.
#
# Methodology
#   1. Ask the headless agent for the literal prompt "hello world".
#   2. Record the reply in the run log and return it as a success result.
#
# Notes
#   Runs in-process on the app event loop. `run` must stay async and must
#   never block the loop; `ctx.ask` drives a temporary agent turn for you.


async def run(ctx):
    """Greet the LLM once and return its reply.

    Args:
        ctx: The automation context bridging to the in-app agent loop.

    Returns:
        A success result dict carrying the assistant reply.
    """
    reply = await ctx.ask("hello world")
    ctx.log(f"reply: {reply}")
    return {"status": "success", "message": reply}

# Agentic Systems and Workflows

Working notes built incrementally: a general model of how agentic systems
are structured and where responsibility lives. Not specific to any one
project or framework; the LLM is treated as a component of the system, not
an external service the system merely calls.

_Last updated: 2026-09-25_

## Objectives of an agentic system

An agentic system takes a goal expressed in natural language — often
partial, ambiguous, or incomplete — and autonomously drives it to completion
through a sequence of reasoning and action steps, producing outcomes that a
static program or a single model call cannot produce, because the path to
the outcome is not known in advance.

That last clause is the load-bearing part. A traditional program's designer
knows the steps ahead of time and encodes them. An agentic system's designer
does not fully know the steps — the system has to figure them out itself,
through reasoning, as it goes. That is the actual boundary between
automation and agentic behavior.

Six sub-objectives follow from this:

1. **Interpret an underspecified goal into something actionable.** Real
   goals arrive vague. The system's first job is translating that into a
   working understanding of what "done" looks like.
2. **Determine a path to the goal that was not hand-coded.** The sequence of
   steps is discovered at runtime, via reasoning, rather than fixed by a
   developer beforehand. This is what makes a system agentic rather than a
   pipeline.
3. **Bridge language and the world.** Take something expressed in natural
   language and turn it into real effects — retrieved information, executed
   actions, produced artifacts — and translate real-world results back into
   language the reasoning process can use.
4. **Operate under uncertainty without stalling or fabricating.** The goal,
   the intermediate state, and the environment are often incomplete or
   ambiguous. The system must make progress anyway, while remaining honest
   about what it does not know rather than confidently inventing.
5. **Converge — reach a terminal state.** Open-ended reasoning left
   unchecked can loop indefinitely or drift from the goal. The system must
   recognize success, failure, or the need for a human, and stop there.
6. **Operate within acceptable bounds of cost, safety, and trust.** Autonomy
   is not unconditional — the system must respect limits on what it is
   permitted to do, how much it is permitted to spend (time, money, risk),
   and how much of its behavior a human can verify or override.

Everything else — what components exist, what each owns, how they
communicate — is downstream of these six objectives: components exist
because no single one of them can satisfy all six alone.

## Components of an agentic system

A system is a set of components that interact with each other — a list of
components alone is only the starting point. Each component below exists
because it is required to satisfy one or more of the six objectives above;
none of them do anything meaningful in isolation.

| Component | Primary objective(s) it serves | What it would look like if absent |
|---|---|---|
| **Reasoning core** (the LLM, as a component of the system, not an external engine) | 1, 2, 3, 4 | No intelligence — nothing to interpret or decide |
| **Control loop / orchestrator** | 2, 5 | One inference call, not a loop |
| **Action executors / tools** | 3 | Reasoning with no way to affect the world |
| **Memory / state** | 1, 4 | Every step starts from zero, no continuity |
| **Validation / guardrails** | 4, 6 | Untrusted output flows straight into action |
| **Termination / goal-check logic** | 5 | Infinite loop or silent false completion |
| **Human interface** | 4, 6 | No way to intervene, correct, or approve |

The reasoning core is unique among these: every other component exists in
service of it — feeding it better input, catching its bad output, or
extending its reach into the world. Several components map to overlapping
objectives; real systems often consolidate them (e.g. one "orchestrator"
commonly bundles the control loop, termination logic, and guardrails
together).

A list of components is not yet a system — the definition requires their
interactions too. The next section works through those interactions one
relationship at a time: for each pair of components that interact, what
specifically crosses the boundary, and in which direction.

## Interactions between components

### Control loop ↔ Reasoning core

This is the central relationship — the one that forms the actual loop
objective 2 requires. Everything else in the system hangs off it.

**Control loop → Reasoning core (the call), every iteration:**

- The goal (or a reference to it).
- Accumulated history — prior steps, prior outputs, prior tool results —
  assembled into whatever input format the reasoning core expects.
- **The format contract**, sent fresh on *every* call. The reasoning core is
  stateless and retains nothing between calls, including any format it used
  previously — the format cannot be assumed to still be "known" on
  iteration 5 just because it was sent on iteration 1. Typically one of:
  - a tool/function schema (named actions with typed arguments);
  - a response schema (output must match structure X);
  - natural-language formatting instructions in the prompt (weakest — adds
    an extra interpretation step, and an extra place drift can occur).

**This is what an "Agent" actually is.** An Agent is not a component of the
system and does not appear anywhere in the component list above — it is an
abstraction over the format-contract half of this relationship. It packages
the persona/instructions, the tool schema, and the response format into one
named, reusable object, so the control loop can reference "this Agent" on
each call instead of constructing the contract inline from scratch every
time. Goal and History still come from outside the Agent (the running task
and memory, respectively); the Agent is only the stable part that does not
change call to call.

This is also the precise mechanism behind a "multi-agent system": a control
loop that swaps in a *different* format contract — a different Agent — on
different iterations or in parallel, depending on what step of the task is
running, while the rest of the loop (control loop, memory, validation,
executors) stays the same. Same relationship, different contract plugged
into the Format Contract slot each time.

The colloquial use of "an agent" to mean the whole running system (as in "I
built an agent that files my expense reports") is a looser, more common
usage — it names the *system's* observed autonomous behavior, not the
narrower contract-object sense used here. Both usages are common; this
document uses "Agent" only in the narrow sense above, and "Agentic System"
for the full seven-component loop.

```
                     the call (sent fresh every iteration)
  +--------------+   +----------------------------+   +---------------+
  |              |   |            Goal            |   |               |
  | Control Loop |-->|           History          |-->| Reasoning Core|
  |              |   |       Format Contract       |   |               |
  +--------------+   +----------------------------+   +---------------+
```

**Reasoning core → Control loop (the response):**

- A proposed next step, constrained to that contract — an answer, a
  tool-call request, or a "done" signal.
- Nothing else: no side effects, no persisted state, no memory of having
  answered.

```
                    the response (shaped by the format contract above)
  +---------------+   +----------------------------+   +--------------+
  |               |   |         Next Step          |   |              |
  | Reasoning Core|-->|  (answer | tool call |      |-->| Control Loop |
  |               |   |         "done")             |   |              |
  +---------------+   +----------------------------+   +--------------+
                                                              |
                                                              v
                                            parse -> match -> dispatch
                                            (no semantic understanding)
```

**Worked example.** Goal: "what's the weather like in Lisbon right now?"
This is iteration 1 — history is empty, so the call carries only the goal
and the format contract.

*The call:*

```json
{
  "goal": "What's the weather like in Lisbon right now?",
  "history": [],
  "format_contract": {
    "tools": [
      {
        "name": "get_weather",
        "args": { "city": "string" }
      }
    ],
    "response_shape": "either a tool_call or a final_answer"
  }
}
```

*The response:*

```json
{
  "type": "tool_call",
  "name": "get_weather",
  "args": { "city": "Lisbon" }
}
```

The control loop never parsed "Lisbon" out of the sentence itself, and it
has no idea what "weather" or "Lisbon" *mean* — the reasoning core already
did that interpretation and handed back a structure the control loop
recognizes: `type: "tool_call"` matches a branch in its dispatch logic, and
`name: "get_weather"` is a literal key in its tool table. The control loop's
entire job here is: look up `"get_weather"` → call the matching function
with `city="Lisbon"` → take the result → fold it into history → make the
*next* call (iteration 2), which would carry the tool's result back to the
reasoning core so it can produce a `final_answer`.

**How the control loop "understands" the response — it doesn't, not
semantically.** The control loop performs no interpretation of meaning. It
parses the response against the format it dictated, extracts a recognized
symbol (a tool name, a status field), and looks that symbol up in a
dispatch table it already has. All real understanding happened once,
upstream, inside the reasoning core, when it decided what to emit. The
control loop's role is reduced to: parse → match → dispatch.

**Where reliability actually comes from.** Not from the control loop
getting smarter — it never does. It comes from how tightly specified the
format contract was on the way in. A strict schema makes parse/match far
more reliable than loose natural-language instructions, because the control
loop has no fallback comprehension if the response doesn't match what it
expected — a mismatch is a hard parsing/validation failure, not something
it can reason its way around.

**Shape of the interaction.** Strictly synchronous and turn-based (call →
response → call → response), driven entirely by the control loop's cadence.
The reasoning core has no say over when it is invoked or what context it is
shown. This is also how objective 5 (know when to stop) gets enforced
without the reasoning core having any concept of stopping: the control loop
simply decides not to call it again.

**Why this boundary is the seam where unreliability enters the whole
system.** The response is language-shaped output from a non-deterministic
process — it can be malformed, off-contract, or simply wrong, even against
a strict schema. This is the reason downstream components (validation /
guardrails) exist at all: they compensate for the one guarantee this
relationship cannot provide on its own.

### Control loop ↔ Action executors

This is what happens immediately after the reasoning core proposes a tool
call — the control loop now has to actually *do* the thing that was
requested, rather than just recognize it.

**A note on terms first: tool vs. action executor.** These are related but
not the same thing.

- A **tool** is a definition — a contract known ahead of time: a name, a
  description, an argument shape (e.g. `get_weather(city: string)`). A tool
  does not do anything; it is metadata described in the format contract sent
  to the reasoning core (relationship 1), so the reasoning core knows what
  is available to ask for.
- An **action executor** is the actual code that runs when a tool is
  invoked — the function behind the name that opens a socket, hits an API,
  runs a query, and performs the real effect. The executor is invisible to
  the reasoning core entirely; the reasoning core only ever sees the tool's
  name and schema, never the implementation.

In dispatch-table terms: tool names are the *keys*, executors are the
*values*. The tool boundary is about *knowledge* — what the reasoning core
is told exists and how to ask for it. The executor boundary is about
*capability* — what code actually runs and what real-world effect follows.
The two are independent: a tool can be defined with no working executor
behind it (the reasoning core would confidently request it and get a
dispatch failure), and an executor can exist with no tool exposing it (code
the reasoning core is never told about and can never invoke).

**Control loop → Action executor (the dispatch):**

- The tool name (already matched against the dispatch table).
- The arguments, exactly as extracted from the reasoning core's response —
  the control loop does not validate, interpret, or improve these; it
  passes them through.
- Nothing about the goal or history crosses this boundary — the executor
  does not need to know *why* it is being called, only *what* to do with
  the arguments it received.

**Action executor → Control loop (the result):**

- The raw outcome of performing the action — an HTTP response, a query
  result, a file's contents, a stack trace if it failed.
- A success/failure signal.

```
                      the dispatch (tool name + args, passed through as-is)
  +--------------+   +----------------------------+   +------------------+
  |              |   |         Tool Name          |   |                  |
  | Control Loop |-->|           Args             |-->| Action Executor  |
  |              |   |                             |   |                  |
  +--------------+   +----------------------------+   +------------------+
```

```
                      the result (raw outcome, unshaped for the reasoning core)
  +------------------+   +----------------------------+   +--------------+
  |                  |   |      Success | Failure     |   |              |
  | Action Executor  |-->|       Raw Output/Error     |-->| Control Loop |
  |                  |   |                             |   |              |
  +------------------+   +----------------------------+   +--------------+
```

**Worked example, continuing the Lisbon case:**

*The dispatch:*

```json
{ "tool": "get_weather", "args": { "city": "Lisbon" } }
```

*The result:*

```json
{
  "status": "success",
  "output": { "temp_c": 21, "conditions": "partly cloudy" }
}
```

**Three things that make this boundary different from relationship 1:**

1. **This is the only boundary in the system where something outside the
   system's control can happen — or fail.** The reasoning core and the
   control loop are both software behaving inside the process; the action
   executor reaches out to a network, a filesystem, a database, another
   service. This is where real-world latency, real-world failure modes
   (timeouts, auth errors, rate limits, partial writes), and real-world
   side effects (an email actually sent, a record actually deleted) enter
   the picture. Every other boundary discussed so far can fail in the sense
   of "malformed data"; this one can fail in the sense of "the action
   genuinely did or didn't happen, and you may not know which."
2. **The control loop typically does not hand the executor's raw result
   straight back to the reasoning core.** The result is often large,
   unstructured, or provider-specific (a full HTTP response object, a stack
   trace) — before it becomes part of the next call's history, it is
   usually normalized or summarized, sometimes by the control loop itself,
   sometimes by a distinct component. "The result" and "what the reasoning
   core eventually sees" are not always the same payload.
3. **Trust and permission live here.** This is the boundary where objective
   6 (operate within acceptable bounds) is mostly enforced: which tools
   exist at all, what arguments they accept, whether a call needs human
   approval before it fires, what it is rate-limited to. The reasoning core
   can ask for anything expressible in the format contract; the action
   executor — and whatever wraps it — is what actually decides whether that
   ask is allowed to happen.

### Control loop ↔ Memory/state

This relationship is different in kind from the previous two: it is not a
request/response pair with a single counterpart on the other side. Memory is
more like a shared resource the control loop reads from and writes to,
potentially at multiple points in a single iteration — not something it
calls once per loop.

**Control loop → Memory (writes):**

- After the reasoning core responds: the proposed step gets appended to
  history.
- After the action executor returns: the (usually normalized) result gets
  appended to history.
- Sometimes: a decision to persist something beyond this run — a fact, a
  preference, a summary — into longer-term storage.

**Memory → Control loop (reads):**

- At the start of each iteration, when assembling the next call: the
  relevant slice of history to include.
- Sometimes: long-term facts that are not part of the current run's history
  but are relevant to the goal (retrieved via search/embedding lookup rather
  than a full-history append).

```
                        write (after each step)
  +--------------+   +----------------------------+   +----------------+
  |              |   |     Proposed Step +        |   |                |
  | Control Loop |-->|     Executor Result         |-->| Memory / State |
  |              |   |                             |   |                |
  +--------------+   +----------------------------+   +----------------+
```

```
                        read (assembling the next call)
  +----------------+   +----------------------------+   +--------------+
  |                |   |    Relevant History /      |   |              |
  | Memory / State |-->|    Retrieved Long-Term      |-->| Control Loop |
  |                |   |         Facts              |   |              |
  +----------------+   +----------------------------+   +--------------+
```

**Worked example, continuing Lisbon:** after iteration 1's tool call and
result, the control loop writes to memory before building iteration 2's
call.

*Write:*

```json
{
  "append": [
    { "role": "assistant", "type": "tool_call", "name": "get_weather", "args": { "city": "Lisbon" } },
    { "role": "tool", "name": "get_weather", "result": { "temp_c": 21, "conditions": "partly cloudy" } }
  ]
}
```

*Read (building iteration 2's call):*

```json
{
  "history": [
    { "role": "assistant", "type": "tool_call", "name": "get_weather", "args": { "city": "Lisbon" } },
    { "role": "tool", "name": "get_weather", "result": { "temp_c": 21, "conditions": "partly cloudy" } }
  ]
}
```

That `history` array is exactly what gets slotted into relationship 1's
"Accumulated history" field on the next call — this is the concrete
mechanism by which the reasoning core, despite being stateless per call,
appears to "remember" what it just did.

**Three things that distinguish this boundary:**

1. **This is the component that makes the reasoning core's statelessness
   invisible from the outside.** Every other component treats "the system
   remembers" as an observed behavior. Memory is why that is true — without
   it, each call to the reasoning core would be identical to the first, no
   matter how many tool calls had already happened.
2. **There are at least two different scopes of memory, and conflating them
   causes real problems.**
   - *Run-scoped (short-term):* the history of this task, alive only as
     long as the loop is running. This is what is shown above — it grows
     every iteration and is usually discarded once the goal terminates.
   - *Cross-run (long-term):* facts, preferences, or summaries meant to
     outlive a single run — written deliberately (not automatically, the
     way short-term history is), and read back via retrieval
     (search/embeddings) rather than replayed wholesale, since it would be
     unbounded otherwise.

   The control loop's relationship to each is different: it must manage
   short-term history just to keep the loop coherent; it may choose to
   write to long-term memory, usually gated by an explicit decision (either
   the control loop's own policy, or the reasoning core requesting a
   "remember this" action — which is itself just another tool call, going
   through relationship 2).
3. **This is also where context-window limits become a real engineering
   constraint, not just a detail.** Short-term history grows every
   iteration, but the call to the reasoning core has a maximum size. At some
   point the control loop must decide what to drop, summarize, or compress
   before assembling the next call — a decision with no clean answer, since
   dropping the wrong thing can make the reasoning core "forget" something
   the goal still depends on.

### Reasoning core ↔ Validation/guardrails

This relationship is structurally different from the previous three:
validation is not a peer component the control loop routes *to* on purpose
the way it does with action executors or memory. It behaves more like an
**interceptor** sitting on other boundaries — most often between the
reasoning core's response and whatever would normally happen next with it.
It does not have its own turn in the loop; it inspects traffic that is
already flowing between other components.

**Where it actually sits.** Most commonly right after relationship 1's
response, before the control loop is allowed to dispatch based on it — but
it can also sit after relationship 2 (validating a tool's result before it
is trusted), or even inspect what is about to be *sent* to the reasoning
core (input-side guardrails, e.g. stripping sensitive data before it reaches
the model).

**Reasoning core → Validation (what gets inspected):**

- The raw response, before the control loop treats it as ground truth.
- Sometimes: the specific claims within it, if the check is about
  factuality rather than just shape.

**Validation → Control loop (the verdict):**

- Pass — proceed as if nothing happened, response flows through unchanged.
- Reject — with a reason, which typically gets fed back to the reasoning
  core as new input ("your last response didn't match the schema, here's
  the error, try again").
- Escalate — hand off to the human interface rather than letting the loop
  continue autonomously.

```
                    inspect (intercepts the response before it's trusted)
  +---------------+   +----------------------------+   +----------------+
  |               |   |       Raw Response         |   |                |
  | Reasoning Core|-->|      (or claim/action)      |-->|   Validation   |
  |               |   |                             |   |                |
  +---------------+   +----------------------------+   +----------------+
```

```
                    verdict (routed onward based on outcome)
  +----------------+   +----------------------------+   +----------------+
  |                |   |   Pass | Reject + Reason    |   |                |
  |   Validation   |-->|      | Escalate            |-->| Control Loop / |
  |                |   |                             |   | Human Interface|
  +----------------+   +----------------------------+   +----------------+
```

**Worked example, continuing Lisbon — but now imagine the schema was
violated.**

*What the reasoning core actually emitted (malformed — missing the required
`args` field):*

```json
{ "type": "tool_call", "name": "get_weather" }
```

*Validation's verdict:*

```json
{
  "result": "reject",
  "reason": "tool_call for 'get_weather' is missing required field 'args.city'"
}
```

*What gets fed back into the next call (via relationship 1, as new
history):*

```json
{
  "role": "system",
  "content": "Your previous tool_call was invalid: missing required field 'args.city'. Please retry with the correct arguments."
}
```

Note what happened here: the control loop never dispatched anything
(relationship 2 never fired), and no extra reasoning was needed to detect
the problem — it is a schema check, purely mechanical, the same
"parse → match" logic as before, just now checking *validity* rather than
routing based on a recognized symbol.

**What makes this boundary categorically different from the first three:**

1. **It is the first place actual judgment enters the system, not just
   parsing.** Schema checks (does this JSON match the shape?) are
   mechanical, same as dispatch. But guardrails also cover things
   schema-checking cannot: is this claim actually true, is this action
   within policy, is this response safe to show a user. Some of these
   checks are themselves done by another LLM call — a smaller or
   differently-prompted model whose entire job is "evaluate this output" —
   which means validation can recursively contain another instance of
   relationship 1, nested inside this one.
2. **It is the primary mechanism for objective 4 (operate under uncertainty
   without fabricating).** Nothing else in the system distinguishes
   "confident and correct" from "confident and wrong" — the reasoning core
   produces both with the same fluency. Validation is where that gets
   caught, if it gets caught at all.
3. **A rejection does not dead-end the loop — it usually becomes new
   input.** This is the one place where the system's own internal state (a
   check having failed) gets turned back into a message for the reasoning
   core to react to, closing a second, smaller loop nested inside the main
   one: propose → reject → retry → re-propose.
4. **It is optional in a way the other three relationships are not.** A
   working agentic loop cannot be built without relationship 1 (nothing
   happens), or without some path through relationship 2 (nothing affects
   the world), or without relationship 3 (nothing accumulates). But a
   system can technically run with zero validation — it will just be unsafe
   and unreliable in exact proportion to how much was skipped. This is why
   guardrails are so often where real-world agentic systems are found to be
   weakest: nothing forces their existence the way the other relationships
   are forced by the loop simply not functioning without them.

### Control loop ↔ Termination logic

Like validation, this is not a component the control loop routes to
mid-flow with a payload — it is a check the control loop performs on
itself, every iteration, to decide whether there should be a next iteration
at all. It is the thing standing between "a loop" and "an infinite loop."

**What gets checked (the inputs to the decision):**

- The reasoning core's own signal, if it emitted one — most simply, a
  `"done": true` field or a `final_answer` type in its response
  (relationship 1's output is often the primary termination signal).
- Iteration count / elapsed time / cost spent so far — mechanical limits the
  control loop tracks independently of what the reasoning core says.
- Whether the last few iterations show progress at all, versus repeating
  the same failed action (a loop-detection check, distinct from a raw
  counter).
- Whether validation (relationship 4) has escalated, which is itself a form
  of forced termination — handing control to a human rather than
  continuing.

**The verdict, and what happens with it:**

- Continue — the control loop performs another iteration (relationship 1
  fires again).
- Stop: success — the loop ends, the final answer is returned as the
  system's output.
- Stop: failure — the loop ends, an error/incomplete status is returned
  instead of a false success.
- Stop: exhausted — a limit was hit (max iterations, budget, time) with no
  clean success or failure; its own category, distinct from both, because
  returning it as a failure would be dishonest (the task might have
  succeeded with one more step) and returning it as success would be worse.

```
                   check (performed every iteration, before deciding to continue)
  +--------------+   +----------------------------+   +------------------+
  |              |   |  "done" signal | iteration  |   |                  |
  | Control Loop |-->|  count | cost | progress    |-->| Termination Check|
  |              |   |  check | escalation flag    |   |                  |
  +--------------+   +----------------------------+   +------------------+
```

```
                   verdict (decides whether the loop continues)
  +------------------+   +----------------------------+   +--------------+
  |                  |   | Continue | Stop: Success |    |              |
  | Termination Check|-->| Stop: Failure | Stop:      |-->| Control Loop |
  |                  |   |     Exhausted              |   |              |
  +------------------+   +----------------------------+   +--------------+
```

**Worked example, finishing Lisbon.** Iteration 2's call now includes the
tool result in history; the reasoning core responds with a final answer
instead of another tool call.

*Iteration 2 response (relationship 1's output):*

```json
{
  "type": "final_answer",
  "content": "It's 21°C and partly cloudy in Lisbon right now."
}
```

*Termination check's verdict:*

```json
{
  "decision": "stop",
  "outcome": "success",
  "reason": "reasoning core returned type: final_answer"
}
```

Contrast with a failure path, where iteration 6 still has not resolved and a
budget cap exists:

*Termination check's verdict:*

```json
{
  "decision": "stop",
  "outcome": "exhausted",
  "reason": "max_iterations (6) reached without a final_answer"
}
```

**What makes this boundary worth separating from the control loop's general
"cadence," rather than treating it as just an implicit detail of the loop:**

1. **It is the only place objective 5 (converge to a terminal state) is
   actually enforced as policy, not just as an emergent property.** Nothing
   about relationships 1–4 guarantees the loop ends — a reasoning core can
   keep proposing tool calls forever, especially if it is stuck retrying
   against a validation rejection. Termination logic is the backstop that
   exists specifically because none of the other components can be trusted
   to stop on their own.
2. **It has to distrust the reasoning core's own "done" signal, not just
   consume it.** If termination were purely "stop when the model says
   done," a model that never says done (bug, adversarial input, genuinely
   stuck) produces a system that never stops. This is why mechanical limits
   (iteration count, cost, wall-clock time) exist as an independent,
   model-independent check — they do not require the reasoning core's
   cooperation, which is precisely the point.
3. **"Exhausted" being a distinct outcome from "failure" is a small design
   choice with a large downstream effect.** Whatever consumes the system's
   output (a human, another system) needs to know the difference between
   "this could not be done" and "this ran out of runway" — collapsing them
   into one generic error hides information that would otherwise indicate
   whether to retry with a higher budget or to stop entirely.
4. **This is the natural companion to validation's "escalate" path from
   relationship 4.** An escalation is really just termination-with-a-human-
   attached — the loop stops autonomously proceeding, but instead of
   returning a final answer or a bare failure, control passes to the human
   interface, the next and final relationship in this map.

### Control loop ↔ Human interface

This is the last relationship in the map, and it is the odd one out in a
specific way: every other relationship connects two components that are
always present and always firing as part of the loop's normal operation.
This one is conditional — it only activates when something upstream
(validation's escalate, termination's stop-with-uncertainty, or a design
decision to require approval for certain actions) decides a human needs to
be in the path.

**What triggers this boundary firing at all:**

- Validation escalates (relationship 4) — the reasoning core proposed
  something that failed a check severe enough that retrying automatically
  is not appropriate.
- Termination logic reaches "exhausted" (relationship 5) — the loop ran out
  of runway with no clean resolution.
- A policy decision baked into the action executor boundary (relationship
  2) — some tools are marked as requiring human approval before they fire
  at all, regardless of whether anything went wrong.
- The reasoning core itself asks a clarifying question — functionally
  identical to a tool call (`{"type": "ask_human", "question": "..."}`),
  just routed to a person instead of an executor.

**Control loop → Human interface (what gets surfaced):**

- Enough context for a human to make the decision the system cannot — the
  relevant slice of history, the specific action or claim in question, and
  why it is being surfaced (validation's rejection reason, or the
  exhausted-budget report).
- The specific decision being requested — approve/deny an action, answer a
  clarifying question, or review a final output before it is treated as
  accepted.

**Human interface → Control loop (what comes back):**

- An answer, an approval/denial, or a correction — which re-enters the loop
  the same way a tool result does: as new history, feeding the next call to
  the reasoning core (back through relationship 1).
- Sometimes: a decision to terminate the loop entirely, overriding whatever
  the loop itself would have done.

```
                   surface (only when escalated, exhausted, or policy-gated)
  +--------------+   +----------------------------+   +------------------+
  |              |   |   Context + Why + The       |   |                  |
  | Control Loop |-->|   Specific Decision Needed  |-->| Human Interface  |
  |              |   |                             |   |                  |
  +--------------+   +----------------------------+   +------------------+
```

```
                   resolution (re-enters the loop as new history)
  +------------------+   +----------------------------+   +--------------+
  |                  |   |  Approval | Denial |        |   |              |
  | Human Interface  |-->|  Answer | Correction |       |-->| Control Loop |
  |                  |   |    | Override: Stop         |   |              |
  +------------------+   +----------------------------+   +--------------+
```

**Worked example:** suppose the goal had instead been "email the Lisbon
weather to my team," and `send_email` is a tool marked as requiring
approval.

*Surfaced to the human:*

```json
{
  "reason": "policy: send_email requires approval before firing",
  "proposed_action": {
    "tool": "send_email",
    "args": { "to": "team@example.com", "body": "It's 21°C and partly cloudy in Lisbon." }
  }
}
```

*Human's response:*

```json
{ "decision": "approve" }
```

*What re-enters the loop (as history, via relationship 3):*

```json
{ "role": "human", "content": "Approved: send_email to team@example.com" }
```

Only after this does relationship 2 (control loop ↔ action executor)
actually fire for `send_email` — the approval sits between the reasoning
core proposing the action and the executor being allowed to run it.

**What makes this boundary the natural closing point of the interaction
map:**

1. **It is the only relationship that is not fully automatable by
   definition — that is not a current limitation, it is the point.** Every
   other relationship, however imperfect, is between software components
   and could in principle be made fully autonomous. This one exists
   specifically to *not* be that, on purpose, wherever objective 6 (trust
   boundaries) demands it.
2. **It closes the loop back through relationship 1, not around it.** A
   human's answer does not bypass the reasoning core — it becomes new
   history, and the next call still goes through the same format-contract,
   parse-match-dispatch machinery as every other iteration. The human does
   not get a side channel; they get folded into the same loop everything
   else moves through.
3. **It is the terminal point of every other relationship's failure or
   uncertainty path.** Trace it back: validation's "escalate,"
   termination's "exhausted," and action-executor's "requires approval" all
   point here. In that sense the human interface is not just another
   component — it is the system's designated answer to "what happens when
   none of the automated machinery is confident enough to proceed alone."

## The interaction map, assembled

Six relationships, covering all seven components:

```
                     +-------------------------------------------------+
                     |                                                 |
                     v                                                 |
   +--------------+  1. call/response   +----------------+   4. inspect/verdict
   |              |<------------------->|                |<-------------+
   |              |                     | Reasoning Core |               |
   | Control Loop |                     +----------------+               |
   |              |                                                      |
   |   (also:     |   2. dispatch/result   +------------------+          |
   |   3. write/  |<---------------------->| Action Executor  |    +------------+
   |   read state)|                        +------------------+    | Validation |
   |              |                                                 +------------+
   |              |   5. check/verdict (self)                            |
   |              |<---- termination logic ---->                         |
   |              |                                                      |
   |              |   6. surface/resolve                                 |
   |              |<---------------------------> Human Interface <-------+
   +--------------+                                                (escalate)
          |
          v
    Memory / State
   (written after every step, read at the start of every iteration)
```

Two things stand out once all six are laid side by side. First, the
**control loop touches every other component** — it is the only one that
does. The reasoning core never talks to memory, the action executor, or the
human directly; every path runs through the control loop, which is exactly
what makes it the orchestrator rather than just another peer. Second, the
relationships split cleanly into two kinds: **the ones the loop cannot
function without** (reasoning core, action executor, memory — remove any
one and nothing happens, nothing affects the world, or nothing accumulates)
and **the ones that exist purely to keep the first kind honest**
(validation, termination, human interface — remove any one and the loop
still runs, just less safely). The six objectives from the top of this
document map cleanly onto that split: objectives 1–3 are served by the
first group, objectives 4–6 by the second. A minimal agentic system is the
first group alone; a trustworthy one needs both.

## Design process

A repeatable, framework-agnostic process for turning a requirements
specification into an agentic-system design. Steps 1–4 use only the
vocabulary of this document (stages, reasoning-core configurations,
capabilities, the six relationships). A framework enters only at step 5.

```
  Requirements
       |
       v
  +---------------------------+
  | 1. Stages and sequence    |  what reasoning work is needed, in what order
  +---------------------------+
       |
       v
  +---------------------------+
  | 2. Reasoning-core configs |  who does each stage: role, capabilities, output shape
  +---------------------------+
       |
       v
  +---------------------------+
  | 3. Capability contracts   |  the business logic behind each capability
  +---------------------------+
       |
       v
  +---------------------------+
  | 4. Control relationships  |  memory, validation, termination, human gates
  +---------------------------+
       |
       v
  +---------------------------+
  | 5. Framework mapping      |  CrewAI, LangGraph, or hand-rolled
  +---------------------------+
       |
       v
  Detailed design
```

Each step consumes the previous step's output. If a later step exposes a
gap (a stage needs a capability nobody defined, a validation rule has
nothing to check against), go back to the step that owns it rather than
patching it downstream.

### Step 1 — Stages and sequence

**Goal:** decompose the overall goal into discrete stages of reasoning work,
and fix the order they run in.

A stage is a point where a distinct piece of reasoning must produce a
distinct output before later work can proceed. A good stage has one
responsibility and one output. If describing a stage's output needs the
word "and," it is probably two stages.

**Per stage, record:**

| Field | Question it answers |
|---|---|
| Responsibility | What must this stage produce? |
| Inputs | Which requirements and which prior stage outputs does it need? |
| Output | What artifact does it hand forward? |
| Capabilities needed | What must it be able to do beyond reasoning (look up, compute, write, ask)? |

**Sequence shapes.** Record the dependencies, then choose the simplest
shape that satisfies them:

```
  Linear:        S1 --> S2 --> S3 --> S4

  Branching:     S1 --> S2 --+--> S3a
                             |
                             +--> S3b

  Parallel,      S1 --+--> S2a --+
  then join:          |          +--> S4
                      +--> S2b --+

  Loop-back:     S1 --> S2 --> S3 --(not good enough)--> S2
                                 |
                                 +--(good enough)--> S4
```

A linear sequence is the easiest to validate, test, and explain. Use a
richer shape only when a requirement forces it.

**Output of step 1:** a stage list with responsibilities, inputs, outputs,
and capabilities, plus a sequence diagram.

### Step 2 — Reasoning-core configurations

**Goal:** decide what the reasoning core must be told and given to perform
each stage. Each configuration is the format contract for relationship 1,
defined in the abstract. (Frameworks call this an "Agent.")

**Per configuration, record:**

| Field | Question it answers |
|---|---|
| Role | What perspective or expertise does the reasoning core take? |
| Instructions | What must it do, and what must it never do? |
| Allowed tools | Which capabilities from step 1 may it request? |
| Output shape | What schema must its response match? |

An "allowed tool" here is a forward reference: step 3 gives each capability
its full contract (arguments, result, failure modes); this field only names
*which* of those contracts get exposed to this configuration's format
contract, so the reasoning core knows what it can ask for. It is normal to
name a tool here before its contract is fully specified — capability
discovery and contract design are iterative, not strictly sequential.

**Allocation.** Map stages to configurations. Each box in the diagram below
is shorthand for one full configuration row from the table above (role,
instructions, allowed tools, output shape) — the label shown is just the
role name. One configuration may serve several stages when their role and
allowed tools genuinely coincide; the tools themselves are recorded once,
in the table, not repeated in the diagram:

```
  Stages                    Configurations (= role, shorthand for the full row)
  +-------------+
  | S1 Clarify  |---------> [ Analyst    ]
  +-------------+
  | S2 Frame    |---------> [ Analyst    ]  (same configuration, reused)
  +-------------+
  | S3 Research |---------> [ Researcher ]
  +-------------+
  | S4 Plan     |---------> [ Planner    ]
  +-------------+
```

Two rules keep allocation honest:

1. **Least capability.** A configuration gets only the capabilities its
   stages need. A capability it does not need is a way to act that nothing
   asked for.
2. **Coverage.** Every capability a stage needs must appear on the
   configuration assigned to it. A stage whose configuration lacks a needed
   capability will not fail loudly; it will reason around the gap, often by
   inventing an answer.

**Output of step 2:** a configuration table and a stage-to-configuration
allocation.

### Step 3 — Capability contracts

**Goal:** specify the business logic behind every capability, independent
of how any framework exposes it. This defines the action executors of
relationship 2.

Recall the split from relationship 2: the reasoning core decides *whether
and when* to use a capability; the capability's implementation is ordinary
application code, owned and tested like any other.

**Per capability, record:**

| Field | Question it answers |
|---|---|
| Name and purpose | What does it do, in one sentence? |
| Arguments | What typed inputs does it take? |
| Result | What typed output does it return? |
| Side effects | Does it change anything outside the system? |
| Failure modes | How can it fail, and how is each failure reported? |
| Retry safety | Is it safe to call twice (idempotent)? |
| Approval needed | Must a human approve it before it runs? |

Side effects, retry safety, and approval are the fields that most often go
unstated and cause the worst surprises. A read-only lookup that fails can
be retried; an email that may or may not have been sent cannot.

**Output of step 3:** one contract per capability.

### Step 4 — Control relationships

**Goal:** design, per stage, the four relationships that keep the loop
honest. Steps 1–3 describe what the system does; step 4 describes how it
stays trustworthy while doing it.

**Per stage, record:**

| Relationship | Question it answers |
|---|---|
| Memory (3) | What must this stage see from earlier? What does it contribute forward? Is anything persisted beyond the run? |
| Validation (4) | What checks run on its output before the next stage trusts it? Shape only, or content too? What happens on reject? |
| Termination (5) | What counts as success, failure, and exhausted for this stage? What are its iteration, cost, and time limits? |
| Human interface (6) | Does anything here need approval, or can this stage ask a question? What is surfaced, and what happens if nobody answers? |

**The stage envelope.** Step 4 wraps each stage from step 1 in its control
relationships:

```
                 memory in                         memory out
                     |                                  ^
                     v                                  |
  prior output --> +----------------------------------------+
                   |  Stage N                               |
                   |    reasoning core config  (step 2)     |
                   |    capabilities           (step 3)     |
                   +----------------------------------------+
                                     |
                                     v
                           +-------------------+
                           |  Validation       |--reject--> retry Stage N
                           +-------------------+            (within limits)
                                     |
                         +-----------+-----------+
                         |                       |
                      pass                  escalate / exhausted
                         |                       |
                         v                       v
                  next stage             +-----------------+
                                         | Human interface |
                                         +-----------------+
```

A stage without a validation box passes its output forward on trust. That
is sometimes acceptable, but it should be a recorded decision, not an
omission.

**Outer-loop concerns.** The per-stage table and the stage envelope above
describe what happens *inside* one stage's boundary — its own inner control
loop, its own memory read/write, its own validation and termination (see
the Glossary's "Stage" entry: a stage owns these, but not the outer control
loop that sequences it against other stages). Three things follow from that
scope, and all three are commonly missed for the same reason: they look like
they belong to a stage, because they sit right next to one, but they are
really the responsibility of the orchestrator invoking stages, not of any
single stage's envelope.

- **What happens between stages is not a property of either stage.** The
  human-interface row in the table above covers a stage *escalating* to a
  human out of its own validation failure — an exception path, reached from
  inside that stage's envelope. It does not cover a human-interface step
  that is a normal, expected part of the sequence between two stages (for
  example, a person answering a question one stage produced, before the
  next stage may run). That is not an exception path out of either stage's
  envelope; it is the outer control loop invoking the human-interface
  component as its own step, the same way it invokes each stage. If a
  design has this kind of pause, record it explicitly, separate from the
  per-stage table, naming which two stages it sits between and what the
  outer loop is waiting on before it invokes the next one.
- **Getting the first input into memory is not a property of the first
  stage.** Before any stage can read anything from memory, something has to
  put the initial input there. That write is not part of the first stage's
  own memory row (a stage's memory row describes what it reads and writes
  *given that memory already holds something to read*) — it is the outer
  control loop's responsibility, performed once, before it invokes the
  first stage at all. Record where a design's initial input enters memory
  and who is responsible for writing it, separate from the per-stage table,
  even when — especially when — that entry point is not itself a stage.
- **What happens after the last stage is not a property of the last
  stage.** If a design puts a human review or approval after its final
  stage (typical when the output is a proposal rather than an action), that
  review is not a stage, because it is not reasoning work, and it is not
  part of the last stage's envelope. The run ends when the last stage
  passes validation. The outer control loop hands the result to the
  human-interface component and stops; unless the design says otherwise,
  the review is a separate step started later, not a wait inside the run.
  Record it as an outer-loop step and answer four questions:
  1. *What can the human do?* For example accept, reject, correct, or ask
     for regeneration.
  2. *How does a correction re-enter the sequence?* Step 1's inputs column
     already is the dependency map. A stage is **stale** when it reads the
     corrected artifact, or reads the output of a stale stage. The re-run
     starts at the earliest stale stage and runs the stale stages in order,
     each reading its inputs from persisted artifacts. Stages before that
     point are not re-run. Record the rule, and say whether the unit of
     correction is a whole artifact or something finer.
  3. *What happens to the corrected artifact itself?* It is not
     regenerated, because that would overwrite the correction. It needs a
     marker (for example, human-corrected) that every later re-run
     respects, including one triggered by a change further upstream.
  4. *Are human edits validated?* An edit bypasses the checks that
     generated output passes. Run the same content checks on the edited
     artifact before any dependent stage runs. If it fails, return it to
     the human instead of regenerating from an invalid input.

  Also record whether a re-run ends in another review. It usually does,
  because regenerated output is unreviewed.

None of these three is a sixth relationship or an eighth component; all are
ordinary work of the outer control loop, the same component that invokes
every stage and enforces run-level termination. They are named separately
here only because the per-stage table cannot represent them without
misattributing them to a stage.

**Output of step 4:** a control table per stage, an outer-loop section
covering initial-input entry, any between-stage human-interface steps, and,
where a review follows the last stage, that review's flow and how a
correction chooses where the re-run starts, and the system-level
termination rule (when is the whole run done, failed, or exhausted).

### Step 5 — Framework mapping

**Goal:** translate the design into a chosen framework, and record which
relationships the framework handles and which stay in application code.

**The mapping table.** For each of the six relationships, record who owns
it in the chosen framework:

| Relationship | Framework handles | Application handles |
|---|---|---|
| 1. Reasoning core call | | |
| 2. Capability dispatch | | |
| 3. Memory | | |
| 4. Validation | | |
| 5. Termination | | |
| 6. Human interface | | |

Filling this table for two or three candidate frameworks is also the most
direct way to choose between them: prefer the framework that absorbs the
relationships the design depends on most, and whose defaults you can trust
or override where it does not.

```
  Design (steps 1-4)                     Framework primitives
  +---------------------------+          +-------------------------------+
  | Stages + sequence         |--------->| orchestration unit            |
  | Reasoning-core configs    |--------->| agent / persona object        |
  | Capability contracts      |--------->| tool bindings                 |
  | Control relationships     |--------->| framework features, or        |
  |                           |          | application code around it    |
  +---------------------------+          +-------------------------------+
```

**Output of step 5:** the framework mapping table, and a list of every
relationship the application must implement itself. That list is the
starting point for the detailed design.

### Design checklist

Use this to review a finished design before detailed design begins.

- [ ] Every stage has exactly one responsibility and one output.
- [ ] The sequence is the simplest shape the requirements allow.
- [ ] Every stage is allocated to exactly one reasoning-core configuration.
- [ ] Every capability a stage needs appears on its configuration; no
      configuration has a capability none of its stages need.
- [ ] Every capability has a contract, including side effects, retry
      safety, and approval.
- [ ] Every stage has an explicit decision on memory, validation,
      termination, and human involvement, even if the decision is "none."
- [ ] Something is named as responsible for writing the initial input into
      memory, before the first stage runs — not attributed to the first
      stage's own memory row.
- [ ] Every human-interface step that sits between two stages, rather than
      escalating out of one stage's own validation, is recorded as an
      outer-loop step naming which two stages it sits between.
- [ ] If a human review or approval follows the last stage, it is recorded
      as an outer-loop step: what the human can do, which stages a
      correction makes stale and where the re-run starts, how a
      human-corrected artifact is protected from regeneration, and that
      human edits pass the same content checks as generated output.
- [ ] The whole run has a defined success, failure, and exhausted outcome.
- [ ] The framework mapping names every relationship the application must
      implement itself.

## Glossary

- **Agentic System** — the full seven-component loop (reasoning core,
  control loop, action executors, memory/state, validation/guardrails,
  termination logic, human interface) and the six relationships between
  them, operating together to satisfy the six objectives at the top of this
  document.
- **Agent** — not a component of the system; an abstraction over the
  format-contract half of the control-loop ↔ reasoning-core relationship. A
  named, reusable bundle of persona/instructions, tool schema, and response
  format that the control loop references on a call instead of constructing
  the contract inline each time. Distinct from the colloquial use of
  "agent" to mean the whole running Agentic System.
- **Reasoning core** — the component that does the actual thinking:
  interpreting the goal, deciding the next step, translating between
  language and structured action. Stateless per call; carries no memory of
  its own between invocations.
- **Control loop / orchestrator** — the component that drives the loop's
  cadence: assembling each call to the reasoning core, dispatching its
  response, checking for termination, and touching every other component.
  The only component with a relationship to all the others.
- **Format contract** — the part of the call to the reasoning core that
  specifies the expected shape of its response (a tool schema, a response
  schema, or natural-language formatting instructions). Sent fresh on every
  call, since the reasoning core retains nothing between calls. An Agent is
  the reusable, named form of this contract.
- **Tool** — a definition, not an implementation: a name, description, and
  argument schema describing an available action, included in the format
  contract so the reasoning core knows what it can ask for.
- **Action executor** — the actual code that runs when a tool is invoked;
  invisible to the reasoning core, which only ever sees the tool's name and
  schema, never its implementation.
- **Memory / state** — the component that carries information across calls
  the reasoning core itself cannot retain. Run-scoped (this task's history,
  discarded when the loop ends) or cross-run (facts/preferences persisted
  deliberately and read back via retrieval).
- **Validation / guardrails** — an interceptor, not a peer component in the
  main loop: inspects traffic at other boundaries (most often the reasoning
  core's response) and returns pass, reject-with-reason, or escalate. The
  primary mechanism for distinguishing confident-and-correct output from
  confident-and-wrong output.
- **Termination logic** — the self-check the control loop performs every
  iteration to decide whether to continue, stop with success, stop with
  failure, or stop exhausted (a limit reached with no clean resolution).
- **Human interface** — the conditional relationship that activates only
  when validation escalates, termination reaches exhausted, or a policy
  requires approval before an action fires. The one relationship in the map
  that is not fully automatable by design.
- **Stage** — a framework-agnostic unit of reasoning work with one
  responsibility and one output (design process, step 1). Frameworks give
  it their own names, e.g. a CrewAI `Task` or a LangGraph node. A stage
  owns: a reasoning-core configuration, the action executors it may call,
  its own **inner control loop** (the call/dispatch/repeat cycle — relationship
  1 and relationship 2, cycling until the stage's own final answer — bounded
  by its own, stage-scoped termination condition), and its own scoped
  memory read/write and validation rules. A stage does **not** own the
  **outer control loop** — the orchestrator that decided to start this
  stage, sequences it against other stages, and enforces run-level
  termination across the whole system. The two loops are the same
  relationship-1/relationship-2 mechanism at different scopes, not two
  different kinds of thing: the inner loop is bounded by "has this stage
  produced its output," the outer loop by "is the whole run done, failed,
  or exhausted."
- **Reasoning-core configuration** — the framework-agnostic definition of
  what the reasoning core is told and given for a stage: role,
  instructions, allowed capabilities, output shape (design process, step
  2). The abstract form of an Agent.
- **Capability** — something a stage must be able to do beyond reasoning
  (look up, compute, write, ask). Defined as a contract in step 3, exposed
  to the reasoning core as a tool, and implemented by an action executor.
- **Multi-agent system** — a control loop that swaps in a different Agent
  (a different format contract) across iterations or in parallel, while the
  rest of the loop (control loop, memory, validation, executors) stays the
  same.
- **Stale stage / re-run from a stage** — a stage is stale when it reads an
  artifact that has since been corrected, or reads the output of a stale
  stage. A re-run from a stage runs that stage and every later stale stage
  in order, each reading its inputs from persisted artifacts, and does not
  re-run earlier stages. The corrected artifact itself is not regenerated.

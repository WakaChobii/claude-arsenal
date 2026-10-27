---
name: build-software
description: Orchestrated workflow for building software with subagents, from a single feature up to a whole new app or system. The main session clarifies what to build, sends parallel code-explorer agents to gather context, writes a precise spec, splits it into non-overlapping tasks for parallel code-builder agents, then has code-verifier agents independently test the result and loops fixes until it passes, with ui-reviewer agents checking usability and visual design for anything with a user interface; large builds are broken into milestones that each run this loop, and new projects start with a scaffold. Use this whenever the user wants something built in code: a new feature, a multi-file change, a refactor, a new module or subsystem, or an entire app or tool from scratch, even if they just describe what they want ("add X to my app", "make it so users can Y", "build me a Z", "let's make a new project that...") without mentioning agents or specs. Also use when the user types /build-software. Skip it for one-file tweaks, quick bug fixes, and questions.
---

# Build Software

The main session is the architect and reviewer. It does not read the codebase wholesale or write the implementation itself. Exploration goes to `code-explorer` agents, implementation to `code-builder` agents, independent testing to `code-verifier` agents, and hands-on review of user-facing interfaces to `ui-reviewer` agents; the main session spends its context on understanding the request, designing and writing specs, and deciding what to do with the results. This keeps the main context lean and lets work run in parallel.

If these agents were installed as part of a plugin, they may be listed under a prefixed name (for example `build-team:code-builder`). Use whichever name appears in your list of available agents.

Use these agents rather than general-purpose ones for any job they cover. They carry only the tools they need, so they start with a small context; a general-purpose agent loads every tool and connector, which can multiply the cost of every step it takes.

## 0. Size it up

Judge the size first, because it decides the shape of the whole process:

- **Small** (one or two files, obvious approach): just do it directly. The overhead of this process isn't worth it.
- **Medium** (a feature or change spanning several files, fits in one spec): run steps 1-7 once.
- **Large** (a new subsystem, a major rewrite, or a whole new app): too big for one spec. Read "Large builds and new projects" below first, then run steps 1-7 once per milestone.

If unsure, tell the user which way you're going in one line and proceed.

## Large builds and new projects

One spec for a large build means guessing at details of code that doesn't exist yet, and every wrong guess compounds across parallel builders. Building in milestones means each spec is written against real, verified code.

**Plan milestones.** Split the build into 3-8 milestones, each ending in something that works and can be verified on its own. A typical order is foundation (data model, core types, storage), then core logic, then interfaces (API, UI, CLI), then integration and polish. Write the plan as a short list: each milestone's goal, what it delivers, and how you'll know it works.

**Get the plan approved.** Show the user the milestone plan, plus any major technical choices (stack, architecture, key libraries), before building anything. Redirecting now costs a message; redirecting after three milestones costs a rebuild. Ask every question the whole plan will need in this same round, including ones that only matter in later milestones (licences, accounts or API keys, paid services, platform choices), so the build doesn't stop partway to wait for an answer.

**New projects start with a scaffold.** With no existing code, explorers have nothing to read and builders have no conventions to match, so each parallel builder would invent its own. Make milestone 1 a scaffold, built by a single builder or by you: project structure, stack and dependencies, config, a test setup that runs, one small working example of each layer, and a short conventions note (naming, file layout, error handling, testing pattern). Verify it runs before parallel work begins. Every later spec points builders at the scaffold as the pattern to follow.

**Between milestones.** After each milestone is verified, give the user a brief update: what now works, anything that changed from the plan, and what's next. Then explore the code that actually exists before writing the next milestone's spec, and adjust the remaining plan if the build taught you something. Keep going without waiting unless something needs the user's decision.

## 1. Understand the request

Make sure you know what "done" looks like before any agent runs, because every later step inherits mistakes made here.

- Restate the goal in a few sentences: what it does, for whom, and how you'll know it works.
- Ask the user only about decisions that would change what gets built (behavior, UX, data, scope, and for new projects, stack or platform if they care). Don't ask things the code can answer; that's what exploration is for.
- If the user already gave a clear brief, don't interrogate them. Move on.
- Batch your questions into one round rather than asking as they come up: every question mid-build stops all the work until the user answers.
- **Pre-flight check** before the first agent runs, so the build doesn't stall halfway: the project builds and its tests run as they are now, there's enough free disk space for the build (compiled languages like Rust or C++ can need several GB), and no leftover processes from earlier sessions are holding the ports the app uses. Fix or ask about anything wrong now, in the same round as your other questions.

## 2. Explore

Send `code-explorer` agents to gather what you need to write the spec. Launch them all in one message so they run in parallel. (On a brand-new project's first milestone there's nothing to explore; skip to the spec.)

- Split the investigation into 1-4 focused questions, each covering a distinct area. For example: "how does the existing settings page load and save data", "how are API routes registered and authenticated", "what test setup exists for the frontend". Overlapping questions waste tokens on duplicate reading.
- Give each explorer: the overall goal (one or two sentences, so it knows what's relevant), its specific question, any files or areas you already know about, and what to return. Ask it to include change impact and shared hotspot files when the goal is a spec.
- Don't read the codebase yourself beyond a quick spot check of something an explorer reported. If a report leaves a gap that matters, send a follow-up explorer (or `SendMessage` the same one) with a narrow question.

## 3. Write the spec

This is the design step, and it belongs to you, not the agents. Decide the architecture, data model, interfaces, and approach yourself: weigh the alternatives, think through edge cases and failure modes, and choose. The explorer reports are evidence about the existing code, not a design to transcribe, and builders will implement what you write without second-guessing it, so the quality of the whole build is set here.

The spec is the only context builders get, so anything not in it doesn't exist for them. Use this structure:

```markdown
# Spec: <feature or milestone>
## Goal
What it does and why, in 2-4 sentences.
## Behavior
Concrete requirements, including edge cases and error handling.
## Shared contracts
Every interface that more than one task touches: function signatures, types, API shapes, DB schema, event names, config keys. Define these exactly, because parallel builders can't coordinate with each other.
## Conventions
Patterns, helpers, and example files to follow (from the explorers or the scaffold, with file paths).
## Tasks
### Task N: <name>
- Owns: files this task may create or edit (no other task touches these)
- Does: what to implement
- Depends on: other tasks whose output it needs, if any
- Tests: the tests this task must write, naming the behaviors and edge cases they cover
- Done when: acceptance criteria for this task
## Verification
Commands that prove the whole thing works (tests, build, type-check, lint), plus how to exercise it for real (run the app, call the endpoint, use the CLI) and which edge cases to try.
## Out of scope
What not to build or change.
```

**Tests are part of the design.** Passing tests only mean something if tests cover the new behavior, so every task that adds or changes behavior lists the tests it must write: the main path, the edge cases, and the error cases. Follow the project's existing test setup; if there is none and the build is more than throwaway, make setting one up an early task (for a new project, it's part of the scaffold). Acceptance criteria should be concrete enough that a verifier can check them as pass or fail.

For a medium build that's ambiguous or high-stakes, show the user a short summary of the spec (goal, tasks, notable decisions) and get an OK before building. For a straightforward one, or if the user said to just go, proceed. For a large build, the milestone plan approval usually covers this; only stop again if a milestone's spec makes a decision the user would want a say in.

## 4. Split into tasks

How the work is split decides whether parallel builders collide.

- **Each file has exactly one owner.** Two builders editing the same file in the same checkout will overwrite each other.
- **Shared hotspots** (route registries, barrel/index exports, shared type files, schema, config): give them to one task, or have that task run first, or make the edit yourself before or after the builders.
- **Dependencies:** tasks that need another's output go in a later wave. Shared contracts defined in the spec let many tasks start at once even when they reference each other's interfaces.
- **Task size:** each task should be something one builder can finish and verify on its own. Prefer a few meaningful tasks over many tiny ones, since each builder has to re-read context. But don't make tasks so big that a builder runs for a very long time: every step re-reads everything it has gathered, so one task that grows to a huge context costs more than two half-size tasks. Split a task that would touch many large files or several separate concerns.
- **Balance the wave.** A wave takes as long as its slowest builder, and the others sit idle waiting. Estimate each task's size, and if one is much bigger than the rest, split it, or start it in an earlier wave so it isn't holding up everyone else.
- **Point builders at the right places.** Give each task the specific files, functions and line ranges the explorers found, so builders read those instead of whole files.
- If file ownership genuinely can't be separated and the project is a git repo, `isolation: "worktree"` keeps builders apart, but you'll then have to merge their branches. Disjoint files is usually simpler.

## 5. Build

Launch one `code-builder` per task in the current wave, all in one message so they run in parallel.

Each builder prompt contains: the full spec (or at least Goal, Shared contracts, Conventions, Out of scope), its own task section, the files it owns, and the files it must not touch. Builders don't see this conversation, so don't refer to "what we discussed".

When builders run in parallel, tell each one to verify with only its own tests (plus a real run of its own piece), not the full suite. Mid-wave, the full suite picks up other builders' half-finished files, and every builder ends up reporting failures that aren't its own. The full suite runs once the wave is done, in step 6. A builder working alone can still run everything.

The builder defaults to Sonnet, and nearly every task should stay there. `haiku` is fine for purely mechanical work.

When a task feels too hard for Sonnet, the usual problem is that the spec still leaves real decisions open. Fix that first: write the exact algorithm, data flow, invariants, and known pitfalls into the task so the builder is following decisions, not making them. Most "tricky" tasks become routine once the hard thinking is in the spec, and that thinking belongs to you anyway.

Use `opus` for a builder only when correctness depends on subtle reasoning that can't be fully written down ahead of time, such as real-time or lock-free code, concurrency, security-sensitive logic, or data-integrity code where a quiet mistake corrupts data. Never use it for UI, glue code, CRUD, wiring, or routine features, however large. When you do use it, give the user a one-line reason in your progress update so the choice is visible. These rules win over model choices written in a plan, handoff note, or earlier spec, since those are often written before this guidance applied. When you write a handoff or plan yourself, leave model choices out of it.

Wait for a wave to finish before launching the next one that depends on it.

## 6. Verify and fix

Builder reports describe what they intended, not necessarily what happened, and builders checking their own work tend to see what they meant to write. So verification is done independently, by a `code-verifier` agent, rather than by you reading every diff (which would spend the main context this process exists to save).

**When:** after each wave of builders whose work forms a checkable whole, and always at the end of a medium build or a milestone. One verifier over a whole wave beats one per builder, because most bugs live at the seams between tasks. Verification blocks the next step, so never run verifiers one after another over the same milestone (for example a backend pass, then a separate full-stack pass): use one verifier for the whole thing, or if it's too big for one, split it by area and run those verifiers in parallel.

**Brief the verifier with:** the full spec, the list of tasks and files that changed (or the git range), the builders' "Not done / concerns" notes, and on a large build the earlier milestones' verification commands so it can catch regressions. Tell it to use the project's existing build output rather than a fresh build directory. It defaults to Sonnet; use `model: "opus"` for a large milestone or anything security- or data-sensitive, since finding subtle bugs takes more judgment than writing code to a spec.

**Act on the report:**
- **PASS:** spot-check one or two of its claims that matter most (for example, rerun the main test command yourself), then move on.
- **FAIL:** for each real bug, decide the fix. Small integration fixes (a wrong import, a missing export) you can make yourself. Otherwise send the owning builder a targeted fix task: the bug, the evidence, and the expected behavior. If a bug is really a flaw in the spec, fix the spec first, then the code. Then run the verifier again on what changed.
- **PARTIAL:** decide whether the unverified items matter. Verify them another way, or carry them into your report to the user as not verified.
- **Cap the loop.** If the same problem survives two fix-and-verify rounds, stop and bring it to the user with what was tried, instead of looping.

Also read each builder's "Not done / concerns" yourself. Don't drop those on the floor.

### UI review
When the build adds or changes an interface people use (a web or desktop app's screens, not an API or a CLI), run a `ui-reviewer` once the verifier has passed, so it reviews working code. The verifier checks that the spec was met; the reviewer checks that the result is easy and pleasant to use, which a spec rarely captures.

- **One reviewer per area or flow.** Screenshots stay in an agent's context, so a single reviewer covering everything gets slower and more expensive with every step. Give each reviewer a focused scope (for example "the recording flow" or "the settings dialog"), small enough to cover in about 30 screenshots. Separate areas can run in parallel if the app can run more than once at the same time (separate ports); otherwise run them one after another.
- **Brief it with:** what the feature is for and who uses it, the flows to walk through, how to run the app (commands, ports, test data), the window sizes to check, and any folder of earlier review scripts it can reuse.
- **Turn findings into fixes.** Send Blocker, Major and Minor issues to builders as fix tasks, using the reviewer's concrete fixes (exact values, wording, behavior). Batch Polish items into one task, and skip any that aren't worth it.
- **Re-check with a fresh reviewer.** After the fixes, start a new `ui-reviewer` (not the old one) with only the list of issues to re-check and the earlier scripts. It starts with a small context and doesn't re-review everything.
- **Cap it.** One review, one fix pass, and one re-check is the normal loop. Only go further for Blocker or Major issues that are still open, and stop and ask the user if a design question keeps coming back.

## 7. Report

Tell the user what was built, how it was verified (the verifier's verdict and real results, including anything that failed or wasn't checked), any decisions made along the way, and anything left open. On a large build, this is the per-milestone update; give the full report at the end. Don't commit or push unless the user asked.

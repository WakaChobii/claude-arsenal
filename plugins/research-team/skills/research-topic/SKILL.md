---
name: research-topic
description: Orchestrated research workflow for learning a topic in depth or answering a broad question from many sources. The main session scopes the request, maps the topic into distinct angles, sends parallel web-researcher agents (web pages plus YouTube transcripts, with source-quality and recency vetting) to cover them, fills gaps with targeted follow-ups, then synthesizes one brief that separates research-backed facts, expert consensus and trends, and saves it as a document. Use this whenever the user wants to learn, master or get up to speed on a subject ("teach me everything about X", "I want to become an expert in Y", "what's the current state of Z"), wants a landscape or comparison across many options (tools, products, approaches, competitors), needs a knowledge base to build a skill, agent or plan from, or asks any research question too broad for one researcher, even if they don't mention agents or research. Also use when the user types /research-topic. Skip it for single facts or narrow questions; send one web-researcher agent for those.
---

# Research Topic

The main session is the research lead: it decides what to cover, briefs the researchers, judges their reports, and writes the synthesis. It does not do the bulk reading itself. Searching and reading go to `web-researcher` agents running in parallel, so the main context holds only their distilled reports and the user gets broad coverage in the time one researcher takes.

If the agent was installed as part of a plugin, it may be listed under a prefixed name (for example `research-team:web-researcher`). Use whichever name appears in your list of available agents.

## 0. Size it up

- **Quick** (a focused question with a few parts): 1-2 researchers, no plan approval, answer in chat. If it's really a single question, skip this skill and send one researcher or search directly.
- **Standard** (a topic overview, a comparison, "what's the best way to X"): 3-5 researchers, one wave plus follow-ups if needed, saved brief.
- **Deep** (learning or mastering a field, a decision with high stakes, "everything about X"): 5-8 researchers, plan approved by the user first, up to two follow-up waves, saved brief with a learning path.

If unsure, say in one line which size you're going with and proceed.

## 1. Scope

Know what the user needs before any researcher runs, because the angles depend on it.

- What's the goal: learning a skill, making a decision, building something, staying current? Who's it for, and at what level (beginner, intermediate, already experienced)?
- What's in and out of scope (platforms, regions, price ranges, time period)?
- Anything they already know, trust, or want excluded?

Ask only about what would change the plan. If the request is already clear, move on.

## 2. Map the topic

Split the topic into 3-8 **distinct angles** that together cover it and don't overlap. Overlapping angles make researchers read the same pages twice and return duplicate reports.

Good angles usually mix these kinds:
- **Fundamentals:** the core principles and mental models that don't change much.
- **Current practice:** how experts do it now, standard tools and workflows, what changed recently.
- **Evidence:** what research, data or testing shows works (and what doesn't).
- **Landscape:** the options, products, tools or schools of thought, compared.
- **Real-world experience:** common mistakes, pitfalls, what practitioners wish they'd known (forums, Reddit, practitioner videos).
- **Trends:** what's new or fashionable, and how much of it is likely to last.
- **Learning resources** (when the goal is learning): the best books, courses, channels and references, and in what order.

**Assign shared basics to exactly one angle.** Facts that several angles touch, like core thresholds, standard sizes, definitions or the current version of something, belong to one researcher. In every other brief, list them under "Not your angle" and say who covers them. Those researchers may mention a shared fact in passing, but must not research it. In one past run, four researchers each re-researched the same contrast ratios and touch-target sizes. If you need such a fact to be certain, a single owner verifying it against the primary source is better than several half-checks.

For each angle, pick **trusted starting sources** from your own knowledge: the official bodies, standards, research groups, canonical references and respected practitioners in that field. Researchers still verify and look beyond them, but seeds anchor them on quality instead of whatever search ranks first.

For a deep build, show the user the plan (angles, what each will answer, seed sources) and get an OK before launching. It costs one message and saves a wasted wave.

## 3. Brief and launch the researchers

Launch one `web-researcher` per angle, **all in one message** so they run in parallel. Keep to about 6 per wave; more risks rate-limiting from search and YouTube and rarely adds coverage.

Each researcher sees only its brief, so make it complete:

```markdown
Overall goal: <the user's goal and level, in 1-2 sentences, so it knows what's relevant>
Your angle: <the specific sub-topic and the 2-5 questions it must answer>
Not your angle: <the other angles, one line each, plus any shared basics owned by another researcher, so it doesn't drift into them>
Depth: <quick / medium / thorough>
Start from: <seed sources>, then go beyond them
Time-sensitivity: <fast-moving or stable; prefer sources from <period> where it matters>
YouTube: <include / skip>, and what videos are useful for here (talks, tutorials, reviews)
Label each finding as one of: research-backed (tested or measured), expert consensus (most credible experts agree), contested (credible experts disagree), trend/taste (popular now, may not last)
Return: your standard report, plus the 3-5 best sources for someone learning this angle, with why
```

Researchers run on Sonnet by default, which is right for this work. Don't override the model.

## 4. Review and fill gaps

When the wave returns, read each report critically:

- **Coverage:** did every angle's questions get answered from good sources? Note gaps and "not confirmed" items that matter.
- **Conflicts across reports:** two researchers may disagree. Decide if dates explain it (one is outdated), if one source is stronger, or if the field genuinely disagrees.
- **Weak spots:** claims resting on a single tier-3 source, low confidence, or anything that sounds surprising.

For gaps and conflicts that matter, send targeted follow-ups: a narrow brief to a new researcher (or `SendMessage` to the original one, which still has its context). Cap it at two follow-up waves; if something is still unresolved, report it as open rather than looping.

Don't re-research angles yourself. If you need to check one claim, a single quick search is fine.

## 5. Synthesize

This is the main session's real work: turn several reports into one understanding. Don't paste the reports together. Organize by what the user needs to know, merge overlapping findings, and cite as you go.

Brief structure (drop sections that don't apply):

```markdown
# <Topic>: research brief
As of <month year>. <One line on scope and depth.>

## Summary
The essentials in a few paragraphs: what matters most, and the biggest takeaways.

## Core knowledge
Organized by theme, not by researcher. Each key point labeled
(research-backed / consensus / contested / trend) and cited with links.

## Where experts disagree
The real debates, each side's best argument, and where the evidence leans.

## Trends vs. what lasts
What's new and popular, and which of it is likely durable versus fashion.

## Common mistakes
What beginners and intermediates get wrong.

## Learning path  (when the goal is learning)
Ordered steps from where the user is to where they want to be, with the specific
resource for each step and what to practice.

## Best sources
The top resources overall, grouped by type (references, research, courses, channels,
communities), each with one line on why it's worth their time.

## Open questions
What couldn't be confirmed, and what would settle it.
```

Keep the confidence labels and the researchers' caveats. If a claim was contested or unconfirmed in the reports, it stays that way in the brief.

## 6. Deliver

- **Quick:** answer in chat with citations.
- **Standard and deep:** save the brief as a Markdown file in the current working folder (for example `research-<topic>.md`), or as a document or page if the user prefers one, and tell them where it is. Then give a short summary in chat: the top 3-5 takeaways, any open questions, and the obvious next step (a deeper dive on one angle, a decision, or starting the learning path).

Mention roughly what it took (how many researchers, waves, and sources read), so the user can calibrate how much to ask for next time.

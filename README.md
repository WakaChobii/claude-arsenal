# Claude Arsenal

My collection of [Claude Code](https://claude.com/claude-code) add-ons: skills, subagents and workflows. Each group is
its own plugin, so you install only what you need. Every installed skill and agent adds a little to Claude's context in
every session, so keeping installs lean pays off.

| Plugin | What's in it | What it's for |
|---|---|---|
| [`build-team`](plugins/build-team) | 4 subagents + 1 skill | Building software with a team of agents: explore, spec, build in parallel, verify, review the UI |
| [`research-team`](plugins/research-team) | 1 subagent + 2 skills | Internet research: vetted, cited answers from web pages and YouTube videos, or a parallel team that researches a whole topic |
| [`tiktok-skills`](plugins/tiktok-skills) | 2 skills | Making TikTok videos: TikTok-style on-screen text and AI product-reveal remakes |

## Install
In Claude Code, add the marketplace once:

```
/plugin marketplace add WakaChobii/claude-arsenal
```

Then install the plugins you want:

```
/plugin install build-team@claude-arsenal
/plugin install research-team@claude-arsenal
/plugin install tiktok-skills@claude-arsenal
```

Or copy individual pieces by hand: skill folders go in `~/.claude/skills/` (for example
`~/.claude/skills/build-software/`), and agent files go in `~/.claude/agents/`. Every skill folder and agent file is
self-contained.

> This repo used to be `tiktok-skills`. If you installed from it before, run `/plugin marketplace add
> WakaChobii/claude-arsenal` and reinstall `tiktok-skills@claude-arsenal`.

---

## build-team
A small software team for Claude Code. Your main session (ideally your strongest model) acts as the lead: it
understands the request, designs the solution and reviews the results. Cheaper, specialised subagents do the reading,
coding and testing, often several at once.

| Piece | Type | Role |
|---|---|---|
| [`code-explorer`](plugins/build-team/agents/code-explorer.md) | subagent (read-only) | Investigates a question in the codebase and returns a short briefing with `file:line` references instead of raw file dumps |
| [`code-builder`](plugins/build-team/agents/code-builder.md) | subagent | Implements a well-scoped spec exactly, matches the codebase's conventions, stays inside its assigned files, verifies, and reports |
| [`code-verifier`](plugins/build-team/agents/code-verifier.md) | subagent (QA) | Independently tries to prove the work is wrong: checks each acceptance criterion, runs the tests, exercises the feature with edge cases, reports pass/fail with evidence |
| [`ui-reviewer`](plugins/build-team/agents/ui-reviewer.md) | subagent (design review) | Uses the app in a browser like a first-time user, judges usability and visual design (hierarchy, spacing, typography, color, feedback, accessibility), and returns ranked issues with exact, buildable fixes |
| [`build-software`](plugins/build-team/skills/build-software/SKILL.md) | skill | The workflow that runs the team |

**How `build-software` works**
1. **Size it up.** Small changes are done directly. Medium ones run the loop once. Large builds and brand-new projects
   are split into milestones (new projects start with a scaffold), and you approve the plan first. Milestones
   that don't depend on each other run in parallel (2-3 at once), then join in an integration milestone.
2. **Understand.** It clarifies only the decisions that would change what gets built.
3. **Explore.** It sends `code-explorer` agents out in parallel, each with a focused question.
4. **Design the spec.** The main session decides the architecture, interfaces and tests, and writes them into a spec,
   including exact shared contracts so parallel builders agree without talking to each other.
5. **Build.** It splits the work so every file has exactly one owner, then runs `code-builder` agents in parallel.
6. **Verify and fix.** A `code-verifier` checks the combined result. Failures go back to the owning builder, and the
   loop stops and asks you if the same problem survives two rounds. If the build changed screens people use,
   `ui-reviewer` agents (one per area) then review them, builders apply the fixes, and a fresh reviewer re-checks.
7. **Report.** It tells you what was built, how it was verified, and anything left open.

**Use it** by describing what you want built, or run `/build-software` (or `/build-team:build-software` when
installed as a plugin). To make Claude reach for it on its own, add a line like this to your `~/.claude/CLAUDE.md`:

```
For building anything in code beyond a small change (a feature, a multi-file change, a new subsystem, or a whole app),
use the build-software skill. Do small one-file changes directly.
```

**Models:** the subagents run on Sonnet by default, and each one only gets the file and shell tools it needs (no
connectors), so they start with a small context. The skill keeps Opus for the main session's design work, and only
lets a builder use it when a task genuinely needs it. The agents also follow token-saving habits: reading only the
part of a file they need, editing with the Edit tool instead of patch scripts, trimming command output, and (for
the UI reviewer) checking facts from the page instead of screenshots and keeping screenshots small.

---

## research-team
Research that you can trust. A cheap, specialised researcher does the searching and reading, judges every source, and
hands back a short cited answer, so your main session never fills up with raw web pages.

| Piece | Type | Role |
|---|---|---|
| [`web-researcher`](plugins/research-team/agents/web-researcher.md) | subagent | Researches one question: plans the search, vets each source for quality and recency, reads the real pages and YouTube transcripts, cross-checks claims, and returns a cited report that separates confirmed facts from uncertain ones |
| [`research-topic`](plugins/research-team/skills/research-topic/SKILL.md) | skill | Splits a big topic into distinct angles, runs several web-researchers in parallel, fills gaps, and writes one cited brief (summary, core knowledge, debates, trends vs. what lasts, common mistakes, learning path, best sources) |
| [`youtube-transcript`](plugins/research-team/skills/youtube-transcript/SKILL.md) | skill | Gets any YouTube video's transcript plus source metadata (channel, subscribers, upload date, views) in seconds, so videos can be read, quoted and cited with timestamps |

**How `web-researcher` judges sources**
- **Ranks sources in tiers.** Official sources, original research and changelogs come first, then reputable expert
  outlets, then forums and practitioner videos. SEO listicles, affiliate roundups and AI filler are avoided.
- **Checks each source.** It looks at who is behind it, checks conflicts of interest, looks for evidence, and
  confirms that other good sources agree.
- **Watches recency.** It decides how fast the topic moves, searches for the current year on fast topics, and
  checks each page's real date.
- **Cross-checks.** Key claims need one primary source or two independent ones. It never invents a URL, quote or
  number.
- **Handles pages that need JavaScript.** It gets the same content as plain data instead, for example Apple's HIG as
  JSON, or raw GitHub files.

**YouTube.** `youtube-transcript` uses YouTube's own captions (about 3-6 seconds per video). It falls back to
yt-dlp, then to local speech-to-text for videos without captions. Results are cached.

The tool runs in its own Python environment at `~/.claude/youtube-transcript-env`. Claude creates it on first use
(Python 3.11+, about a minute). See the skill's First-time setup section.

**Safety.** Web pages can contain text that tries to trick AI agents, so `web-researcher` has no file-writing tool
and no connectors. Its shell is locked by a hook (`hooks/hooks.json`) to the transcript command only. That hook only
restricts `web-researcher`: your main session and other agents are not affected.

**Use it** by asking anything that needs current information from the internet, or say "use the web-researcher".
Run `/research-topic` (or `/research-team:research-topic`) for a whole subject. To make Claude reach for them on
its own, add lines like these to your `~/.claude/CLAUDE.md`:

```
For anything on the internet, send a web-researcher agent instead of running web searches yourself.
For learning a topic in depth or research too broad for one question, use the research-topic skill.
```

---

## tiktok-skills

| Skill | What it does |
|---|---|
| [`add-text`](plugins/tiktok-skills/skills/add-text/SKILL.md) | Burns on-screen text onto your video that looks exactly like TikTok's own in-app text |
| [`product-reveal`](plugins/tiktok-skills/skills/product-reveal/SKILL.md) | Remakes a reference TikTok's product shots with your product, in new rooms, with no text |

### add-text
Makes text that looks like TikTok's in-app text tool: TikTok Sans "Classic", in plain white, white with a black
outline, pale yellow, gold or lilac, with iPhone emoji. The styles were measured frame by frame from real TikToks.

- **Copy a reference TikTok's text** onto your own video, matching its wording, line breaks, size, position and the
  exact frames each caption appears and disappears. Then it checks the result side by side with the reference.
- **Write new captions** in the same style.

Ask Claude something like:
- *"Copy the text from `reference.mp4` onto `my video.mp4`"*
- *"Add the text 'wait for it…' in the middle of `clip.mp4` for the first 3 seconds, outline style"*

You get `my video (WITH TEXT).mp4` next to your original, which stays untouched.

### product-reveal
Give it a reference TikTok and a photo of your product. It finds the product shots (product on a surface, held up,
pointed at), removes the captions, puts your product's scene in a new room, and re-assembles the section on the same
frames as the reference. On close-ups it puts the real printed label back, because AI video edits garble small text.

Ask Claude something like:
- *"Remake the product shots from `reference.mp4` with my product (`packshot.jpg`) in a bright bathroom"*

**Needs a [Higgsfield](https://higgsfield.ai) account connected to Claude** (its MCP connector), and uses
Higgsfield credits: about 10.5 per product shot at the time of writing. Claude tells you the total before it starts
and asks before spending anything extra. The result is AI-edited, so turn on TikTok's AI-generated content label
when you post it.

### Setup
Setup is automatic. The first time you use a TikTok skill, Claude:
1. creates a private Python environment in `~/.claude/tiktok-skills/` and installs what the skills need (about
   1-2 minutes, once), and
2. checks for **ffmpeg**. If it's missing, Claude asks you, then installs it (`winget` on Windows, `brew` on Mac).

You need **Python 3.9 or newer** ([python.org](https://www.python.org/downloads/)). If you don't have it, Claude
will tell you.

---

## Repo layout

```
.claude-plugin/marketplace.json   lists the plugins below
plugins/
  build-team/
    .claude-plugin/plugin.json
    agents/                       code-explorer, code-builder, code-verifier, ui-reviewer
    skills/build-software/
  research-team/
    .claude-plugin/plugin.json
    agents/                       web-researcher
    hooks/hooks.json              locks web-researcher's shell to the transcript tool
    skills/research-topic/
    skills/youtube-transcript/
  tiktok-skills/
    .claude-plugin/plugin.json
    skills/add-text/
    skills/product-reveal/
```

To add a new plugin, create `plugins/<name>/` with a `.claude-plugin/plugin.json` and its `skills/` and/or `agents/`
folders, then list it in `.claude-plugin/marketplace.json`.

## Credits and licences
- Code: MIT licence (see `LICENSE`).
- Font: [TikTok Sans](https://github.com/tiktok/TikTokSans), © TikTok Inc., SIL Open Font License 1.1 (see
  `plugins/tiktok-skills/skills/add-text/fonts/OFL.txt`).
- Emoji images are downloaded on first use from the [emoji-data](https://github.com/iamcal/emoji-data) project and
  aren't included in this repo.

Not affiliated with or endorsed by TikTok or Higgsfield.

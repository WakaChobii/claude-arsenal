# TikTok Skills

[Claude Code](https://claude.com/claude-code) skills for making TikTok videos.

| Skill | What it does |
|---|---|
| [`add-text`](skills/add-text/SKILL.md) | Burns on-screen text onto your video that looks exactly like TikTok's own in-app text |
| [`product-reveal`](skills/product-reveal/SKILL.md) | Remakes a reference TikTok's product shots with your product, in new rooms, with no text |

## add-text
Makes text that looks like TikTok's in-app text tool: TikTok Sans "Classic", in plain white, white with a black
outline, pale yellow, gold or lilac, with iPhone emoji. The styles were measured frame by frame from real TikToks.

- **Copy a reference TikTok's text** onto your own video, matching its wording, line breaks, size, position and the
  exact frames each caption appears and disappears. Then it checks the result side by side with the reference.
- **Write new captions** in the same style.

Ask Claude something like:
- *"Copy the text from `reference.mp4` onto `my video.mp4`"*
- *"Add the text 'wait for it…' in the middle of `clip.mp4` for the first 3 seconds, outline style"*

You get `my video (WITH TEXT).mp4` next to your original, which stays untouched.

## product-reveal
Give it a reference TikTok and a photo of your product. It finds the product shots (product on a surface, held up,
pointed at), removes the captions, puts your product's scene in a new room, and re-assembles the section on the same
frames as the reference. On close-ups it puts the real printed label back, because AI video edits garble small text.

Ask Claude something like:
- *"Remake the product shots from `reference.mp4` with my product (`packshot.jpg`) in a bright bathroom"*

**Needs a [Higgsfield](https://higgsfield.ai) account connected to Claude** (its MCP connector), and uses
Higgsfield credits: about 10.5 per product shot at the time of writing. Claude tells you the total before it starts
and asks before spending anything extra. The result is AI-edited, so turn on TikTok's AI-generated content label
when you post it.

## Install
As a plugin (both skills, kept up to date). In Claude Code, run:

```
/plugin marketplace add WakaChobii/tiktok-skills
/plugin install tiktok-skills@tiktok-skills
```

Then use them by asking, or run `/tiktok-skills:add-text` or `/tiktok-skills:product-reveal`.

Or copy just the skill you want: put its folder from `skills/` into `~/.claude/skills/` (for example
`~/.claude/skills/add-text/`). Each skill folder is self-contained.

## Setup
Setup is automatic. The first time you use a skill, Claude:
1. creates a private Python environment in `~/.claude/tiktok-skills/` and installs what the skills need (about
   1-2 minutes, once), and
2. checks for **ffmpeg**. If it's missing, Claude asks you, then installs it (`winget` on Windows, `brew` on Mac).

You need **Python 3.9 or newer** ([python.org](https://www.python.org/downloads/)). If you don't have it, Claude
will tell you.

## Credits and licences
- Code: MIT licence (see `LICENSE`).
- Font: [TikTok Sans](https://github.com/tiktok/TikTokSans), © TikTok Inc., SIL Open Font License 1.1 (see
  `skills/add-text/fonts/OFL.txt`).
- Emoji images are downloaded on first use from the [emoji-data](https://github.com/iamcal/emoji-data) project and
  aren't included in this repo.

Not affiliated with or endorsed by TikTok or Higgsfield.

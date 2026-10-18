# TikTok Text

A [Claude Code](https://claude.com/claude-code) plugin that burns on-screen text onto your videos and makes it look
exactly like TikTok's own in-app text tool: TikTok Sans "Classic", in plain white, white with a black outline, pale
yellow, gold or lilac, with iPhone emoji.

It can:
- **Copy a reference TikTok's text** onto your own video, matching its wording, line breaks, size, position and the
  exact frames each caption appears and disappears. Then it checks the result side by side with the reference.
- **Write new captions** in the same style.

The styles were measured frame by frame from real TikToks.

## Install
In Claude Code, run:

```
/plugin marketplace add WakaChobii/tiktok-text
/plugin install tiktok-text@tiktok-text
```

Or just tell Claude: *"install the plugin from github.com/WakaChobii/tiktok-text"*.

## Use
Ask Claude something like:
- *"Copy the text from `reference.mp4` onto `my video.mp4`"*
- *"Add the text 'wait for it…' in the middle of `clip.mp4` for the first 3 seconds, outline style"*

Or run `/tiktok-text:add-text`. You get `my video (WITH TEXT).mp4` next to your original, which stays untouched.

## Setup
Setup is automatic. The first time you use it, Claude:
1. creates a private Python environment for the plugin and installs what it needs (about 1-2 minutes, once), and
2. checks for **ffmpeg**. If it's missing, Claude asks you, then installs it (`winget` on Windows, `brew` on Mac).

You need **Python 3.9 or newer** ([python.org](https://www.python.org/downloads/)). If you don't have it, Claude
will tell you.

## Credits and licences
- Code: MIT licence (see `LICENSE`).
- Font: [TikTok Sans](https://github.com/tiktok/TikTokSans), © TikTok Inc., SIL Open Font License 1.1 (see
  `plugins/tiktok-text/skills/add-text/fonts/OFL.txt`).
- Emoji images are downloaded on first use from the [emoji-data](https://github.com/iamcal/emoji-data) project and
  aren't included in this repo.

Not affiliated with or endorsed by TikTok.

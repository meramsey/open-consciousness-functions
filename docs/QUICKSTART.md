# OCF quickstart

Choose a practice, choose a voice, preview a session, create an edition, then
listen and review it. You can begin by reading guides; creating audio is optional.

## If you already have a listening edition

Open your configured private listening portal, or open `guides/index.html` in a
listener package. Choose the function and edition, read its guide, and use the
matching transcript while listening. A guide or catalog entry alone does not
mean its recording is included. See the [listening guide](LISTENING_GUIDE.md) for
comfort, volume, stereo and between-session practice.

Keep earlier editions when trying a new voice, mix or pacing. Portal notes belong
to the selected edition. A completed technical check does not mark an edition as
personally reviewed or approved for publication.

## Create your first session

### 1. Install and check your tools

Use the expandable [installation instructions in the README](../README.md#get-started),
then run these commands from the checkout with its Python environment active:

```bash
python scripts/ocf.py doctor --json
python scripts/ocf.py voice doctor
```

Core browsing and planning work without speech or background-audio engines.
Creating audio needs the tools and models reported for that workflow. Discovery
does not install or download them. [Setup](SETUP.md) explains how to inspect an
existing installation before adding anything.

### 2. Choose and understand one function

```bash
python scripts/ocf.py functions list
python scripts/ocf.py functions describe OCF-FND-002 --rich
python scripts/ocf.py audio eligibility OCF-FND-002 --locale en-US
python scripts/ocf.py audio plan OCF-FND-002 --locale en-US --expand
```

This example selects Focus, the attention-oriented function. It is distinct from
the Focus 10/11 stages used in audio designs. Replace its ID with your chosen
function. Read the description, exact cues, instructions and current availability
before rendering. An ineligible or planned function needs its missing work
resolved; do not bypass the eligibility report.

### 3. Choose a voice

```bash
python scripts/ocf.py voice list
python scripts/ocf.py voice capabilities --json
```

Choose an installed, available voice by its reported ID. A metadata entry is not
necessarily an installed model. Run `voice smoke VOICE_ID --locale en-US` with
your chosen ID to verify fresh short synthesis in memory; no file is exported. Use a voice
audition when you want a saved clip to listen to.

To use your own voice, follow the [private voice walkthrough](VOICE_PACKS.md):
prepare an authorized reference, create a private pack, inspect it, then audition
new text before selecting it for a session. This reference-based process does
not train a new model. Existing complete or partial recordings can instead use
[recorded narration](RECORDED_NARRATION.md) or [hybrid narration](HYBRID_NARRATION.md).

### 4. Preview and render a new edition

Replace `VOICE_ID` with the voice you verified and `NEW_OUTPUT_DIRECTORY` with a
new private directory. Keep completed editions outside disposable workspace
cache; see [durable private storage](PRIVATE_LISTENING_DELIVERY.md#durable-private-storage).

```bash
python scripts/ocf.py audio render OCF-FND-002 --locale en-US --voice VOICE_ID --output NEW_OUTPUT_DIRECTORY --dry-run
python scripts/ocf.py audio render OCF-FND-002 --locale en-US --voice VOICE_ID --output NEW_OUTPUT_DIRECTORY
```

The dry run checks the request without producing the session. The second command
renders it. Do not start another render for the same destination while one is
running. Keep the resulting master, transcript, timing and integrity receipts
together. Use [session overrides](SESSION_OVERRIDES.md) only when you deliberately
want a different supported composition, pacing or mix.

Standalone Preparation Learning uses its [dedicated private-session pathway](PRIVATE_LISTENING_DELIVERY.md),
with three Eleven visits and 510 seconds of practice. It is not a substitute
function identity for a routine session.

### 5. Listen, compare and keep your notes

Start at a comfortable level. Check that the words are clear, pauses feel useful,
and the ending is appropriate for what you are doing next. Pause or stop whenever
you wish. Preserve the master when making a smaller browser/mobile copy.

A private portal discovers completed editions through verified manifests;
copying an unfinished folder into its library does not publish it. Follow the
[private delivery guide](PRIVATE_LISTENING_DELIVERY.md) for authenticated LAN
access, mobile copies, transcripts and review notes. Never put voice references,
models, consent records or credentials in the listening library.

## Read or export the function guides

The [guide workflow](FUNCTION_GUIDES.md) creates Markdown, PDF and offline HTML
from the same canonical function resources. A portable collection includes all
function guides, a complete handbook, cue and relationship references, and tag
search. It contains documentation, not listening audio. Generate a new collection
for an updated edition rather than overwriting an older snapshot.

Tags and companion relationships already live in each function's dedicated
locale YAML. Reviewed relationships and draft suggestions are shown separately;
none is a required listening order. See [the authority map](PER_LOCALE_FUNCTION_AUTHORITY.md)
when contributing metadata. Use [the documentation map](README.md) for advanced
workflows and development.

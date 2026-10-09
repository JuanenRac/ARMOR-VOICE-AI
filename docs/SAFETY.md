# Voice safety

Speech recognition is **untrusted input**. This service never forwards spoken
text as a shell command or a device command; it turns a transcript into one of
fifteen known intents or refuses it.

## What is understood

Transcripts are normalised (Unicode NFKC, lower case, no accents, punctuation or
polite filler such as "please" or "por favor") and must then equal a known phrase
in English, Spanish, German, French, Italian, Japanese or Chinese. Anything else, anything over 200 characters and any phrase
that could mean two intents is *not understood*.

| Intent | Meaning | Confirmation |
|---|---|---|
| `status` | Ask for the system state | no |
| `silence` | Silence the alarm | no |
| `arm` | Arm the perimeter | **yes** |
| `disarm` | Disarm the perimeter | **yes** |

## The confirmation turn

Arming and disarming need an explicit second turn, and the confirmation is
something the **service** issues, not something the caller states:

1. The first turn returns no acceptance and a `confirmation_token`.
2. The second turn must echo that token for the same intent within 30 seconds.
3. The token is signed (HMAC-SHA-256) with a secret the caller does not have, so it
   cannot be forged, altered or moved to another intent; it works once (a replay is
   refused) and it dies with the process unless `ARMOR_VOICE_CONFIRM_SECRET` is set.

A request that carries the old `confirmed: true` flag is refused. A later
deployment may add authenticated speaker or physical confirmation, but must not
remove this confirmation without a documented risk review.

## What is recorded

With `--audit-file`, one line per decision: time, intent, outcome and the SHA-256
of the transcript. **Never audio and never the raw text**, so the log shows what
was decided without keeping what was said.

## What this service does not do

It does not arm, disarm or silence anything: an accepted decision is a
recommendation to ARMOR-SERVER, which still authenticates and authorises the
action. Speech recognition and synthesis engines are deployment choices and are
not part of this repository yet.

## Two kinds of command

The closed list has fifteen commands (`phrases.py`), of two kinds. The ones that **ask** - the state, the alarms, the nodes, the cameras, the radars, the solar system, the
consumption, the network, the time, the help - change nothing and need no confirmation. The ones that **do** are *arm* and *disarm* (they change the security state, so they are
confirmed in a second turn with a signed, single-use token), *silence* (acknowledges the alarms) and the *lights* (on and off). The gateway only decides which command a phrase
is: the server carries each out with the session of the person who spoke, writes it in the audit trail and says what it did in their language. A phrase that is not exactly one
of them, or that could be two, is not understood.

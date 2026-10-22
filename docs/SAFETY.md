# Voice safety

Speech recognition is **untrusted input**. This service never forwards spoken
text as a shell command or a device command; it turns a transcript into one of
fifteen known intents or refuses it.

## What is understood

Transcripts are normalised (Unicode NFKC, lower case, no accents, punctuation or
polite filler such as "please" or "por favor") and must then equal a known phrase
in English, Spanish, German, French, Italian, Portuguese, Japanese or Chinese. Anything else, anything over 200 characters and any phrase
that could mean two intents is *not understood*.

| Intent | Kind | Meaning | Confirmation |
|---|---|---|---|
| `status` | asks | Ask for the system state | no |
| `alarms` | asks | Ask for the alarms that are active | no |
| `nodes` | asks | Ask for the state of the nodes | no |
| `cameras` | asks | Ask for the state of the cameras | no |
| `radar` | asks | Ask for the state of the radars | no |
| `solar` | asks | Ask for the state of the solar system | no |
| `electrical` | asks | Ask for the electrical consumption | no |
| `network` | asks | Ask for the state of the network | no |
| `time` | asks | Ask for the time | no |
| `help` | asks | Ask what can be said | no |
| `silence` | does | Silence (acknowledge) the alarms | no |
| `lights_on` | does | Turn the lights on | no |
| `lights_off` | does | Turn the lights off | no |
| `arm` | does | Arm the perimeter | **yes** |
| `disarm` | does | Disarm the perimeter | **yes** |

The ten that *ask* change nothing. The five that *do* are carried out by ARMOR-SERVER with the session of the person who spoke, not by this service.

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

## The wall-panel turn (`POST /v1/turn`)

The wall panel sends the audio of one turn; the service turns it into text with the configured speech engine and hands the text to the same gate as any other transcript. The safety
rules of that route are:

* **Nothing is trusted from the audio.** The text that comes out of the speech engine is *untrusted input*: it is normalised and must equal one of the known phrases, exactly as above.
  The engines are programs run without a shell, with a short environment, reading the audio from the standard input.
* **Bounded by size and time.** At most 480 000 bytes of 16 kHz 16-bit mono audio (411/413 otherwise, 415 for another type), a language the service knows (422), at most two turns at
  once (503). If the speech engine takes so long that the server was not asked in time, the answer is 504 and **nothing is executed**: past nine seconds no command is carried out, and the
  panel gives up after twelve.
* **Confirmation is spoken, and only for arming.** The panel has no keyboard, so the service remembers the question it asked this client for half a minute and takes the next turn that
  says *yes* (in the language of the panel) as the confirmation and the next that says *no* as a refusal. Disarming is never done from here: it needs the PIN of a person, and a PIN
  is not said aloud.
* **Nothing is kept.** The audio is not stored, and the audit line carries the SHA-256 of the text, never the text.
* **Not on the network in clear.** The service listens on the loopback only: either a proxy of the server forwards the turn, or `--allow-remote` is used behind TLS. The token and the audio
  must not cross the network in clear.
* **No identity of the speaker yet.** The turn does not say which panel or which person spoke; the server decides with the token it was given. Adding the panel (and, where it exists,
  the person) to the request is a change of the contract between ARMOR-SERVER and the panel and is not done.

## Silencing by voice

"Silence" is accepted at once unless the installation asks for more: ARMOR-SERVER can send a policy that requires a spoken PIN or a second confirming turn (see `SILENCE_POLICY.md`). The PIN is never logged, kept or
echoed back, wrong guesses are limited, and a policy that is present but unreadable counts as the second turn.

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

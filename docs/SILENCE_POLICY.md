# Silencing the alarms by voice

Saying "silence" acknowledges the active alarms. By default this service passes it on at once (`off`). The installation can ask for more, and the choice belongs to ARMOR-SERVER:
this service only applies the mode it is told.

## The contract

ARMOR-SERVER holds the setting `voice.silence_confirmation` with the values `off` (the default), `pin` and `double_turn`, and sends it on every request it makes to this service as

```json
{"policy": {"silence_confirmation": "off"}}
```

* `POST /v1/command`: a `policy` field of the JSON body (and, for `pin`, a `pin` field with the digits).
* `POST /v1/turn`: the audio is the body, so the policy goes in the header `X-Armor-Policy`, a JSON object of at most 256 bytes.

Rules the sender can rely on:

| What arrives | What is applied |
|---|---|
| no `policy` / no header | `off`: exactly the behaviour of earlier versions |
| `off` | "silence" is passed on at once |
| `double_turn` | the first "silence" is not carried out and the panel is asked to say yes; a yes within 15 seconds (same panel) passes the original command on, a no or anything else drops it |
| `pin` | the first "silence" is not carried out and the panel is asked for the PIN; the right PIN within 20 seconds passes the command on |
| a policy that is present but not an object, not JSON, too long, or with an unknown value | `double_turn` (a broken setting never switches a protection off) |

Only "silence" is affected; every other command behaves as before, and arming and disarming keep their own rules.

## The PIN

* It is set in the environment of this service, `ARMOR_VOICE_SILENCE_PIN` (4 to 12 digits), next to the other secrets of the installation. A value that is not valid stops the service at start-up without printing it.
* It is spoken as digits or as digit words (eight languages, Chinese and Japanese numerals included); words that are not digits are ignored ("my PIN is one two three four").
* It is compared in constant time, **never written to a log or to the audit file, never kept, and never echoed back**: the `heard` field of a PIN turn is empty.
* Three wrong PINs lock silencing by voice for **every** panel for five minutes (a client name is chosen by the caller, so a count per name could be walked around). While locked, even the right PIN is refused. A right PIN clears the count.
* With `pin` asked for and no PIN set up, nothing is silenced by voice (it fails closed) and the panel is told to use the screen.

## What ARMOR-SERVER has to do

* Add the setting `voice.silence_confirmation` (`off` by default) and send `policy` on each request to this service: `X-Armor-Policy` on `/v1/turn`, `policy` (and `pin`) on `/v1/command`.
* Where the server decides on its own what a spoken "silence" is worth (`/api/v1/voice/command`), it should apply the same mode, so that the two routes cannot disagree; this service
  cannot see a request that reaches the server without passing through it.
* If the wall panel (ARMOR-HMI) calls `/v1/turn` directly, the header has to be added by whatever sits between it and this service (the server's proxy), not by the panel.

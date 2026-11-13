# Training the wake word models

The wake word of the wall panel ([SERVICE.md](SERVICE.md)) is detected by [openWakeWord](https://github.com/dscripka/openWakeWord) on the machine that runs the voice service. The model for each language is a small file that a person trains once and that then travels as an asset of a release of this project. Nothing in this repository trains a model, downloads one or switches the wake word on: the feature stays off unless `ARMOR_WAKE_WORD=on`, and a language without its model answers `wake_model_missing`.

The service starts with the generic model of openWakeWord by default (see [SERVICE.md](SERVICE.md), "The generic wake word"); training the family's own models is a later improvement, published in the releases of this project, and this page is its routine.

This page is the whole routine: what to train, the file the service expects, how to check it and how to add it to a signed release.

## What to train

One model per language, named exactly as `wake_words.json` names it (the example of the eight languages is `docs/wake_words.example.json`):

| Language | Phrase | File |
|---|---|---|
| en | hey armor | `hey_armor_en.onnx` |
| es | oye armor | `oye_armor_es.onnx` |
| de | hey armor | `hey_armor_de.onnx` |
| fr | dis armor | `dis_armor_fr.onnx` |
| it | ehi armor | `ehi_armor_it.onnx` |
| ja | ねえ アーマー | `nee_armor_ja.onnx` |
| zh | 你好 armor | `nihao_armor_zh.onnx` |
| pt | olá armor | `ola_armor_pt.onnx` |

English and Spanish come first. A language whose model is not trained simply has no wake word; nothing falls back to another language.

## Training

openWakeWord trains a model from synthetic speech, so no recording of a person is needed (and none is kept or sent anywhere). Follow the training notebook or the `train.py` script of the openWakeWord project, whose options change between its versions, with these choices:

1. Work in a clean Python environment on a machine with a GPU or a lot of patience; training is not done on the voice service machine or on the wall panel.
2. One configuration file per language. Set `target_phrase` to the phrase of the table (the spelling that a speech synthesiser of that language reads naturally; for Japanese and Chinese write the phrase in the script of the language), `model_name` to the file name without `.onnx`, and the output folder to a folder of your own.
3. Use a voice for the synthetic clips that matches the language (the Piper voices of that language, several speakers). Train with background noise and room impulse responses, and with the false positive validation set that the project documents, so that the model does not wake on speech in general.
4. Aim for few false activations first and a good recall second: a panel that wakes by itself is worse than one that needs the word said twice. The service already asks for two 80 ms frames in a row over the threshold and then stays quiet for two seconds.
5. Export the model as ONNX. The file the service loads is the classifier that openWakeWord writes, whose input is the window of embeddings (`[batch, 16, 96]`) and whose output is one score (`[batch, 1]`). A TFLite file is not used.
6. Try it before releasing it, with the real service and a microphone: `ARMOR_WAKE_WORD=on ARMOR_WAKE_MODELS=<folder> ARMOR_WAKE_CONFIG=<wake_words.json>`, say the phrase and some other sentences, and tune `threshold` in `wake_words.json` (0.3 to 0.99, 0.6 to start). The threshold is a setting, not part of the model.

## The format the service expects

| Property | Required |
|---|---|
| File name | the one `wake_words.json` names for the language: lower case letters, digits and `_`, ending in `.onnx` |
| Size | from 8 KiB to 8 MiB |
| Format | ONNX; one graph input of shape `[batch, 16, 96]` and one output of shape `[batch, 1]`, the batch being 1 or left open |
| Weights | inside the file (no external data file) |
| Names | one model file per language; two languages never share a file |

## Checking a model

The check reads the file with the standard library only (it runs nothing and needs neither openWakeWord nor onnx):

```
python -m armor_voice_ai.wake_model_check MODEL.onnx --language es --words wake_words.json
python -m armor_voice_ai.wake_model_check --folder MODELS_DIR --words wake_words.json --allow-missing
```

It prints, for each language, `ok` with the size and the SHA-256 or `BAD` with each problem, and exits with 1 when anything is wrong (a name that `wake_words.json` does not give for the language, a size out of range, a shape that is not the one above, a weight kept in another file, a hash that is not the expected one with `--sha256`). Without `--allow-missing` a language of the words file with no model in the folder is a problem too. The same check runs in the tests of this repository on models built in memory.

## Adding the models to the signed release

The models are assets of the release of this project, next to the signed package of the service. The helper builds them:

```
python -m armor_voice_ai.wake_release --models MODELS_DIR --version <the release version> --out OUT_DIR --words wake_words.json --sign
```

It checks every model first and writes nothing if one is wrong. In `OUT_DIR` it leaves the models, `armor-voice-wake-models-<version>.manifest` (one line per model: language, file, bytes, SHA-256) and, with `--sign`, `armor-voice-wake-models-<version>.manifest.sig2`: the signature of the manifest hash made by the signer of the releases (`~/.armor/sign.mjs`, or `--signer`), which holds the key itself; the helper never reads a key. Whoever downloads a model checks its hash against the manifest and the manifest against the public key of the releases.

Then, once the release of that version exists, add the files to it:

```
gh release upload v<version> OUT_DIR/* -R JuanenRac/ARMOR-VOICE-AI
```

and check the release page lists the models, the manifest and the signature. The models are not part of the package of the service (`armor-voice-<version>.tgz`), so adding them does not change its hash or its signature, and a release without models is still a complete release: the wake word just has nothing to load.

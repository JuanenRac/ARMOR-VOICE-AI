"""The phrases of the closed allow-list, per command and per language.

Copyright (C) 2026 JuanenRac (Electro Hobby 3D). GPL-3.0-or-later.

Written the way a person says them (accents, apostrophes, kana with their marks): intent.py normalises every one when it loads, with the same function that normalises what
is heard, so they cannot drift apart. A phrase may belong to one command only (a test checks it). The commands are of two kinds: the ones that *ask* (the state, the alarms,
the nodes...) change nothing and need no confirmation, and the ones that *do* - arm and disarm, which change the security state and are confirmed in a second turn, silence
and the lights, which the server carries out with the session of the person who asked.
"""

from __future__ import annotations

LANGUAGES = ("en", "es", "de", "fr", "it", "ja", "zh")

#: command -> language -> phrases
PHRASES: dict[str, dict[str, tuple[str, ...]]] = {
    "arm": {
        "en": ("arm", "arm system", "arm the system"),
        "es": ("armar", "armar sistema", "armar el sistema", "arma el sistema", "activar alarma", "activa la alarma"),
        "de": ("scharfschalten", "alarm scharfschalten", "system scharfschalten", "das system scharfschalten"),
        "fr": ("armer", "armer le système", "armer l'alarme", "activer l'alarme"),
        "it": ("armare", "armare il sistema", "attivare l'allarme", "attiva l'allarme"),
        "ja": ("警備開始", "警備を開始", "警備を開始して"),
        "zh": ("布防", "系统布防", "开启警戒"),
    },
    "disarm": {
        "en": ("disarm", "disarm system", "disarm the system"),
        "es": ("desarmar", "desarmar sistema", "desarmar el sistema", "desarma el sistema", "desactivar alarma", "desactiva la alarma"),
        "de": ("entschärfen", "alarm entschärfen", "system entschärfen", "das system entschärfen"),
        "fr": ("désarmer", "désarmer le système", "désarmer l'alarme", "désactiver l'alarme"),
        "it": ("disarmare", "disarmare il sistema", "disattivare l'allarme", "disattiva l'allarme"),
        "ja": ("警備解除", "警備を解除", "警備を解除して"),
        "zh": ("撤防", "系统撤防", "解除警戒"),
    },
    "status": {
        "en": ("status", "system status", "what is the status"),
        "es": ("estado", "estado del sistema", "cuál es el estado"),
        "de": ("status", "systemstatus", "wie ist der status"),
        "fr": ("statut", "état du système", "quel est l'état"),
        "it": ("stato", "stato del sistema", "qual è lo stato"),
        "ja": ("状態", "システムの状態"),
        "zh": ("状态", "系统状态"),
    },
    "silence": {
        "en": ("silence", "silence alarm", "silence the alarm"),
        "es": ("silenciar", "silenciar alarma", "silenciar la alarma", "silencia la alarma"),
        "de": ("stummschalten", "alarm stummschalten", "den alarm stummschalten"),
        "fr": ("silence alarme", "faire taire l'alarme"),
        "it": ("silenzio", "silenzia", "silenzia l'allarme", "silenzia allarme"),
        "ja": ("警報を止めて", "警報停止"),
        "zh": ("消音", "静音报警"),
    },
    "alarms": {
        "en": ("alarms", "active alarms", "are there any alarms", "how many alarms are there"),
        "es": ("alarmas", "alarmas activas", "hay alguna alarma", "cuántas alarmas hay"),
        "de": ("alarme", "aktive alarme", "gibt es alarme", "wie viele alarme gibt es"),
        "fr": ("alarmes", "alarmes actives", "y a-t-il des alarmes", "combien d'alarmes y a-t-il"),
        "it": ("allarmi", "allarmi attivi", "ci sono allarmi", "quanti allarmi ci sono"),
        "ja": ("アラーム", "有効なアラーム", "アラームはありますか"),
        "zh": ("报警", "活动报警", "有报警吗", "有几个报警"),
    },
    "nodes": {
        "en": ("nodes", "node status", "how many nodes are online", "are the nodes online"),
        "es": ("nodos", "estado de los nodos", "cuántos nodos hay conectados", "están los nodos conectados"),
        "de": ("knoten", "knotenstatus", "wie viele knoten sind online", "sind die knoten online"),
        "fr": ("nœuds", "noeuds", "état des nœuds", "combien de nœuds sont en ligne", "les nœuds sont-ils en ligne"),
        "it": ("nodi", "stato dei nodi", "quanti nodi sono online", "i nodi sono online"),
        "ja": ("ノード", "ノードの状態", "オンラインのノードは何台ですか"),
        "zh": ("节点", "节点状态", "有几个节点在线"),
    },
    "cameras": {
        "en": ("cameras", "camera status", "are the cameras online", "are the cameras working"),
        "es": ("cámaras", "estado de las cámaras", "están las cámaras conectadas", "funcionan las cámaras"),
        "de": ("kameras", "kamerastatus", "sind die kameras online", "funktionieren die kameras"),
        "fr": ("caméras", "état des caméras", "les caméras sont-elles en ligne", "les caméras fonctionnent-elles"),
        "it": ("telecamere", "stato delle telecamere", "le telecamere sono online", "le telecamere funzionano"),
        "ja": ("カメラ", "カメラの状態", "カメラは動いていますか"),
        "zh": ("摄像头", "摄像头状态", "摄像头正常吗"),
    },
    "radar": {
        "en": ("radar", "is anyone there", "is there anyone outside", "people detected"),
        "es": ("radar", "hay alguien", "hay alguien fuera", "personas detectadas"),
        "de": ("radar", "ist jemand da", "ist jemand draußen", "erkannte personen"),
        "fr": ("radar", "y a-t-il quelqu'un", "y a-t-il quelqu'un dehors", "personnes détectées"),
        "it": ("radar", "c'è qualcuno", "c'è qualcuno fuori", "persone rilevate"),
        "ja": ("レーダー", "誰かいますか", "検知された人"),
        "zh": ("雷达", "有人吗", "检测到的人"),
    },
    "solar": {
        "en": ("solar", "solar status", "battery status", "how is the battery"),
        "es": ("solar", "estado solar", "estado de la batería", "cómo está la batería"),
        "de": ("solar", "solarstatus", "batteriestatus", "wie ist die batterie"),
        "fr": ("solaire", "état solaire", "état de la batterie", "comment va la batterie"),
        "it": ("solare", "stato solare", "stato della batteria", "come sta la batteria"),
        "ja": ("ソーラー", "ソーラーの状態", "バッテリーの状態"),
        "zh": ("太阳能", "太阳能状态", "电池状态"),
    },
    "electrical": {
        "en": ("power", "power consumption", "electrical status", "how much power am i using"),
        "es": ("consumo", "consumo eléctrico", "estado eléctrico", "cuánta electricidad estoy usando"),
        "de": ("stromverbrauch", "elektrik", "elektrischer status", "wie viel strom verbrauche ich"),
        "fr": ("consommation", "consommation électrique", "état électrique", "combien d'électricité j'utilise"),
        "it": ("consumo", "consumo elettrico", "stato elettrico", "quanta elettricità sto usando"),
        "ja": ("電力", "電力消費", "電気の状態"),
        "zh": ("用电", "用电量", "电气状态"),
    },
    "network": {
        "en": ("network", "network status", "is the internet working", "do i have internet"),
        "es": ("red", "estado de la red", "funciona internet", "tengo internet"),
        "de": ("netzwerk", "netzwerkstatus", "funktioniert das internet", "habe ich internet"),
        "fr": ("réseau", "état du réseau", "internet fonctionne-t-il", "ai-je internet"),
        "it": ("rete", "stato della rete", "internet funziona", "ho internet"),
        "ja": ("ネットワーク", "ネットワークの状態", "インターネットは使えますか"),
        "zh": ("网络", "网络状态", "网络正常吗"),
    },
    "time": {
        "en": ("time", "what time is it", "what is the time"),
        "es": ("hora", "qué hora es", "dime la hora"),
        "de": ("uhrzeit", "wie spät ist es", "wie viel uhr ist es"),
        "fr": ("heure", "quelle heure est-il", "il est quelle heure"),
        "it": ("ora", "che ora è", "che ore sono"),
        "ja": ("時間", "今何時ですか"),
        "zh": ("时间", "现在几点"),
    },
    "help": {
        "en": ("help", "what can you do", "what can i say", "commands"),
        "es": ("ayuda", "qué puedes hacer", "qué puedo decir", "comandos"),
        "de": ("hilfe", "was kannst du", "was kann ich sagen", "befehle"),
        "fr": ("aide", "que peux-tu faire", "que puis-je dire", "commandes"),
        "it": ("aiuto", "cosa puoi fare", "cosa posso dire", "comandi"),
        "ja": ("ヘルプ", "何ができますか", "何と言えばいいですか"),
        "zh": ("帮助", "你能做什么", "我能说什么"),
    },
    "lights_on": {
        "en": ("lights on", "turn on the lights", "switch on the lights"),
        "es": ("luces encendidas", "enciende las luces", "encender las luces"),
        "de": ("licht an", "schalte das licht ein", "lichter einschalten"),
        "fr": ("lumières allumées", "allume les lumières", "allumer les lumières"),
        "it": ("luci accese", "accendi le luci", "accendere le luci"),
        "ja": ("電気をつけて", "ライトをつけて"),
        "zh": ("开灯", "打开灯"),
    },
    "lights_off": {
        "en": ("lights off", "turn off the lights", "switch off the lights"),
        "es": ("luces apagadas", "apaga las luces", "apagar las luces"),
        "de": ("licht aus", "schalte das licht aus", "lichter ausschalten"),
        "fr": ("lumières éteintes", "éteins les lumières", "éteindre les lumières"),
        "it": ("luci spente", "spegni le luci", "spegnere le luci"),
        "ja": ("電気を消して", "ライトを消して"),
        "zh": ("关灯", "关闭灯"),
    },
}

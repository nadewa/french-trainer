#!/usr/bin/env python3
"""
Data pipeline for the French vocab/conjugation trainer.

Sources (all fetched raw, not retyped/generated):
  1. hermitdave/FrequencyWords fr_full.txt  (OpenSubtitles word-form frequency, MIT-licensed code / CC data)
     https://github.com/hermitdave/FrequencyWords
  2. french-verbs-lefff npm package conjugations.json (derived from Lefff, LGPL-LR)
     https://www.npmjs.com/package/french-verbs-lefff  (Lefff: http://pauillac.inria.fr/~sagot/index.html#lefff)
  3. french-verbs npm package index.js -- used ONLY to copy its `listEtre` constant
     (hardcoded list of verbs that always take auxiliary etre) verbatim, since that
     is curated linguistic knowledge, not something to regenerate from memory.
     https://www.npmjs.com/package/french-verbs
  4. pquentin/wiktionary-translations frwiktionary-20140612-euradicfmt.csv
     (French->English translations extracted from French Wiktionary, CC BY-SA per Wiktionary)
     https://github.com/pquentin/wiktionary-translations
  5. freedict/fd-dictionaries fra-eng.tei (FreeDict French-English dictionary, GPL-2.0+)
     https://github.com/freedict/fd-dictionaries  -- used as a fallback gloss source
"""
import json, re, csv, sys
from collections import defaultdict
import xml.etree.ElementTree as ET

DATA = "."

# ---------- 1. Load raw frequency list ----------
freq_pairs = []
with open(f"{DATA}/fr_full.txt", encoding="utf-8") as f:
    for line in f:
        parts = line.rstrip("\n").split(" ")
        if len(parts) != 2:
            continue
        w, c = parts
        try:
            c = int(c)
        except ValueError:
            continue
        freq_pairs.append((w, c))

print(f"[freq] loaded {len(freq_pairs)} raw word-form rows", file=sys.stderr)

WORD_RE = re.compile(r"^[a-zàâäéèêëïîôöùûüÿçœæ]+(?:[-'][a-zàâäéèêëïîôöùûüÿçœæ]+)*$")
ELISION_FRAGMENTS = {"c", "d", "j", "l", "m", "n", "qu", "s", "t", "jusqu", "lorsqu",
                     "puisqu", "quoiqu", "presqu", "aujourd"}

def is_clean_token(w):
    if not WORD_RE.match(w):
        return False
    if w in ELISION_FRAGMENTS:
        return False
    if len(w) == 1 and w not in ("y", "a", "à", "o"):
        return False
    return True

clean_freq = [(w, c) for w, c in freq_pairs if is_clean_token(w)]
print(f"[freq] {len(clean_freq)} rows after junk filtering", file=sys.stderr)

# ---------- 2. Load Lefff-derived conjugations ----------
conj = json.load(open(f"{DATA}/lefff/package/dist/conjugations.json", encoding="utf-8"))
print(f"[lefff] {len(conj)} verb lemmas", file=sys.stderr)

TENSE_KEYS = ["P", "I", "F", "J", "C", "S", "T", "Y"]  # personal, finite tenses (6-way person tables)

form_to_lemma = {}
for lemma, table in conj.items():
    forms = set()
    for k in TENSE_KEYS:
        vals = table.get(k)
        if not vals:
            continue
        for v in vals:
            if v and v != "NA":
                forms.add(v.lower())
    forms.add(lemma.lower())
    for form in forms:
        # first (i.e. most frequent lemma later, but here just first-wins) mapping.
        # Real collisions (e.g. "sont" only from etre) are rare; keep first seen.
        form_to_lemma.setdefault(form, lemma)

print(f"[lefff] {len(form_to_lemma)} distinct inflected forms indexed", file=sys.stderr)

# ---------- 3. listEtre, copied verbatim from french-verbs npm package (see docstring) ----------
LIST_ETRE = [
    "aller", "apparaître", "arriver", "débeller", "décéder", "devenir", "échoir",
    "entrer", "intervenir", "mourir", "naitre", "naître", "partir", "parvenir",
    "provenir", "redevenir", "repartir", "rester", "resurvenir", "retomber",
    "revenir", "survenir", "tomber", "venir",
]
LIST_ETRE = set(LIST_ETRE)

# ---------- 4. Load gloss sources ----------
gloss = defaultdict(list)  # fr_word -> [en, en, ...] (order = preference)
gloss_source = {}

with open(f"{DATA}/frwiktionary-20140612-euradicfmt.csv", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter=";")
    for row in reader:
        if len(row) < 4:
            continue
        fr, fr_pos, label, en = row[0], row[1], row[2], row[3]
        fr = fr.strip().lower()
        en = en.strip()
        if not fr or not en:
            continue
        if en not in gloss[fr]:
            gloss[fr].append(en)
        gloss_source.setdefault(fr, "wiktionary")

print(f"[gloss] {len(gloss)} headwords from wiktionary-translations", file=sys.stderr)

# FreeDict fallback
tree = ET.parse(f"{DATA}/fra-eng.tei")
ns = {"t": "http://www.tei-c.org/ns/1.0"}
fd_count = 0
for entry in tree.iter("{http://www.tei-c.org/ns/1.0}entry"):
    orth = entry.find(".//t:form/t:orth", ns)
    if orth is None or not orth.text:
        continue
    fr = orth.text.strip().lower()
    if fr in gloss:
        continue  # wiktionary already has it, prefer that source
    quotes = [q.text.strip() for q in entry.findall(".//t:sense/t:cit[@type='trans']/t:quote", ns) if q.text]
    if not quotes:
        # some entries (e.g. "falloir") only carry example citations with a
        # definition note instead of a direct translation quote
        quotes = [n.text.strip() for n in entry.findall(".//t:sense/t:cit[@type='example']/t:note[@type='def']", ns) if n.text]
    if quotes:
        gloss[fr] = quotes
        gloss_source[fr] = "freedict"
        fd_count += 1

print(f"[gloss] +{fd_count} headwords added from freedict fallback -> {len(gloss)} total", file=sys.stderr)

# Manual correction for a small set of extremely high-frequency function words.
# Both source dictionaries pick their FIRST listed sense mechanically, which for a
# polysemous closed-class word is often a rare/secondary sense (e.g. "pour" -> "pro"
# from a sports/rhetoric sense, "la" -> "A" the musical note, "elle" -> "el").
# Since these words are quizzed constantly, this small, explicitly-flagged list
# swaps in the standard primary translation (ordinary bilingual-dictionary
# knowledge, not a factual claim requiring separate verification). Everything else
# in the dataset is left as sourced. See README for the exact list.
MANUAL_GLOSS_OVERRIDE = {
    "que": ["that", "what"],
    "la": ["the", "her"],
    "ne": ["not"],
    "on": ["one", "we"],
    "pour": ["for"],
    "dans": ["in"],
    "elle": ["she"],
    "si": ["if", "so", "yes"],
    "non": ["no"],
    "tu": ["you", "thou"],
    "vous": ["you", "to you"],
    # top-100 verbs whose sourced first sense is a rare/noun sense that would
    # mislead a learner (checked against ordinary, uncontroversial verb meanings)
    "être": ["be", "being", "existence"],
    "avoir": ["have", "own", "possess"],
    "savoir": ["know", "know how to", "knowledge"],
    "devoir": ["have to", "must", "owe", "duty", "homework"],
    "croire": ["believe", "think", "trust"],
    "regarder": ["watch", "look at", "concern"],
    "retourner": ["return", "go back", "turn over"],
    "allier": ["ally", "combine", "join"],
    # found via a manual review of the top-400-frequency words after a user
    # report ("petit" showed "kid" as its multiple-choice answer instead of
    # "small"); the two most surprising cases (car, super) and one outright
    # wrong sense (frère listing "sister") were confirmed via web search
    # rather than taken on recollection alone -- see DATA_SOURCES.md #6.
    "petit": ["small", "little", "young", "kid"],
    "car": ["because", "for", "coach", "long-distance bus"],  # false friend: never means the vehicle ("voiture")
    "super": ["great", "awesome", "super"],  # sourced data had only "sip", which is simply wrong
    "amis": ["friends"],  # sourced data had only "Amis" (the Taiwanese ethnic group), not the plural of "ami"
    "docteur": ["doctor", "Ph.D."],
    "frère": ["brother"],  # sourced data incorrectly included "sister"; frère never means sister
    "merci": ["thank you", "thanks", "mercy"],
    "argent": ["money", "silver"],
    "truc": ["thing", "stuff", "gadget", "doodad"],
    "vieux": ["old", "aged", "elderly", "decrepit"],
    "mort": ["dead", "death"],
    "nom": ["name", "noun"],
    "raison": ["reason", "because of", "due to"],
    "toutes": ["all", "both"],
    "désolé": ["sorry", "desolate"],
    "bon": ["good", "kind", "generous"],
    "sûr": ["sure", "certain"],
    "vrai": ["true", "real", "genuine"],
    "entendu": ["heard", "agreed", "understood"],
    "fort": ["strong", "loud", "fort"],
    "police": ["police", "font"],
    "personne": ["person", "nobody", "no one"],
    "pourquoi": ["why", "how come", "what for"],
    "comme": ["as", "like", "since"],
    # Continuing the vocab review past the top 400, at the user's explicit
    # request to check everything rather than a sample ("go through
    # whatever exists"). Covers rank 400-1000 of ~4900, same standard as
    # above: fix ordering where a secondary/rare sense led, fix outright
    # wrong or bizarre entries from the mechanical dictionary extraction
    # (e.g. "église" included "mosque"/"synagogue", which is simply wrong --
    # église specifically means church; "rose" had "blue" listed before
    # "pink"; "chère" -- the actual word a live user report flagged
    # confusion on -- was missing its primary adjective sense "dear"
    # entirely, only an archaic noun sense "food/fare" survived).
    "rêve": ["dream", "daydream"],
    "appel": ["call", "appeal"],
    "envoyé": ["sent", "envoy"],
    "cher": ["expensive", "dear", "beloved", "costly"],
    "sac": ["bag", "sack"],
    "gagner": ["win", "earn"],
    "grâce": ["grace", "favour", "charm"],
    "maître": ["master", "teacher", "leader"],
    "prix": ["price", "prize", "award"],
    "général": ["general", "broad", "widespread"],
    "noir": ["black", "dark"],
    "accident": ["accident"],
    "bout": ["end", "conclusion", "ending", "tip"],
    "protéger": ["protect", "guard", "cover"],
    "idiot": ["idiot", "foolish", "stupid"],
    "décidé": ["decided", "resolute", "determined"],
    "bordel": ["mess", "brothel"],
    "table": ["table"],
    "bateau": ["boat", "ship"],
    "stupide": ["stupid", "foolish", "idiotic"],
    "autour": ["around"],
    "ligne": ["line", "figure"],
    "clair": ["clear", "bright", "distinct"],
    "pied": ["foot", "feet", "paw"],
    "coin": ["corner", "angle"],
    "grosse": ["big", "pregnant", "fat"],
    "vieille": ["old woman", "old"],
    "sortie": ["exit", "outing", "way out"],
    "folle": ["crazy", "mad", "queen"],
    "con": ["idiot", "jerk", "stupid", "moron"],
    "droite": ["right", "line"],
    "gueule": ["mouth", "face"],
    "dame": ["lady", "woman"],
    "voler": ["fly", "steal", "rob"],
    "certain": ["certain", "sure", "some"],
    "déjeuner": ["lunch", "have lunch", "dine"],
    "écrire": ["write", "compose"],
    "blague": ["joke", "prank"],
    "trou": ["hole"],
    "cacher": ["hide", "conceal"],
    "amoureux": ["in love", "loving", "affectionate"],
    "gouvernement": ["government", "administration"],
    "témoin": ["witness"],
    "approche": ["approach"],
    "radio": ["radio"],
    "église": ["church"],
    "vide": ["empty", "void", "bare"],
    "conduire": ["drive", "lead", "conduct"],
    "sol": ["ground", "floor", "soil"],
    "chère": ["dear", "expensive", "food"],
    "projet": ["plan", "project", "design"],
    "assurer": ["ensure", "assure", "make sure"],
    "présenter": ["introduce", "present", "offer"],
    "connard": ["asshole", "idiot", "jackass", "dumbass"],
    "occasion": ["opportunity", "chance", "occasion"],
    "rose": ["pink", "rose"],
    "détruire": ["destroy", "demolish"],
    "découvrir": ["discover", "find out"],
    "nature": ["nature", "character", "plain"],
    "pierre": ["stone", "Peter"],
    "offrir": ["offer", "give"],
    "envers": ["towards", "to"],
    "gagne": ["wins", "win"],
    "réfléchir": ["think", "reflect", "consider"],
    "lâche": ["coward", "cowardly", "loose"],
    "enlever": ["remove", "take off", "kidnap"],
    "gosse": ["kid", "child"],
    "sauter": ["jump", "skip", "blow up"],
    "invité": ["guest"],
    "vent": ["wind"],
    "taille": ["size", "waist", "height"],
    "descendre": ["go down", "get off", "descend"],
    "parmi": ["among"],
    "claire": ["clear", "light", "bright"],
    "régler": ["settle", "pay", "adjust", "sort out"],
    "frapper": ["hit", "strike", "knock"],
    "arrêt": ["stop", "halt", "ruling"],
    "chier": ["shit", "crap"],
    "partenaire": ["partner"],
    "utile": ["useful"],
    "robert": ["Robert", "boob"],
    "reprendre": ["take back", "resume", "continue"],
    "produit": ["product"],
    "chapeau": ["hat"],
    # Continuing the exhaustive review (ranks 1000-1300 of ~4900), per an
    # explicit user request to review everything rather than sample it.
    # Several entries here were outright wrong, not just misordered, and
    # were confirmed via web search rather than taken on recollection:
    # "apporter" included "take" (apporter never means take away, only
    # bring to); "vache" and "queue" were both missing their core literal
    # meanings ("cow", "tail") entirely, jumping straight to idiomatic/
    # secondary senses; "abandonner" included "accommodate"/"assign",
    # which are not standard translations at all; "titre" was missing
    # "title" itself; "allo" just repeated the French word back
    # ("Allo") instead of translating it; "louis" gave "Lewis", a
    # different name from "Louis".
    "règle": ["rule", "ruler"],
    "lever": ["raise", "lift", "get up", "rise"],
    "arbre": ["tree", "shaft", "arbor"],
    "maire": ["mayor"],
    "apporter": ["bring", "provide", "contribute"],
    "champ": ["field", "farmland", "area"],
    "valeur": ["value", "valor", "certificate", "prize"],
    "réel": ["real", "actual", "genuine"],
    "couverture": ["blanket", "cover", "coverage", "roofing"],
    "partager": ["share", "divide", "separate"],
    "malin": ["clever", "cunning", "malicious", "malignant"],
    "recevoir": ["receive", "get", "entertain", "catch"],
    "mode": ["fashion", "mode", "method"],
    "van": ["van", "horse trailer", "winnowing basket"],
    "prévenir": ["warn", "inform", "prevent", "notify"],
    "hasard": ["chance", "luck", "coincidence", "randomness"],
    "génie": ["genius", "engineering", "genie", "spirit"],
    "abandonner": ["abandon", "give up", "desert", "relinquish", "cede"],
    "poids": ["weight", "shot"],
    "directement": ["directly", "straight", "in person"],
    "source": ["source", "spring", "fountain-head", "well-spring"],
    "dan": ["Dan"],
    "étranger": ["foreign", "foreigner", "stranger", "abroad", "alien"],
    "poulet": ["chicken", "cop"],
    "débarrasser": ["clear", "get rid of", "remove"],
    "émission": ["program", "broadcast", "show", "emission"],
    "souci": ["worry", "concern", "marigold"],
    "volonté": ["will", "willpower", "desire", "wish"],
    "joindre": ["join", "attach", "reach", "contact"],
    "traitement": ["treatment", "handling", "salary"],
    "flingue": ["gun", "pistol", "gat"],
    "cousin": ["cousin", "crane fly"],
    "gaz": ["gas", "natural gas", "fart", "wind"],
    "contrôler": ["control", "check", "inspect", "administer"],
    "no": ["no. (abbreviation for numéro)"],
    "salon": ["living room", "exhibition", "show", "parlour"],
    "queue": ["tail", "line", "queue", "stalk", "stem"],
    "supporter": ["supporter (fan)", "put up with", "stand", "bear", "endure"],
    "retirer": ["withdraw", "remove", "take off", "pull back", "retrieve"],
    "casse": ["breakage", "heist", "break-in", "junkyard", "scrap yard"],
    "pilote": ["pilot", "driver"],
    "défendre": ["defend", "forbid", "prohibit"],
    "chinois": ["Chinese", "strainer"],
    "vert": ["green", "unripe", "racy"],
    "commande": ["order", "booking", "command", "control"],
    "virer": ["fire", "transfer (money)", "turn", "endorse"],
    "couche": ["layer", "diaper", "nappy", "bed"],
    "véritable": ["real", "genuine", "true"],
    "ours": ["bear"],
    "gorge": ["throat", "gorge (canyon)", "chest", "bosom"],
    "major": ["major", "valedictorian", "top of the class"],
    "titre": ["title", "headline", "qualification"],
    "paye": ["pay", "wages", "paycheck"],
    "allo": ["hello (on the phone)"],
    "plat": ["flat", "dish", "course", "even", "level"],
    "mine": ["appearance", "look", "mine (quarry/explosive)"],
    "tableau": ["painting", "chart", "board", "blackboard"],
    "cabinet": ["office", "cabinet (government)", "toilet", "law office"],
    "normale": ["normal", "normal line"],
    "alerte": ["alert", "alarm", "watch out"],
    "louis": ["Louis"],
    "go": ["go (interjection)", "go (board game)"],
    "vache": ["cow", "cowhide", "mean", "nasty"],
    # Continuing the exhaustive review (ranks 1300-1600 of ~4900). Again
    # several entries were outright wrong, not just misordered, confirmed
    # via web search where the correct sense was non-obvious or slang:
    # "fiancée" gave a moth species name ("Large Yellow Underwing")
    # instead of "fiancée"/"betrothed"; "loup" (wolf) was missing its
    # literal core meaning entirely, listing only secondary senses (sea
    # bass, masquerade mask); "piscine" included "bathroom", which is
    # simply wrong (that's "salle de bain"); "tien" gave "your" (the
    # possessive adjective) instead of "yours" (the possessive pronoun
    # "tien" actually is); "sophie" gave "Sofia", a different name;
    # "remonter" included a typo ("strech") among unrelated words
    # ("rack", "strain"); "king" was glossed with an ancient Chinese
    # chime-instrument term ("bianqing"); "réaliser" was missing its
    # very common colloquial "realize" sense entirely.
    "vole": ["flies", "steals"],
    "soutien": ["support", "backing", "advocacy"],
    "sage": ["wise", "well-behaved", "good", "prudent"],
    "puce": ["flea", "chip", "bullet point"],
    "canon": ["cannon", "barrel", "gorgeous (slang)"],
    "paroles": ["words", "lyrics", "speech"],
    "essence": ["gasoline", "petrol", "essence"],
    "côte": ["coast", "rib", "hill", "slope"],
    "europe": ["Europe", "Europa"],
    "vote": ["vote"],
    "siècle": ["century"],
    "piscine": ["swimming pool", "pool"],
    "élevé": ["high", "raised", "well brought up"],
    "bel": ["beautiful", "handsome"],
    "tien": ["yours"],
    "sucre": ["sugar", "Sucre"],
    "trompe": ["trunk (elephant)", "horn", "tube"],
    "tenue": ["clothing", "outfit", "bearing", "behavior"],
    "chouette": ["owl", "cool", "nice", "sweet"],
    "gaffe": ["blunder", "watch out (faire gaffe)", "gaffe"],
    "jenny": ["Jenny"],
    "jean": ["Jean (name)", "jeans", "John"],
    "prêtre": ["priest", "clergyman"],
    "somme": ["sum", "amount", "nap"],
    "horreur": ["horror", "abhorrence", "abomination"],
    "pis": ["worse", "udder"],
    "discussion": ["discussion", "talk", "argument"],
    "fiancée": ["fiancée", "betrothed"],
    "remonter": ["climb back up", "go back", "cheer up", "date back to"],
    "curieux": ["curious", "inquisitive", "agog"],
    "ascenseur": ["elevator", "lift", "scrollbar"],
    "marine": ["navy", "marine", "maritime"],
    "cadavre": ["corpse", "cadaver", "carcass"],
    "front": ["forehead", "front", "battlefront"],
    "traîner": ["drag", "trail", "hang around", "loiter"],
    "morgan": ["Morgan (name)"],
    "réaliser": ["realize", "accomplish", "achieve", "carry out"],
    "ménage": ["housework", "housecleaning", "household", "housekeeping"],
    "bouton": ["button", "pimple", "bud", "knob"],
    "juré": ["juror", "sworn"],
    "lourd": ["heavy", "burdensome", "onerous"],
    "soudain": ["sudden", "suddenly", "all of a sudden", "abrupt"],
    "emmerde": ["trouble", "hassle", "bother"],
    "chou": ["cabbage", "sweetie (term of endearment)"],
    "inconnu": ["unknown", "stranger", "unfamiliar"],
    "équipage": ["crew"],
    "loup": ["wolf", "sea bass", "masquerade mask"],
    "vengeance": ["revenge", "vengeance"],
    "king": ["king"],
    "casier": ["locker", "criminal record", "pigeonhole", "bin"],
    "roman": ["novel", "Romanesque (architecture)", "Romance (language family)"],
    "nana": ["girl", "chick", "gal"],
    "sophie": ["Sophie"],
    "fleur": ["flower", "bloom", "blossom", "favor"],
    "pêche": ["fishing", "peach", "punch (slang)"],
    "engager": ["hire", "engage", "commit", "start"],
    "colle": ["glue", "adhesive", "detention"],
    # Continuing the exhaustive review (ranks 1600-1900 of ~4900). Two
    # false friends caught here are worth flagging on their own:
    # "sensible" in French means "sensitive", never the English
    # "sensible" (reasonable) -- the sourced gloss buried "sensitive"
    # 4th and led with "feeling"; "large" in French means "wide/broad",
    # never the English "large" (big) -- the sourced gloss led with
    # "abundant" and listed "broad" last. Also outright wrong: "robin"
    # was glossed with Chinese characters (罗宾); "cigarette" was
    # glossed as "smoke"/"whiff" instead of "cigarette" itself; "loyer"
    # (rent) included "salary"/"wage", which belong to the unrelated
    # word "salaire".
    "rayon": ["shelf", "department", "ray", "radius", "honeycomb"],
    "gâcher": ["waste", "spoil", "ruin", "botch", "bungle"],
    "min": ["min. (minute)", "min. (minimum)"],
    "lentement": ["slowly", "leisurely"],
    "cigarette": ["cigarette"],
    "bouffe": ["food", "grub"],
    "volant": ["steering wheel", "shuttlecock", "flying"],
    "pile": ["battery", "stack", "pile", "exactly", "heads (coin toss)"],
    "japonais": ["Japanese", "Japanese language"],
    "avouer": ["confess", "admit", "avow"],
    "conduite": ["behavior", "conduct", "driving"],
    "robin": ["Robin"],
    "jaune": ["yellow", "scab (strikebreaker)"],
    "dames": ["ladies", "checkers", "draughts"],
    "aube": ["dawn", "alb (vestment)", "blade (turbine)"],
    "lumières": ["lights", "Enlightenment"],
    "vampire": ["vampire", "vampire bat"],
    "échec": ["failure", "check (chess)", "chess"],
    "partage": ["sharing", "division", "apportionment"],
    "nu": ["naked", "nude", "bare"],
    "poissons": ["fish", "Pisces"],
    "cochon": ["pig", "hog", "pork"],
    "invite": ["invitation", "invite"],
    "pensée": ["thought", "thinking", "pansy (flower)"],
    "psy": ["shrink", "psychiatrist", "psychologist"],
    "balance": ["scale", "balance", "Libra", "snitch (slang)"],
    "raisonnable": ["reasonable", "sensible", "appropriate"],
    "sensible": ["sensitive", "touchy", "noticeable"],
    "déposer": ["deposit", "put down", "drop off", "file"],
    "matière": ["subject", "matter", "material"],
    "bagarre": ["fight", "brawl", "scuffle"],
    "pigé": ["got it", "understood"],
    "large": ["wide", "broad", "ample"],
    "donnée": ["data", "given (fact)"],
    "jo": ["Jo (name)"],
    "brave": ["brave", "gallant", "stalwart"],
    "portefeuille": ["wallet", "portfolio", "briefcase"],
    "tours": ["turns", "towers", "tricks", "Tours (city)"],
    "supérieur": ["superior", "higher", "above"],
    "précieux": ["precious", "valuable", "affected (literary)"],
    "panne": ["breakdown", "fault"],
    "renvoyer": ["send back", "fire", "dismiss", "refer"],
    "loyer": ["rent", "rental"],
    "humour": ["humor", "humour"],
    "trafic": ["traffic", "trade"],
    "do": ["C (musical note)"],
    "remise": ["discount", "shed", "delivery"],
    "participer": ["participate", "take part", "contribute"],
    "coucou": ["cuckoo", "hiya! (greeting)", "cuckoo clock"],
    "pouls": ["pulse", "beat", "pulsation"],
    # Continuing the exhaustive review (ranks 1900-2200 of ~4900). Two
    # more false friends, verified via web search: "caution" in French
    # means "deposit/security/bail", never English "caution"
    # (carefulness) -- the sourced gloss led with the false-friend word
    # "caution" itself; "définitivement" means "permanently/once and
    # for all", never English "definitely" -- the sourced gloss
    # ("conclusively", "definitively") didn't actively mislead but
    # also never stated the real meaning. Also outright wrong: "gants"
    # (gloves) was glossed as just "Gants", not a translation at all;
    # "diane" (the name) was glossed with a butterfly species name
    # ("Southern Festoon"); "chirurgien" (surgeon) included the
    # unrelated "surgeonfish".
    "élever": ["raise", "bring up", "breed", "elevate"],
    "taule": ["prison (slang)", "crib", "pad"],
    "pur": ["pure", "clean", "absolute", "mere"],
    "culture": ["culture", "cultivation", "tillage"],
    "gants": ["gloves"],
    "témoignage": ["testimony", "evidence", "deposition"],
    "diane": ["Diane"],
    "pisser": ["piss", "pee"],
    "salade": ["salad"],
    "flotte": ["fleet", "water (slang)"],
    "rage": ["rage", "fury", "rabies"],
    "chic": ["chic", "stylish", "great! (interjection)"],
    "rigole": ["drain", "gutter", "ditch"],
    "vague": ["wave", "vague", "vagueness"],
    "soutenir": ["support", "bear", "endure", "stand"],
    "floride": ["Florida", "florid"],
    "charme": ["charm", "grace", "spell"],
    "interne": ["internal", "inner", "intern (medical trainee)"],
    "sein": ["breast", "within (au sein de)", "bosom"],
    "fichu": ["crappy", "darned", "done for", "headscarf (noun)"],
    "parent": ["parent", "relative", "kin"],
    "gratuit": ["free", "complimentary", "gratuitous", "unfounded"],
    "étude": ["study", "étude (music)"],
    "bol": ["bowl", "luck (slang)"],
    "léger": ["light", "slight", "mild"],
    "cité": ["city", "complex (housing)", "district"],
    "remède": ["remedy", "cure", "medicine"],
    "couler": ["flow", "sink", "run (liquid)"],
    "emporter": ["take away", "carry away", "lose one's temper (s'emporter)"],
    "pratiquement": ["practically", "almost", "virtually"],
    "caution": ["deposit (security)", "bail", "guarantee"],
    "rond": ["round", "circle", "ring"],
    "intelligence": ["intelligence", "smarts", "aptitude"],
    "plaindre": ["pity", "complain (se plaindre)"],
    "so": ["so (interjection)", "SW (compass)"],
    "esclave": ["slave", "bondman", "thrall"],
    "amant": ["lover"],
    "chirurgien": ["surgeon"],
    "crever": ["burst", "be exhausted (slang)", "die (slang)"],
    "grandir": ["grow", "grow up"],
    "totale": ["the whole works (slang)", "total (feminine)"],
    "reconnaissance": ["recognition", "gratitude", "identification"],
    "rouler": ["roll", "drive", "cheat", "take in"],
    "réveil": ["alarm clock", "awakening", "waking up"],
    "détendre": ["relax", "loosen", "unwind"],
    "définitivement": ["permanently", "once and for all", "definitively"],
    "noix": ["walnut", "nut"],
    "lot": ["batch", "lot", "prize (lottery)"],
    "serré": ["tight", "cramped", "close (competition)"],
    "bail": ["lease", "it's been ages! (ça fait un bail)"],
    "héroïne": ["heroine", "heroin"],
    "opérer": ["operate", "carry out", "act"],
    "rupture": ["breakup", "rupture", "break"],
    "assuré": ["confident", "assured", "insured"],
    "tester": ["test", "try out", "make a will (legal)"],
    "creuser": ["dig"],
    "masse": ["mass", "crowd", "heap", "ground (electrical)"],
    # Continuing the exhaustive review (ranks 2200-2500 of ~4900). The
    # standout here is "collège", one of the most commonly cited
    # French/English false friends (verified via web search): it means
    # "middle school" (ages 11-15), never "high school" or "college" --
    # the sourced gloss offered only "high school"/"gymnasium"/
    # "grammar-school", none of them correct. Also fixed something more
    # serious than a stylistic gap: "enlèvement" (abduction/kidnapping)
    # included "rape" as a gloss, which is simply wrong -- "rape" in
    # French is "viol", a completely different word (already correctly
    # present elsewhere in this list). Verified via web search before
    # removing it, given the severity of leaving a wrong gloss like that
    # in place. Other outright-wrong entries: "lincoln" was glossed with
    # an obscure sheep-breed name; "nicole" gave "Nicoll", a different
    # surname; "bouffer" (informal "to eat") was glossed as "puff".
    "collège": ["middle school", "junior high"],
    "dent": ["tooth", "teeth", "cog", "prong"],
    "pétrole": ["oil", "petroleum", "kerosene"],
    "solitaire": ["solitary", "lonely", "solitaire (card game)"],
    "arracher": ["pull out", "tear out", "rip out", "eradicate"],
    "tendre": ["tender", "soft", "stretch out", "hold out"],
    "issue": ["exit", "way out", "outlet", "egress"],
    "débrouiller": ["sort out", "manage (se débrouiller)", "figure out"],
    "timide": ["shy", "timid", "bashful"],
    "chevalier": ["knight"],
    "précisément": ["precisely", "exactly", "accurately"],
    "ordures": ["garbage", "trash", "rubbish"],
    "vomir": ["puke", "throw up", "vomit"],
    "christine": ["Christine", "Christina"],
    "résistance": ["resistance", "resistor", "stand"],
    "moyenne": ["average", "mean"],
    "net": ["clean", "clear", "net (profit)", "sharp"],
    "conducteur": ["driver", "conductor", "leading"],
    "maintenir": ["maintain", "keep", "uphold", "continue"],
    "abattre": ["shoot down", "kill", "fell (a tree)", "knock down"],
    "jules": ["Jules (name)", "boyfriend (dated slang)"],
    "combinaison": ["combination", "jumpsuit", "overall"],
    "lincoln": ["Lincoln (name)"],
    "four": ["oven", "furnace", "kiln"],
    "ordure": ["garbage", "filth", "scum (insult)", "bastard (insult)"],
    "marin": ["sailor", "marine", "maritime"],
    "revanche": ["revenge", "rematch", "retribution"],
    "franc": ["frank", "honest", "franc (former currency)"],
    "piqué": ["stung", "pricked", "annoyed", "dive (aviation)"],
    "casque": ["helmet", "headphones"],
    "prime": ["bonus", "premium", "bounty"],
    "chatte": ["she-cat", "pussy (vulgar slang)"],
    "mordu": ["bitten", "buff (enthusiast)", "fan"],
    "délire": ["delirium", "madness (colloquial)", "craziness"],
    "trente": ["thirty"],
    "pension": ["pension", "boarding house", "guesthouse"],
    "crève": ["cold (illness)", "chill"],
    "enquêter": ["investigate", "look into"],
    "asile": ["asylum", "sanctuary"],
    "allumer": ["light", "turn on", "ignite", "kindle"],
    "tarder": ["delay", "take long", "be late"],
    "hop": ["hup! (interjection)", "there we go!"],
    "blé": ["wheat", "dough (money slang)"],
    "entrain": ["enthusiasm", "liveliness", "drive"],
    "accéder": ["access", "reach", "agree to (a request)"],
    "manche": ["sleeve", "handle", "English Channel", "round (in a game)"],
    "dalle": ["slab", "flagstone", "hunger (slang: avoir la dalle)"],
    "enlèvement": ["abduction", "kidnapping", "removal"],
    "historique": ["historical", "historic", "history", "log (computing)"],
    "piquer": ["pierce", "prick", "sting", "steal (slang)"],
    "énerver": ["annoy", "irritate", "get on someone's nerves"],
    "he": ["hey! (interjection)", "he (English loanword)"],
    "faiblesse": ["weakness", "frailty", "faintness"],
    "bouffer": ["eat (informal)", "scoff down"],
    "avertir": ["warn", "alert", "caution"],
    "nicole": ["Nicole"],
    # Continuing the exhaustive review (ranks 2500-2800 of ~4900).
    # "prétendre" is a well-documented false friend, verified via web
    # search: it means "to claim/assert", never "to pretend" (that's
    # "faire semblant") -- the sourced gloss actively included the
    # wrong "pretend" and never stated the real meaning at all. Also
    # outright wrong: "prêter" (to lend) included "borrow", which is
    # the opposite verb ("emprunter"); "montée" (climb/ascent) was
    # glossed as "branche" -- a different French word entirely, most
    # likely a row-alignment error in the source data; "tache" (stain)
    # included "dent" -- again a different French word (tooth).
    "élu": ["elected", "elected official"],
    "serrer": ["squeeze", "tighten", "hold tight", "shake (hands)"],
    "trouble": ["trouble", "disorder", "unease", "blurred/murky (adjective)"],
    "rapporter": ["bring back", "report", "yield (profit)", "tattle (slang)"],
    "sourd": ["deaf", "muted", "dull", "blunt"],
    "suicider": ["commit suicide", "kill oneself"],
    "chant": ["song", "singing", "chant"],
    "nid": ["nest", "den", "lair"],
    "atelier": ["workshop", "studio", "atelier"],
    "déplacé": ["displaced", "displaced person", "inappropriate (remark)"],
    "quelconque": ["any", "some kind of", "mediocre (pejorative)"],
    "fillette": ["little girl"],
    "quête": ["quest", "search", "collection (fundraising)"],
    "grève": ["strike (labor)", "shore", "bank (river)"],
    "culotte": ["underwear", "panties", "briefs", "culottes"],
    "suisse": ["Swiss", "Switzerland"],
    "signaler": ["report", "point out", "flag", "alert"],
    "pendu": ["hanged (person)", "hangman (game)"],
    "prêter": ["lend", "loan", "advance"],
    "buter": ["kill (slang)", "stumble", "trip (over)"],
    "soupir": ["sigh", "quarter rest (music)"],
    "horloge": ["clock"],
    "pétrin": ["mess", "hot water", "jam", "kneading trough"],
    "vedette": ["star (celebrity)", "speedboat", "spotlight", "top billing"],
    "prétendre": ["claim", "allege", "assert"],
    "marteau": ["hammer", "door knocker", "gavel", "crazy/nuts (slang)"],
    "saisi": ["seized", "grabbed", "caught"],
    "déterminer": ["determine", "decide", "cause", "fix"],
    "montée": ["climb", "ascent", "rise", "uphill"],
    "tache": ["stain", "spot", "blot", "blemish"],
    "cinquième": ["fifth", "seventh grade (French school year)"],
    "coke": ["coke (cocaine, slang)", "Coke (cola)", "coke (fuel)"],
    "aperçu": ["overview", "glimpse", "insight"],
    "réussite": ["success", "solitaire (card game: patience)"],
    "plaie": ["wound", "sore", "nuisance (figurative: quelle plaie!)"],
    "relever": ["pick up (again)", "raise", "point out", "relieve"],
    "exposé": ["presentation", "talk", "report (school)"],
    "assaut": ["assault", "attack", "charge", "aggression"],
    "recherché": ["wanted", "sought-after", "refined (style)"],
    "çà": ["here and there (çà et là)"],
    "mouche": ["fly (insect)", "beauty spot", "soul patch"],
    "grillé": ["grilled", "toasted"],
    "baignoire": ["bathtub", "bath", "theater box (ground floor)"],
    "coincer": ["jam", "stick", "wedge", "corner/catch (someone)"],
    "révélé": ["revealed"],
    "saleté": ["dirt", "filth", "dirty trick (colloquial)"],
    "plaisanterie": ["joke", "jest", "prank"],
    "thème": ["theme", "subject", "topic"],
    "ennui": ["boredom", "trouble/problem", "ennui"],
    "came": ["drugs (slang)", "dope"],
    "disputer": ["contest", "dispute", "argue (se disputer)"],
    "are": ["are (unit of area, 100 m²)"],
    # Continuing the exhaustive review (ranks 2800-3100 of ~4900).
    # "licence" is a factual/academic-level error worth flagging on its
    # own, verified via web search: in the French university system a
    # licence is a Bachelor's-equivalent degree (3 years), never a
    # doctorate -- the sourced gloss included "doctorate" outright.
    # Also outright wrong: "citron" (lemon) included a butterfly
    # species name ("Common Brimstone") and "lime" (lime is "citron
    # vert" in French, a different compound word); "chiffre" (number)
    # included yet another butterfly species name ("Niobe Fritillary");
    # "coiffure" (hairstyle) included "coiffeur", a different word
    # (the hairdresser, a person, not the hairstyle); "correspondance"
    # included "responsibility" (that's "responsabilité", unrelated).
    "règne": ["reign", "kingdom", "rule"],
    "sou": ["penny (old coin)", "cent"],
    "coller": ["stick", "glue", "fail (school slang)"],
    "fouille": ["search", "frisking", "excavation"],
    "reporter": ["reporter (noun)", "postpone", "put off", "carry over"],
    "développement": ["development", "growth"],
    "han": ["ugh! (interjection)", "Han (name/ethnicity)"],
    "descente": ["descent", "going down", "police raid"],
    "plomb": ["lead (metal)", "fuse (electrical)", "sinker"],
    "décharge": ["landfill", "discharge", "waiver (legal)"],
    "attacher": ["attach", "tie", "fasten", "bind"],
    "taupe": ["mole (animal)", "taupe (color)", "mole (spy, slang)"],
    "inspiration": ["inspiration", "inhalation"],
    "coco": ["coconut (informal)", "dear/sweetie (term of endearment)", "commie (dated slang)"],
    "jacques": ["Jacques (name)", "James", "Jack"],
    "extra": ["extra", "great (colloquial)"],
    "ci": ["here (as in ci-dessus, celui-ci)"],
    "sirène": ["siren (alarm)", "mermaid"],
    "jalousie": ["jealousy", "venetian blind (window)"],
    "statut": ["status", "by-law", "article", "regulation"],
    "requête": ["request", "query (computing)", "petition"],
    "planter": ["plant", "stick", "crash/fail (se planter)"],
    "citron": ["lemon"],
    "impressionner": ["impress"],
    "spécialité": ["specialty", "field of expertise", "culinary specialty"],
    "arraché": ["torn out", "snatch (weightlifting)"],
    "croisé": ["crossed", "crusader", "crossbred"],
    "sensé": ["sensible", "reasonable", "sane", "wise"],
    "flipper": ["pinball (machine)", "freak out (slang verb)"],
    "banc": ["bench", "sandbank", "school (of fish)"],
    "engin": ["device", "machine", "vehicle (engin spatial, etc.)", "gizmo"],
    "peste": ["plague", "pest (annoying person, colloquial)"],
    "académie": ["academy", "regional school district (French admin)"],
    "pompe": ["pump", "pomp", "shoe (slang, plural: pompes)"],
    "présentation": ["presentation", "introduction", "appearance"],
    "chiffre": ["number", "digit", "figure", "cipher"],
    "hurler": ["howl", "scream", "yell", "bellow"],
    "brosse": ["brush"],
    "flèche": ["arrow", "spire"],
    "ordonnance": ["prescription", "order", "ordinance"],
    "consulter": ["consult"],
    "bêtise": ["silliness", "stupid thing/blunder", "foolishness"],
    "inconscient": ["unconscious", "reckless", "thoughtless"],
    "poussée": ["push", "surge (e.g. fever)", "thrust"],
    "coiffure": ["hairstyle", "hairdo", "headdress"],
    "botte": ["boot", "bunch/bundle (vegetables)"],
    "ras": ["close-cropped", "fed up (ras-le-bol)", "level with (au ras de)"],
    "halte": ["stop", "halt", "break (during travel)"],
    "licence": ["license", "bachelor's degree (French university)", "authorization"],
    "facteur": ["factor", "mailman", "postman"],
    "claque": ["slap", "claque (paid applauders)"],
    "sabre": ["saber", "sabre", "cut-throat razor"],
    "filet": ["net", "fillet (meat/fish)", "thread"],
    "fixer": ["set", "fix", "stare at", "define"],
    "correspondance": ["correspondence (mail)", "connection (transit transfer)"],
    "chanteur": ["singer", "vocalist"],
    "automatique": ["automatic", "default"],
    "maîtrise": ["mastery", "control", "command (of a skill)"],
    # Continuing the exhaustive review (ranks 3100-3400 of ~4900).
    # "décevoir" is another verified false friend: it means "to
    # disappoint", never "to deceive" (that's "tromper") -- the sourced
    # gloss actively led with the wrong "deceive". "sympathique" is a
    # second false friend in this batch: it means "nice/likable",
    # never "sympathetic" (that's "compatissant") -- the sourced gloss
    # included the misleading "sympathetic" outright. Also outright
    # wrong: "chèvre" (goat) included "Ram" (that's Aries, unrelated);
    # "rein" (kidney) included the English homograph "rein" (a horse
    # strap, a completely different word); "isabelle" (the name)
    # included a moth species name ("Spanish moon moth") -- yet
    # another lepidoptera contamination in this dataset.
    "discipline": ["discipline"],
    "loge": ["theater box", "dressing room", "lodge (Masonic/porter's)"],
    "décevoir": ["disappoint", "let down"],
    "ado": ["teenager", "teen", "youth"],
    "traumatisme": ["trauma", "traumatism"],
    "céréales": ["cereal", "cereals", "grain"],
    "georges": ["George (name)", "autopilot (aviation slang)"],
    "arabe": ["Arab", "Arabic", "Arabian"],
    "légèrement": ["lightly", "slightly"],
    "allure": ["appearance", "look", "speed/pace"],
    "ressort": ["spring (mechanical)", "energy", "drive/motivation"],
    "veine": ["vein", "luck (slang: avoir de la veine)"],
    "pan": ["panel", "flap", "bang! (onomatopoeia)"],
    "fusée": ["rocket", "fuze/fuse"],
    "caca": ["poop", "caca", "yuck (interjection)"],
    "marquer": ["mark", "score", "denote"],
    "chèvre": ["goat", "goat cheese", "nanny goat"],
    "gage": ["pledge", "deposit", "forfeit/dare (party game)"],
    "précédent": ["precedent", "previous", "preceding"],
    "secondaire": ["secondary", "minor", "accessory"],
    "surmonter": ["overcome", "surmount"],
    "raser": ["shave", "raze", "bore (colloquial: ça me rase)"],
    "observation": ["observation", "remark", "notice"],
    "grossier": ["crude", "rude", "vulgar"],
    "môme": ["kid", "child (informal)"],
    "randall": ["Randall (name)"],
    "char": ["tank (military)", "cart", "chariot", "car (Quebec French slang)"],
    "prévoir": ["plan", "foresee", "anticipate", "prepare for"],
    "vachement": ["really", "very (slang intensifier)"],
    "marcel": ["tank top", "undershirt", "vest"],
    "stand": ["stand (exhibition booth)", "stand (grandstand)"],
    "délai": ["deadline", "time limit", "delay"],
    "cassie": ["Cassie (name)"],
    "colonie": ["colony", "settlement", "summer camp (colonie de vacances)"],
    "isabelle": ["Isabelle", "Isabel"],
    "colis": ["package", "parcel"],
    "purée": ["mashed potatoes", "puree", "mush"],
    "arc": ["bow (weapon)", "arch", "arc"],
    "banane": ["banana", "big smile (avoir la banane)", "fanny pack (sac banane)"],
    "réplique": ["line/quote (film/theater)", "reply", "replica", "aftershock"],
    "rein": ["kidney"],
    "favori": ["favorite", "favored", "preferred"],
    "attentat": ["attack (terrorist)", "assassination attempt", "assault"],
    "renverser": ["overturn", "spill", "knock down (vehicle)", "reverse"],
    "distributeur": ["vending machine", "distributor", "ATM (distributeur de billets)"],
    "fumier": ["manure", "dung", "bastard (insult)"],
    "baraque": ["shack", "hut", "house (informal)", "barrack (military)"],
    "nage": ["swimming", "stroke"],
    "lessive": ["laundry", "detergent", "washing powder"],
    "urine": ["urine", "pee", "piss"],
    "rasoir": ["razor", "boring (slang adjective)"],
    "sympathique": ["nice", "likable", "friendly", "congenial"],
    "formulaire": ["form", "blank (form)"],
    "répondeur": ["answering machine", "voicemail"],
    "mineur": ["minor", "miner (mine worker)"],
    "alimentation": ["food", "nutrition", "power supply (electrical)"],
    "rex": ["Rex (name/pet name)", "rex rabbit"],
    "outre": ["beyond", "furthermore (en outre)", "besides"],
    # Continuing the exhaustive review (ranks 3400-3700 of ~4900).
    # Three more false friends, verified via web search: "actuel"
    # means "current/present-day", never "actual" (that's "réel") --
    # the sourced gloss led with the wrong "actual"; "stage" means
    # "internship/training course", never a performance platform (that
    # IS "scène") -- the sourced gloss included the equally wrong
    # "season" (that's "saison"); "assumer" means "to take on/accept
    # responsibility for", never "to assume" (that's "présumer"/
    # "supposer") -- the sourced gloss led with the wrong "assume".
    # Also outright wrong: "braquage" (a very common crime-slang word
    # for "robbery/heist") was glossed entirely with automotive
    # steering terminology, missing the common sense completely; "bac"
    # (very commonly short for "baccalauréat", the French high-school
    # exit exam) was glossed only with vague container words.
    "braquage": ["robbery", "heist", "steering (car)"],
    "pince": ["pliers", "tongs", "clip", "claw"],
    "primaire": ["primary", "elementary"],
    "baie": ["bay", "berry", "picture window"],
    "deb": ["Deb (name, short for Deborah)", "debutante (informal)"],
    "rappel": ["reminder", "booster (vaccine)", "recall"],
    "office": ["religious service", "function/role", "pantry (dated)"],
    "mi": ["mi (musical note, = E)"],
    "mental": ["mental"],
    "messager": ["messenger"],
    "souhait": ["wish", "desire", "aspiration"],
    "crochet": ["hook", "bracket", "crochet (knitting)", "detour (faire un crochet)"],
    "naître": ["to be born", "be born"],
    "age": ["age (likely âge)", "draft-pole (archaic, rare)"],
    "rude": ["harsh", "tough", "rough"],
    "passager": ["passenger", "passing", "fleeting"],
    "raide": ["stiff", "rigid", "steep"],
    "peintre": ["painter"],
    "rebelle": ["rebellious", "disobedient", "recalcitrant", "rebel (noun)"],
    "montage": ["editing (film)", "montage", "assembly"],
    "rhume": ["cold", "common cold"],
    "mat": ["matte", "checkmate", "flat"],
    "assumer": ["take on", "accept/own (responsibility)", "come to terms with"],
    "régulièrement": ["regularly", "evenly"],
    "voisinage": ["neighborhood", "vicinity", "nearness"],
    "accordé": ["granted", "agreed", "tuned", "betrothed (archaic)"],
    "réclame": ["advertisement", "ad"],
    "canne": ["cane", "walking stick", "fishing rod", "reed"],
    "actuel": ["current", "present-day", "present"],
    "garer": ["park (a vehicle)"],
    "détente": ["relaxation", "trigger (gun)", "détente (diplomatic)"],
    "limousine": ["limousine (car)"],
    "duel": ["duel"],
    "néanmoins": ["nevertheless", "nonetheless"],
    "sixième": ["sixth", "sixth grade (French school year)"],
    "carré": ["square", "straightforward"],
    "agenda": ["diary", "planner", "appointment book"],
    "culot": ["nerve", "cheek", "audacity"],
    "ressortir": ["stand out", "go back out", "emerge"],
    "gray": ["Gray (name/place)"],
    "débarquer": ["disembark", "land", "show up (unannounced, colloquial)"],
    "mousse": ["foam", "moss", "mousse (dessert)", "cabin boy"],
    "stage": ["internship", "training course"],
    "comporter": ["include", "comprise", "behave (se comporter)"],
    "permanence": ["permanence", "study hall (school, la permanence)"],
    "décrocher": ["pick up (phone)", "unhook", "land (a job)", "drop out (school, colloquial)"],
    "guise": ["as one pleases (à sa guise)", "by way of (en guise de)"],
    "bouquin": ["book (informal)"],
    "céder": ["give in", "give way", "cede", "yield"],
    "rigoler": ["laugh", "joke around", "kid", "tease"],
    "minuscule": ["tiny", "minuscule", "lower case (letter)"],
    "internationale": ["international (feminine)", "The Internationale (anthem)"],
    "fantasme": ["fantasy", "illusion"],
    "conséquence": ["consequence", "result"],
    "express": ["express", "espresso (coffee)", "express train"],
    "volume": ["volume", "capacity", "loudness"],
    "enthousiasme": ["enthusiasm", "zest", "alacrity"],
    "tanner": ["tan (leather)", "pester/bug (slang)"],
    "bac": ["baccalauréat (exam, informal)", "bin/tub", "tray"],
    "parages": ["vicinity", "area (dans les parages = in the area)"],
    # Continuing the exhaustive review (ranks 3700-4000 of ~4900).
    # "pâques" (Easter) wrongly included "Passover" as a direct
    # synonym -- verified via web search that these are genuinely
    # distinct in French: Pâques (no article) is specifically the
    # Christian holiday, while Passover is "la Pâque" (feminine, with
    # the article), a related but different word. Other outright
    # errors: "mouton" (sheep) was missing the literal animal meaning
    # entirely, listing only obscure synonyms for "dust bunny";
    # "efface" (a conjugated form of "effacer", "erases") had leaked
    # into the vocab list as its own headword, glossed as the noun
    # "eraser" (a different word, "gomme"); "boeuf" (the unaccented
    # duplicate of "bœuf") was glossed as "Boeuf River", an obscure US
    # place name, instead of matching the correct "bœuf" entry (beef).
    "défoncer": ["smash", "break down", "get high (slang)"],
    "cardinal": ["cardinal"],
    "prudence": ["caution", "care", "prudence"],
    "noyé": ["drowned"],
    "soulager": ["relieve", "ease", "alleviate"],
    "mere": ["mother (likely mère)"],
    "vase": ["vase (container)", "mud/silt (feminine noun)"],
    "reins": ["kidneys", "lower back", "loin"],
    "coupure": ["cut", "bill (banknote)", "power outage (coupure de courant)"],
    "romain": ["Roman"],
    "vilaine": ["nasty (feminine)", "wicked (feminine)", "Vilaine (river)"],
    "définition": ["definition", "resolution (image)"],
    "boeuf": ["beef", "ox", "bovine"],
    "raccompagner": ["walk/drive (someone) home", "see off", "take back"],
    "richesse": ["wealth", "richness", "affluence", "fortune"],
    "bilan": ["balance sheet", "assessment (faire le bilan)"],
    "pope": ["Orthodox priest", "priest"],
    "réglo": ["fair", "honest", "trustworthy (slang)"],
    "juive": ["Jewish (feminine)", "Jewish woman"],
    "maternelle": ["kindergarten", "nursery school"],
    "parvenir": ["achieve", "attain", "manage to", "arrive at"],
    "clou": ["nail", "spike", "stud", "clove (clou de girofle)"],
    "conséquent": ["consequent", "substantial/sizeable", "therefore (par conséquent)"],
    "largement": ["largely", "widely", "easily/by far", "amply"],
    "écarter": ["push aside", "spread apart", "rule out", "remove"],
    "gâchette": ["trigger (gun)"],
    "fosse": ["pit", "trench", "grave", "burial pit"],
    "dexter": ["Dexter (name)"],
    "cuisinier": ["cook", "chef"],
    "marianne": ["Marianne (name/French national symbol)"],
    "sonnette": ["doorbell", "bell"],
    "cogner": ["knock", "bang", "hit"],
    "flûte": ["flute (instrument)", "champagne flute (glass)", "thin baguette (bread)"],
    "dentaire": ["dental"],
    "mouton": ["sheep", "mutton", "dust bunny (colloquial)"],
    "excès": ["excess", "overindulgence"],
    "slip": ["briefs", "underwear", "panties"],
    "pâques": ["Easter"],
    "laid": ["ugly"],
    "bouquet": ["bouquet (flowers)", "cluster"],
    "majeur": ["of age (legal adult)", "major", "middle finger (anatomical)"],
    "soutenu": ["sustained", "supported", "formal (style soutenu)"],
    "cellulaire": ["cellular", "cell phone (Quebec French)"],
    "bassin": ["basin (water/geographic)", "pelvis (anatomical)"],
    "pleuvoir": ["to rain", "rain"],
    "piloter": ["pilot (aircraft)", "drive", "steer"],
    "efface": ["erases"],
    "lavage": ["washing", "wash", "cleaning"],
    "curé": ["parish priest", "clergyman", "parson"],
    "sécher": ["dry", "ditch/skip (class, slang)"],
    "ouf": ["phew! (interjection)", "crazy (verlan slang for fou)"],
    "réduction": ["discount", "reduction", "decrease"],
    # Continuing the exhaustive review (ranks 4000-4300 of ~4900). Two
    # more false friends, verified via web search: "librairie" means
    # "bookstore", never "library" (that's "bibliothèque") -- the
    # sourced gloss included the misleading "library" outright, one of
    # the most commonly cited French/English false friends; "vicieux"
    # primarily means "perverted/depraved/kinky", and does not reliably
    # carry the English "vicious" (violent) sense the sourced gloss led
    # with. Also outright wrong: "chaton" (kitten) was missing that
    # core meaning entirely, listing only obscure botany/jewelry terms;
    # "étendre" (to extend/stretch out) was glossed entirely with
    # unrelated words ("adulterate", "aggrandize", "anoint"); "grouille"
    # (a conjugated form of "grouiller") had leaked in as its own
    # headword glossed as "girl Friday", unrelated.
    "indic": ["informant (slang)", "snitch"],
    "zoé": ["Zoe", "Zoé"],
    "acquis": ["acquired", "gained", "rights/gains (les acquis sociaux)"],
    "vanter": ["praise", "vaunt", "boast (se vanter)"],
    "spa": ["spa", "whirlpool bath"],
    "bénéfice": ["profit", "benefit", "gain"],
    "more": ["more (English loanword)"],
    "grouille": ["hurry up! (grouille-toi)", "swarms/teems"],
    "commode": ["convenient", "handy", "chest of drawers (furniture)"],
    "porteur": ["bearer", "porter", "carrier (disease)"],
    "biscuit": ["biscuit", "cookie"],
    "immédiat": ["immediate", "instant", "instantaneous"],
    "griller": ["grill", "toast", "catch red-handed (slang)"],
    "cote": ["rating", "odds", "quotation (stock)"],
    "déception": ["disappointment", "disillusionment"],
    "verser": ["pour", "pay/deposit (money)", "shed (tears)"],
    "sentence": ["verdict (legal)", "maxim", "saying"],
    "boucler": ["buckle", "fasten", "lock up (slang)", "wrap up/finish"],
    "épais": ["thick"],
    "brèche": ["breach", "gap"],
    "chaton": ["kitten", "catkin (botany)", "gem setting (jewelry)"],
    "tremblement": ["trembling", "shaking", "earthquake (tremblement de terre)"],
    "saul": ["Saul (name)"],
    "froc": ["pants (slang)", "frock (monk's robe)", "cowl"],
    "presser": ["press", "squeeze", "hurry (se presser)"],
    "indépendant": ["independent"],
    "introduire": ["introduce", "insert", "bring in"],
    "étendre": ["extend", "stretch out", "spread out", "hang (laundry)"],
    "pitoyable": ["pitiful", "pathetic"],
    "brune": ["brunette", "brown (feminine)"],
    "librairie": ["bookstore", "bookshop", "bookseller"],
    "soviétique": ["Soviet"],
    "asiatique": ["Asian", "Asiatic"],
    "craque": ["fib", "lie (slang)"],
    "comble": ["peak", "height (figurative)", "last straw (c'est le comble!)", "attic (les combles)"],
    "scie": ["saw (tool)"],
    "sympathie": ["liking", "friendliness", "fellow-feeling"],
    "achever": ["finish", "complete", "finish off (kill, e.g. wounded animal)"],
    "disposer": ["arrange", "have at one's disposal"],
    "bulle": ["bubble", "blister", "comic/speech bubble", "papal bull (document)"],
    "cordon": ["cord", "string", "cordon (police)"],
    "tailleur": ["tailor", "woman's suit (tailleur)"],
    "saumon": ["salmon", "salmon pink"],
    "vicieux": ["perverted", "depraved", "kinky", "sly/tricky"],
    # Continuing the exhaustive review (ranks 4300-4600 of ~4900).
    # "résumé" is another verified false friend: in French it means
    # "summary", never the English "résumé"/"resume" (a job-application
    # CV, which in French is just "CV") -- the sourced gloss directly
    # conflated the two by including "curriculum vita"/"resume"/"vita".
    # Also outright wrong, including one case where the sourced gloss
    # gave the literal opposite meaning: "malchance" (bad luck)
    # included "good luck" as a synonym; "homard" (lobster) included
    # "scallop", a different shellfish entirely; "gratte" (a conjugated
    # form of "grattir", "scratches") had leaked in as its own headword
    # glossed as "axe"/"blade", unrelated.
    "permanente": ["permanent", "perm (hairstyle)"],
    "gonzesse": ["chick (slang)", "girl"],
    "détourner": ["divert", "hijack (a plane)", "embezzle"],
    "précaution": ["precaution", "caution", "care"],
    "graine": ["seed", "grain", "pip"],
    "maniaque": ["maniacal", "maniac", "neat freak (fussy, colloquial)"],
    "fondu": ["melted", "fade (film editing)"],
    "devise": ["currency", "motto"],
    "pâté": ["pâté (food)", "block (pâté de maisons)"],
    "méfier": ["distrust (se méfier)", "be wary of", "watch out"],
    "globe": ["globe", "ball", "eyeball (globe oculaire)"],
    "lente": ["slow (feminine)", "nit (louse egg)"],
    "arche": ["arch", "ark (Noah's)"],
    "alaska": ["Alaska"],
    "prétendu": ["so-called", "alleged", "supposed"],
    "ignoré": ["ignored", "unknown"],
    "résumé": ["summary"],
    "contourner": ["go around", "bypass", "circumvent (a law/rule)"],
    "lecteur": ["reader (of books)", "player (CD/DVD)", "drive (disk)"],
    "dément": ["demented", "awesome! (slang)"],
    "permanent": ["permanent", "constant", "enduring"],
    "léon": ["Leon (name)", "Leo"],
    "homard": ["lobster"],
    "terminale": ["twelfth grade (French school year)", "senior year"],
    "poney": ["pony"],
    "malchance": ["bad luck", "misfortune", "ill-luck"],
    "grade": ["rank (military/professional)", "grade", "degree"],
    "gorille": ["gorilla", "bodyguard (slang)"],
    "atteinte": ["infringement", "violation", "harm (porter atteinte à)"],
    "abandon": ["abandonment", "desertion", "debt forgiveness (legal)"],
    "déguisement": ["disguise", "costume"],
    "veau": ["calf (animal)", "veal (meat)"],
    "polonais": ["Polish", "Pole"],
    "fréquenter": ["frequent (a place)", "attend", "date/see (someone romantically)"],
    "correspondant": ["corresponding", "correspondent (news/pen pal)", "counterpart"],
    "sourde": ["deaf (feminine)", "voiceless consonant (linguistics)"],
    "détour": ["detour"],
    "réclamer": ["claim", "demand", "ask for"],
    "pieu": ["post", "stake", "bed (slang: le pieu)"],
    "schéma": ["diagram", "sketch", "pattern"],
    "gratte": ["scratches (il/elle gratte)", "scraper (tool)"],
    "remuer": ["move", "stir", "shift"],
    "satané": ["damn/blasted (colloquial)", "devilish"],
    "cafard": ["cockroach", "the blues (avoir le cafard)"],
    "gratter": ["scratch", "scrape", "itch"],
    # Final batch of the exhaustive review (ranks 4600-4900 of ~4900).
    # This completes the full word-by-word pass through every entry in
    # the ~4,900-word vocabulary list. The most serious error in this
    # last batch: "compagne" (feminine of "compagnon") was missing its
    # extremely common, basic meaning ("companion"/"partner" --
    # girlfriend or wife) entirely, replaced only by "chaperon"/
    # "duenna" (an archaic Spanish-cultural concept, a woman who
    # supervises unmarried women) -- about as far from the real
    # everyday meaning as a gloss in this dataset gets. Also outright
    # wrong: "dizaine" ("about ten") was glossed as "decade" (a ten-
    # YEAR period, "décennie") and "dozen" (exactly twelve,
    # "douzaine") -- neither is what the word means; "recommandation"
    # (recommendation) was missing its own basic meaning entirely,
    # glossed only with indirect words like "caveat"/"enrollment".
    "gueules": ["mouths/faces (plural of gueule)", "gules (heraldry)"],
    "brique": ["brick", "carton (brique de lait)"],
    "recommandation": ["recommendation"],
    "peluche": ["stuffed animal (toy)", "plush (fabric)"],
    "évêque": ["bishop"],
    "procédé": ["process", "method", "procedure", "conduct (dated)"],
    "noyau": ["pit (fruit)", "core", "kernel", "nucleus"],
    "dalton": ["Dalton (name)", "dalton (atomic mass unit)"],
    "faculté": ["faculty (university)", "ability/capacity"],
    "battant": ["fighter (figurative)", "clapper (bell)", "door leaf"],
    "amer": ["bitter", "acrimonious"],
    "bouchon": ["cork", "cap", "traffic jam"],
    "affecter": ["affect", "move (emotionally)", "allocate/assign"],
    "fournisseur": ["supplier", "provider"],
    "activer": ["activate", "speed up", "kindle"],
    "mara": ["Mara (name)"],
    "voiles": ["sails", "veils", "Vela (constellation)"],
    "dominer": ["dominate", "control", "exceed", "surpass"],
    "gonflé": ["swollen", "ballsy/daring (slang)"],
    "blouse": ["smock/work coat", "overall", "blouse (shirt)"],
    "régulier": ["regular", "constant", "steady"],
    "bi": ["bi (bisexual, informal)"],
    "dizaine": ["about ten", "ten or so"],
    "compagne": ["companion", "partner (girlfriend/wife)"],
    "tiffany": ["Tiffany (name)"],
    "tuteur": ["guardian (legal)", "tutor/mentor", "plant stake"],
    "compteur": ["meter", "counter", "speedometer (compteur de vitesse)"],
    "verse": ["pours (il/elle verse)"],
    "gel": ["gel (hair/shower)", "frost", "freeze"],
    "fritz": ["Fritz (name)", "Kraut (dated WWII slang for German)"],
    "ascension": ["ascent", "climb", "Ascension (religious holiday)"],
    "axe": ["axis", "main road (axe routier)"],
    "moniteur": ["monitor (screen)", "instructor (ski, swimming, etc.)"],
    "gigantesque": ["gigantic", "giant", "huge", "astronomical (figurative)"],
    "chantant": ["singing", "melodious", "singsong"],
    "madeleine": ["madeleine (cake)", "Magdalene (name)"],
    "hold-up": ["robbery/heist (hold-up)"],
    "étroit": ["narrow", "tight", "close (relationship)"],
    "débattre": ["debate", "discuss"],
    "console": ["console (gaming)", "bracket (architectural support)"],
    "consommation": ["consumption", "drink (café/bar)", "intake"],
    "défiler": ["march", "parade", "scroll (modern tech)"],
    "kerry": ["Kerry (name)"],
    "galère": ["hassle/ordeal (colloquial)", "galley (ship)"],
    "embarquement": ["embarkation", "boarding"],
    "entente": ["agreement", "accord", "understanding"],
    "réalisation": ["realization", "achievement", "film (director's work)"],
    "corbeau": ["crow", "bracket-corbel (architecture)"],
    "coquille": ["seashell", "typo (printing error)", "athletic cup/jockstrap"],
    "global": ["overall", "comprehensive", "global", "total"],
    # Full review of all 100 verbs' gloss[0], triggered by a user report
    # that "pouvoir" showed "power" instead of "can"/"be able to" in
    # multiple choice -- the same root cause as the entries above, but
    # checked exhaustively here (all 100 verbs) rather than a
    # frequency-ordered sample, since every verb is drilled heavily.
    # "falloir" needed more than reordering: its sourced glosses were
    # garbled sentence fragments ("We need something", "You have to"),
    # not word-level translations, which would have broken typed-answer
    # grading outright.
    "pouvoir": ["can", "be able to", "may", "power"],
    "vouloir": ["want", "wish", "be willing to", "will"],
    "falloir": ["be necessary", "have to", "need"],
    "attendre": ["wait for", "wait", "expect", "await"],
    "partir": ["leave", "depart", "go away"],
    "rester": ["stay", "remain", "keep"],
    "passer": ["pass", "go", "put on", "transfer"],
    "trouver": ["find", "like"],
    "sortir": ["go out", "come out", "bring out", "take out"],
    "comprendre": ["understand", "include"],
    "mettre": ["put", "put on", "wear", "begin"],
    "aider": ["help", "aid", "assist"],
    "arrêter": ["stop", "arrest", "detain"],
    "laisser": ["leave", "let", "allow", "release"],
    "entrer": ["enter", "come into", "go in"],
    "donner": ["give", "donate"],
    "sentir": ["feel", "smell"],
    "chercher": ["look for", "search for", "go after"],
    "porter": ["carry", "bear", "support", "wear"],
    "tenir": ["hold", "keep", "maintain", "hang onto"],
    "vivre": ["live", "alive"],
    "jouer": ["play", "act", "perform"],
    "travailler": ["work", "labour"],
    "garder": ["keep", "guard", "maintain"],
    "essayer": ["try", "attempt"],
    "rentrer": ["come home", "re-enter", "gather in"],
    "commencer": ["start", "begin", "commence"],
    "compter": ["count", "calculate"],
    "marcher": ["walk", "work"],
    "apprendre": ["learn", "teach", "find out"],
    "revoir": ["see again", "review", "revise"],
    "changer": ["change", "alter"],
    "continuer": ["continue", "go on", "keep on"],
    "devenir": ["become", "get", "grow"],
    "occuper": ["occupy", "fill", "take up"],
    "montrer": ["show", "demonstrate", "display"],
    "sembler": ["seem", "appear", "look like"],
    "tirer": ["pull", "draw", "fire"],
    "ouvrir": ["open"],
    "dormir": ["sleep", "be asleep"],
    "rappeler": ["call back", "recall", "remind"],
    "finir": ["finish", "end", "conclude"],
    "retrouver": ["find again", "recover", "rediscover"],
    "excuser": ["excuse", "forgive", "pardon"],
    "battre": ["beat", "applaud", "bang", "break", "clap"],
    "poser": ["place", "lay down", "ask"],
    "imaginer": ["imagine", "picture"],
    "quitter": ["leave", "quit"],
    "toucher": ["touch", "feel"],
    "emmener": ["take along", "take away"],
    "ignorer": ["not know", "ignore"],
    "permettre": ["allow", "permit", "let"],
    "jeter": ["throw", "cast"],
    "dégager": ["clear", "free", "disengage"],
    "aimer": ["like", "love", "enjoy", "appreciate"],
    "suivre": ["follow", "come after", "trail"],
}
for w, g in MANUAL_GLOSS_OVERRIDE.items():
    gloss[w] = g
    gloss_source[w] = "model-override"

# ---------- 5. Rank verb lemmas using a collision-resistant frequency signal ----------
# Many 1st-group verbs (armer, terrer, monder, contrer, celer, poindre...) have a
# present-tense/passe-simple stem that is spelled identically to a much more common
# noun/pronoun/preposition ("arme", "terre", "monde", "contre", "cela", "point").
# Naively summing ALL inflected-form frequencies massively over-counts those obscure
# verbs. Imparfait, futur simple, and the nous/vous present forms are far less prone
# to such homograph collisions (their suffixes -ais/-ait/-ions/-erai/-ons/-ez rarely
# coincide with an unrelated common word), so we use only those forms as the RANKING
# signal. The full conjugation table is still used for the final output once a verb
# is selected.
freq_lookup = dict(clean_freq)

def collision_resistant_score(lemma):
    table = conj[lemma]
    forms = set()
    for k in ("I", "F"):
        for v in (table.get(k) or []):
            if v and v != "NA":
                forms.add(v.lower())
    p = table.get("P") or []
    for v in p[3:5]:  # nous / vous present forms
        if v and v != "NA":
            forms.add(v.lower())
    return sum(freq_lookup.get(f, 0) for f in forms)

verb_candidates = []
for lemma, table in conj.items():
    if not table.get("P"):  # guards against stray empty entries (e.g. "voila")
        continue
    verb_candidates.append((lemma, collision_resistant_score(lemma)))
verb_candidates.sort(key=lambda kv: -kv[1])

top_verbs = []
skipped_verbs_no_gloss = []
for lemma, freq in verb_candidates:
    if freq <= 0:
        continue
    g = gloss.get(lemma)
    if not g:
        skipped_verbs_no_gloss.append(lemma)
        continue
    top_verbs.append((lemma, freq, g))
    if len(top_verbs) == 100:
        break

print(f"[verbs] selected {len(top_verbs)} verbs; {len(skipped_verbs_no_gloss)} high-scoring verb lemmas skipped for missing gloss (first 15: {skipped_verbs_no_gloss[:15]})", file=sys.stderr)

verb_lemma_set = {l for l, _, _ in top_verbs}

# ---------- 6. Build the set of inflected forms "consumed" by the selected verbs ----------
consumed_forms = set()
for lemma in verb_lemma_set:
    table = conj[lemma]
    for k in TENSE_KEYS:
        for v in (table.get(k) or []):
            if v and v != "NA":
                consumed_forms.add(v.lower())
    consumed_forms.add(lemma.lower())

# ---------- 7. Build vocab list from every token NOT consumed by a selected verb ----------
# (A token that happens to also be an inflected form of some OTHER, non-selected verb
# -- e.g. "monde" vs. the obscure verb "monder" -- is simply treated as ordinary
# vocabulary, since that verb never made the final cut.)
plain_freq = defaultdict(int)
plain_first_rank = {}
for rank, (w, c) in enumerate(clean_freq):
    if w in consumed_forms:
        continue
    if w not in plain_freq:
        plain_first_rank[w] = rank
    plain_freq[w] += c

print(f"[vocab] {len(plain_freq)} candidate plain tokens after removing forms of the {len(verb_lemma_set)} selected verbs", file=sys.stderr)

vocab_candidates = sorted(plain_freq.items(), key=lambda kv: (-kv[1], plain_first_rank[kv[0]]))

TARGET_TOTAL = 5000
target_vocab = TARGET_TOTAL - len(top_verbs)

vocab_list = []
skipped_vocab_no_gloss = 0
for w, freq in vocab_candidates:
    if w in verb_lemma_set:
        continue
    g = gloss.get(w)
    if not g:
        skipped_vocab_no_gloss += 1
        continue
    vocab_list.append((w, freq, g))
    if len(vocab_list) == target_vocab:
        break

print(f"[vocab] selected {len(vocab_list)} vocab words; {skipped_vocab_no_gloss} skipped for missing gloss along the way", file=sys.stderr)

# ---------- 8. Emit verbs.json ----------
# "souvenir" has no non-reflexive modern use: it is always "se souvenir" and,
# like every pronominal verb, always takes "etre" in compound tenses -- this is
# a categorical French grammar rule, not something the Lefff data encodes (Lefff
# gives bare verb inflections without the reflexive clitic pronoun).
PRONOMINAL_ONLY = {"souvenir"}
REFLEXIVE_PRONOUNS = ["me", "te", "se", "nous", "vous", "se"]
VOWEL_SOUND = set("aeiouyàâäéèêëïîôöùûü") | {"h"}  # elide me/te/se -> m'/t'/s'

def elide_clitic(pronoun, following_word):
    if pronoun in ("me", "te", "se") and following_word and following_word[0].lower() in VOWEL_SOUND:
        return pronoun[0] + "'" + following_word
    return pronoun + " " + following_word

def build_conjugation_entry(lemma, table):
    pronominal = lemma in PRONOMINAL_ONLY
    aux = "etre" if (pronominal or lemma in LIST_ETRE) else "avoir"
    aux_present = conj["être" if aux == "etre" else "avoir"]["P"]
    participe = table.get("K", [None])[0]
    passe_compose = None
    if participe and participe != "NA":
        if pronominal:
            passe_compose = [f"{elide_clitic(p, a)} {participe}" for p, a in zip(REFLEXIVE_PRONOUNS, aux_present)]
        else:
            passe_compose = [f"{a} {participe}" for a in aux_present]

    def get(key):
        v = table.get(key)
        if not v:
            return None
        return [x if x != "NA" else None for x in v]

    return {
        "infinitive": lemma,
        "display_infinitive": ("se " + lemma) if pronominal else lemma,
        "pronominal": pronominal,
        "reflexive_pronouns": REFLEXIVE_PRONOUNS if pronominal else None,
        "aux": aux,
        "present": get("P"),
        "imparfait": get("I"),
        "futur_simple": get("F"),
        "passe_simple": get("J"),
        "conditionnel_present": get("C"),
        "subjonctif_present": get("S"),
        "subjonctif_imparfait": get("T"),
        "imperatif": get("Y"),
        "participe_passe": participe,
        "participe_present": (table.get("G") or [None])[0],
        "passe_compose": passe_compose,
    }

def true_total_frequency(lemma):
    # Now that the verb is confirmed legitimate (passed the collision-resistant
    # selection above), sum ALL its inflected forms' real corpus frequency to get
    # an actual usage-frequency figure -- used only to interleave verbs with plain
    # vocab in the app's new-card introduction order, not for selection.
    table = conj[lemma]
    forms = set()
    for k in TENSE_KEYS:
        for v in (table.get(k) or []):
            if v and v != "NA":
                forms.add(v.lower())
    forms.add(lemma.lower())
    return sum(freq_lookup.get(f, 0) for f in forms)

verbs_out = []
for lemma, freq, g in top_verbs:
    entry = build_conjugation_entry(lemma, conj[lemma])
    entry["frequency_rank_basis"] = freq
    entry["true_frequency"] = true_total_frequency(lemma)
    entry["gloss"] = g[:5]
    entry["gloss_source"] = gloss_source.get(lemma, "?")
    verbs_out.append(entry)

json.dump(verbs_out, open(f"{DATA}/../out/verbs.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

# ---------- 9. Emit vocab.json ----------
vocab_out = []
for w, freq, g in vocab_list:
    vocab_out.append({
        "word": w,
        "gloss": g[:5],
        "gloss_source": gloss_source.get(w, "?"),
        "frequency": freq,
    })

json.dump(vocab_out, open(f"{DATA}/../out/vocab.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

print(f"[done] wrote {len(verbs_out)} verbs, {len(vocab_out)} vocab words", file=sys.stderr)

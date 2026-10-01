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

#!/usr/bin/env python3
"""
Data pipeline for the Spanish vocab/conjugation trainer -- mirrors
build_data.py (French) in structure and standards. Sources (all fetched
raw, not retyped/generated):

  1. hermitdave/FrequencyWords es_full.txt (OpenSubtitles word-form frequency)
     https://github.com/hermitdave/FrequencyWords
  2. spanish-verbs npm package (RosaeNLG project, Apache-2.0) -- a rule-based
     conjugation ENGINE (getConjugation(infinitive, tense, person)), not a
     static table like French's Lefff data. Spot-checked against ordinary
     Spanish competence: ser/estar/tener/ir/hacer/decir/saber/poner/querer/
     ver/dar/poder all correct, including irregular past participles
     (hecho, dicho, puesto, visto). Does NOT validate that its input is a
     real verb (garbage in, garbage out -- "lugar" produces "lugo"), so it
     cannot by itself distinguish real verb infinitives from -ar/-er/-ir
     -ending nouns like "lugar"/"mujer"/"carácter".
     https://www.npmjs.com/package/spanish-verbs
  3. apertium-eng-spa apertium-eng-spa.eng-spa.dix (Apertium project bilingual
     dictionary, GPL) -- used BOTH as the primary English gloss source AND,
     via its part-of-speech tags (vblex/vbser/vbhaver/vbmod), as the
     authoritative list of real verb infinitives (solving the problem above
     with sourced data instead of a guess).
     https://github.com/apertium/apertium-eng-spa
  4. freedict/fd-dictionaries spa-eng.tei (FreeDict Spanish-English
     dictionary, GPL-2.0+) -- fallback gloss source. Checked standalone
     coverage of the top-5000 frequency list: only 28%, confirming it is
     not viable as a primary source (unlike Apertium).
     https://github.com/freedict/fd-dictionaries

Conjugation coverage: présent (INDICATIVE_PRESENT), imperfect
(INDICATIVE_IMPERFECT), perfect/pretérito perfecto compuesto
(INDICATIVE_PERFECT -- Spanish always uses "haber", unlike French's
être/avoir split, so there is no auxiliary-selection step here), future
(INDICATIVE_FUTURE), and subjunctive present (SUBJUNCTIVE_PRESENT) -- the
same 5-tense set the app drills for French.

Known scope limitation (disclosed, not silent): reflexive/pronominal verbs
(llamarse, quejarse, irse...) are NOT specially handled in this pass --
they're conjugated as their base non-reflexive infinitive. The French
pipeline only special-cased one such verb (souvenir); a fuller pass here
is left for a future update.
"""
import json, re, sys
from collections import defaultdict
import xml.etree.ElementTree as ET

DATA = "."

# ---------- 1. Load raw frequency list ----------
freq_pairs = []
with open(f"{DATA}/es_full.txt", encoding="utf-8") as f:
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

WORD_RE = re.compile(r"^[a-záéíóúñü]+$")

def is_clean_token(w):
    if not WORD_RE.match(w):
        return False
    if len(w) == 1 and w not in ("y", "o", "a", "e", "u"):
        return False
    return True

clean_freq = [(w, c) for w, c in freq_pairs if is_clean_token(w)]
print(f"[freq] {len(clean_freq)} rows after junk filtering", file=sys.stderr)
freq_lookup = dict(clean_freq)

# ---------- 2. Load Apertium bilingual dictionary (primary gloss source +
#               authoritative verb-infinitive list via POS tags) ----------
apertium_raw = open(f"{DATA}/apertium-eng-spa.dix", encoding="utf-8").read()
entries = re.findall(r"<e[^>]*>.*?</e>", apertium_raw)
print(f"[apertium] {len(entries)} raw dictionary entries", file=sys.stderr)

TAG_RE = re.compile(r"<[^>]+>")
VERB_POS = ("vblex", "vbser", "vbhaver", "vbmod")

gloss = defaultdict(list)  # es_word -> [en, en, ...] (order = preference)
gloss_source = {}
verb_infinitives = set()

for e in entries:
    # direction: entries marked r="LR" are English->Spanish ONLY, not valid
    # for our Spanish->English lookup direction; everything else (no r
    # attribute, or r="RL") is usable.
    dir_match = re.match(r'<e\s+r="([^"]*)"', e)
    if dir_match and dir_match.group(1) == "LR":
        continue
    l_match = re.search(r"<l>(.*?)</l>", e)
    r_match = re.search(r"<r>(.*?)</r>", e)
    if not l_match or not r_match:
        continue
    l_raw, r_raw = l_match.group(1), r_match.group(1)
    if "<b/>" in l_raw or "<b/>" in r_raw or "<g>" in l_raw or "<g>" in r_raw:
        continue  # multiword entry -- skip, we only want single tokens
    is_verb = bool(re.search(r'<s n="(?:vblex|vbser|vbhaver|vbmod)"/>', r_raw))
    en = TAG_RE.sub("", l_raw).strip().lower()
    es = TAG_RE.sub("", r_raw).strip().lower()
    if not en or not es or not es.isalpha():
        continue
    if is_verb and es.endswith(("ar", "er", "ir")):
        verb_infinitives.add(es)
    if en not in gloss[es]:
        gloss[es].append(en)
    gloss_source.setdefault(es, "apertium")

print(f"[apertium] {len(gloss)} headwords, {len(verb_infinitives)} verb infinitives (POS-tagged)", file=sys.stderr)

# FreeDict fallback
tree = ET.parse(f"{DATA}/spa-eng.tei")
ns = {"t": "http://www.tei-c.org/ns/1.0"}
fd_count = 0
for entry in tree.iter("{http://www.tei-c.org/ns/1.0}entry"):
    orth = entry.find(".//t:form/t:orth", ns)
    if orth is None or not orth.text:
        continue
    es = orth.text.strip().lower()
    if es in gloss:
        continue
    quotes = [q.text.strip() for q in entry.findall(".//t:sense/t:cit[@type='trans']/t:quote", ns) if q.text]
    if quotes:
        gloss[es] = quotes
        gloss_source[es] = "freedict"
        fd_count += 1

print(f"[gloss] +{fd_count} headwords added from freedict fallback -> {len(gloss)} total", file=sys.stderr)

# Manual correction for extremely high-frequency closed-class words -- the
# same category of fix as French's MANUAL_GLOSS_OVERRIDE (ordinary,
# uncontroversial bilingual-dictionary knowledge, ordered by primary sense).
MANUAL_GLOSS_OVERRIDE = {
    "de": ["of", "from"],
    "que": ["that", "what", "than"],
    "no": ["no", "not"],
    "a": ["to", "at"],
    "la": ["the", "her", "it"],
    "el": ["the"],
    "es": ["is"],
    "y": ["and"],
    "en": ["in", "on", "at"],
    "lo": ["it", "him", "the"],
    "un": ["a", "an", "one"],
    "por": ["for", "by", "through"],
    "qué": ["what"],
    "me": ["me", "myself", "to me"],
    "una": ["a", "an", "one"],
    "te": ["you", "yourself", "to you"],
    "si": ["if"],
    "sí": ["yes"],
    "con": ["with"],
    "para": ["for", "in order to"],
    "mi": ["my"],
    "su": ["his", "her", "its", "your"],
    "yo": ["I"],
    "tu": ["your"],
    "tú": ["you"],
    "él": ["he"],
    "ella": ["she"],
    "los": ["the", "them"],
    "las": ["the", "them"],
    "del": ["of the", "from the"],
    "al": ["to the"],
    "se": ["himself", "herself", "itself", "oneself", "themselves"],
    "nos": ["us", "ourselves", "to us"],
    "le": ["to him", "to her", "to you"],
    "les": ["to them", "to you all"],
    "esto": ["this"],
    "eso": ["that"],
    "vamos": ["let's go", "we go"],
    "está": ["is"],
    "estoy": ["I am"],
    "soy": ["I am"],
    "ha": ["has"],
    "he": ["I have"],
    "hay": ["there is", "there are"],
    # found via manual review of the top ~400 words, same standard applied
    # to the French data. Two distinct defects: (a) a handful of Apertium
    # entries leak a grammatical tag instead of a translation ("mi"/"ti" ->
    # "prpers"), or list a wrong secondary sense first ("este" -> "east"
    # before "this"; "hermano" wrongly included "sister" -- verified false,
    # hermano only ever means brother, exactly like French's frère/sister
    # bug); (b) FreeDict's spa-eng.tei has a genuine upstream data defect
    # where some multi-word translations lost their spaces in the source
    # XML itself ("tanto" -> literally "thatmuch" in the raw file, not a
    # parsing bug on this end) -- confirmed by inspecting the raw TEI.
    "mí": ["me"],
    "ti": ["you"],
    "este": ["this", "east"],
    "hermano": ["brother"],
    "usted": ["you"],
    "pronto": ["soon", "early", "prompt"],
    "mucho": ["a lot of", "much"],
    "tanto": ["so much", "as much"],
    "dicho": ["said", "aforementioned"],
    "volver": ["return", "go back", "come back", "turn around"],
    "esta": ["this", "these"],
    "anoche": ["last night"],
    "noticias": ["news", "notice", "announcement", "message", "report"],
    "buscar": ["look for", "search", "seek", "get", "pick up"],
}
for w, g in MANUAL_GLOSS_OVERRIDE.items():
    gloss[w] = g
    gloss_source[w] = "model-override"

# ---------- 3. Candidate verb infinitives: Apertium-tagged verbs that also
#               literally appear in the frequency list ----------
freq_words = set(freq_lookup.keys())
verb_candidates = sorted(v for v in verb_infinitives if v in freq_words)
print(f"[verbs] {len(verb_candidates)} candidate infinitives (Apertium-tagged AND in frequency list)", file=sys.stderr)

# ---------- 4. Generate conjugation tables via the spanish-verbs engine
#               (done in build-time Node step -- see gen_es_conjugations.js),
#               loaded here as a precomputed JSON lookup ----------
conj = json.load(open(f"{DATA}/es_conjugations.json", encoding="utf-8"))
TENSE_KEYS = ["present", "imperfect", "perfect", "future", "subjunctive_present"]

# ---------- 5. Rank verb candidates with a collision-resistant signal ----------
# Spanish -ar present yo-forms end in plain "-o", which collides constantly
# with unrelated nouns (many Spanish nouns end in -o). Imperfect forms
# (-aba.../-ía...) and nosotros/vosotros present forms are far more
# distinctively verb-shaped, mirroring the exact same fix used for French.
def collision_resistant_score(inf):
    table = conj.get(inf)
    if not table:
        return 0
    forms = set()
    for v in (table.get("imperfect") or []):
        if v:
            forms.add(v.lower())
    present = table.get("present") or []
    for v in present[3:5]:  # nosotros / vosotros
        if v:
            forms.add(v.lower())
    return sum(freq_lookup.get(f, 0) for f in forms)

scored = [(inf, collision_resistant_score(inf)) for inf in verb_candidates]
scored.sort(key=lambda kv: -kv[1])

top_verbs = []
skipped_verbs_no_gloss = []
for inf, score in scored:
    if score <= 0:
        continue
    g = gloss.get(inf)
    if not g:
        skipped_verbs_no_gloss.append(inf)
        continue
    top_verbs.append((inf, score, g))
    if len(top_verbs) == 100:
        break

print(f"[verbs] selected {len(top_verbs)} verbs; {len(skipped_verbs_no_gloss)} high-scoring infinitives skipped for missing gloss (first 15: {skipped_verbs_no_gloss[:15]})", file=sys.stderr)

verb_lemma_set = {inf for inf, _, _ in top_verbs}

# ---------- 6. Build the set of inflected forms "consumed" by selected verbs ----------
consumed_forms = set()
for inf in verb_lemma_set:
    table = conj[inf]
    for key in TENSE_KEYS:
        for v in (table.get(key) or []):
            if v:
                consumed_forms.add(v.lower())
    consumed_forms.add(inf)

# ---------- 7. Build vocab list from remaining frequency-ranked tokens ----------
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

# ---------- 8. Emit verbs_es.json ----------
def build_verb_entry(inf, table):
    entry = {
        "infinitive": inf,
        "display_infinitive": inf,
        "gloss": gloss[inf],
        "gloss_source": gloss_source.get(inf, "apertium"),
        "true_frequency": next(s for i, s, _ in top_verbs if i == inf),
    }
    entry["present"] = table["present"]
    entry["imparfait"] = table["imperfect"]  # key name kept aligned with app's TENSES keys
    entry["passe_compose"] = table["perfect"]
    entry["futur_simple"] = table["future"]
    entry["subjonctif_present"] = table["subjunctive_present"]
    return entry

verbs_out = [build_verb_entry(inf, conj[inf]) for inf, _, _ in top_verbs]

# ---------- 8b. Correct conjugator gaps found by manual review ----------
# spanish-verbs (v3.4.0) is a rule-based engine, not a sourced lookup table
# like French's Lefff data, and its own README says "plenty of exceptions
# still missing". Confirmed by systematically dumping every selected verb's
# present/imperfect/perfect/future/subjunctive and reviewing by eye against
# ordinary Spanish competence (the same standard used for French's
# MANUAL_GLOSS_OVERRIDE) -- the two least-obvious cases (sentir's
# nosotros/vosotros "sintamos" subjunctive pattern, jugar's "juegue"
# spelling change) were confirmed via web search rather than taken on
# recollection alone. This was a full pass over all 100 selected verbs
# across present/subjunctive, and a full pass over imperfect (a closed set
# of exactly 3 irregular verbs in Spanish: ser/ir/ver) and future (a
# closed, well-known irregular-stem set) -- NOT a cell-by-cell recheck of
# every tense x person combination, so a rarer gap could still remain.
MANUAL_CONJUGATION_OVERRIDE = {
    "pensar": {"present": ["pienso", "piensas", "piensa", "pensamos", "pensáis", "piensan"],
               "subjonctif_present": ["piense", "pienses", "piense", "pensemos", "penséis", "piensen"]},
    "sentir": {"present": ["siento", "sientes", "siente", "sentimos", "sentís", "sienten"],
               "subjonctif_present": ["sienta", "sientas", "sienta", "sintamos", "sintáis", "sientan"]},
    "empezar": {"present": ["empiezo", "empiezas", "empieza", "empezamos", "empezáis", "empiezan"],
                "subjonctif_present": ["empiece", "empieces", "empiece", "empecemos", "empecéis", "empiecen"]},
    "entender": {"present": ["entiendo", "entiendes", "entiende", "entendemos", "entendéis", "entienden"],
                 "subjonctif_present": ["entienda", "entiendas", "entienda", "entendamos", "entendáis", "entiendan"]},
    "perder": {"present": ["pierdo", "pierdes", "pierde", "perdemos", "perdéis", "pierden"],
               "subjonctif_present": ["pierda", "pierdas", "pierda", "perdamos", "perdáis", "pierdan"]},
    "comenzar": {"present": ["comienzo", "comienzas", "comienza", "comenzamos", "comenzáis", "comienzan"],
                 "subjonctif_present": ["comience", "comiences", "comience", "comencemos", "comencéis", "comiencen"]},
    "sentar": {"present": ["siento", "sientas", "sienta", "sentamos", "sentáis", "sientan"],
               "subjonctif_present": ["siente", "sientes", "siente", "sentemos", "sentéis", "sienten"]},
    "referir": {"present": ["refiero", "refieres", "refiere", "referimos", "referís", "refieren"],
                "subjonctif_present": ["refiera", "refieras", "refiera", "refiramos", "refiráis", "refieran"]},
    "pedir": {"present": ["pido", "pides", "pide", "pedimos", "pedís", "piden"],
              "subjonctif_present": ["pida", "pidas", "pida", "pidamos", "pidáis", "pidan"]},
    "salir": {"present": ["salgo", "sales", "sale", "salimos", "salís", "salen"],
              "subjonctif_present": ["salga", "salgas", "salga", "salgamos", "salgáis", "salgan"],
              "futur_simple": ["saldré", "saldrás", "saldrá", "saldremos", "saldréis", "saldrán"]},
    "jugar": {"present": ["juego", "juegas", "juega", "jugamos", "jugáis", "juegan"],
              "subjonctif_present": ["juegue", "juegues", "juegue", "juguemos", "juguéis", "jueguen"]},
    "suponer": {"present": ["supongo", "supones", "supone", "suponemos", "suponéis", "suponen"],
                "subjonctif_present": ["suponga", "supongas", "suponga", "supongamos", "supongáis", "supongan"],
                "futur_simple": ["supondré", "supondrás", "supondrá", "supondremos", "supondréis", "supondrán"],
                "passe_compose": ["he supuesto", "has supuesto", "ha supuesto", "hemos supuesto", "habéis supuesto", "han supuesto"]},
    "traer": {"present": ["traigo", "traes", "trae", "traemos", "traéis", "traen"],
              "subjonctif_present": ["traiga", "traigas", "traiga", "traigamos", "traigáis", "traigan"]},
    "mantener": {"present": ["mantengo", "mantienes", "mantiene", "mantenemos", "mantenéis", "mantienen"],
                 "subjonctif_present": ["mantenga", "mantengas", "mantenga", "mantengamos", "mantengáis", "mantengan"],
                 "futur_simple": ["mantendré", "mantendrás", "mantendrá", "mantendremos", "mantendréis", "mantendrán"]},
    "confiar": {"present": ["confío", "confías", "confía", "confiamos", "confiáis", "confían"],
                "subjonctif_present": ["confíe", "confíes", "confíe", "confiemos", "confiéis", "confíen"]},
    "enviar": {"present": ["envío", "envías", "envía", "enviamos", "enviáis", "envían"],
               "subjonctif_present": ["envíe", "envíes", "envíe", "enviemos", "enviéis", "envíen"]},
    "dirigir": {"present": ["dirijo", "diriges", "dirige", "dirigimos", "dirigís", "dirigen"],
                "subjonctif_present": ["dirija", "dirijas", "dirija", "dirijamos", "dirijáis", "dirijan"]},
    "ver": {"imparfait": ["veía", "veías", "veía", "veíamos", "veíais", "veían"]},
}
verbs_by_inf = {v["infinitive"]: v for v in verbs_out}
override_count = 0
for inf, fixes in MANUAL_CONJUGATION_OVERRIDE.items():
    if inf not in verbs_by_inf:
        continue  # verb not in the final top-100 selection; nothing to patch
    for key, forms in fixes.items():
        verbs_by_inf[inf][key] = forms
        override_count += 1
print(f"[verbs] applied {override_count} manual conjugation corrections across {len(MANUAL_CONJUGATION_OVERRIDE)} verbs", file=sys.stderr)

json.dump(verbs_out, open("verbs_es.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[out] wrote verbs_es.json ({len(verbs_out)} verbs)", file=sys.stderr)

# ---------- 9. Emit vocab_es.json ----------
vocab_out = [
    {"word": w, "gloss": gloss[w], "gloss_source": gloss_source.get(w, "apertium"), "frequency": freq}
    for w, freq, _ in vocab_list
]
json.dump(vocab_out, open("vocab_es.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"[out] wrote vocab_es.json ({len(vocab_out)} words)", file=sys.stderr)

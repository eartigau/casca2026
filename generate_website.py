#!/usr/bin/env python3
"""
generate_website.py — Regenerate CASCA 2026 website JSON files from Overleaf LaTeX.



Usage:
    python3 generate_website.py

Reads:  overleaf/sections/generated_schedule.tex
        overleaf/sections/generated_abstracts.tex
        overleaf/sections/generated_posters_abstracts.tex
        overleaf/sections/generated_participants.tex
Writes: website/schedule.json
        website/posters.json
"""

import json
import re
import sys
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
SECTIONS = BASE / 'overleaf' / 'sections'
OUT = BASE / 'website'

# ─── Field translations (EN → FR) ─────────────────────────────────────────────
FIELD_FR = {
    'Astrostatistics, Astroinformatics, and AI / Machine Learning':
        'Astrostatistiques, astroinformatique et IA/apprentissage automatique',
    'Astrostatistics, Astroinformatics, and AI/Machine Learning':
        'Astrostatistiques, astroinformatique et IA/apprentissage automatique',
    'Compact Objects': 'Objets compacts',
    'Cosmology and Early Universe': 'Cosmologie et univers primitif',
    'Education and Public Outreach': 'Éducation et communication avec le public',
    'Equity, Diversity and Inclusion': 'Équité, diversité et inclusion',
    'Exoplanets': 'Exoplanètes',
    'Galaxy': 'Galaxie',
    'Galaxy Clusters': 'Amas de galaxies',
    'Gas, dust and the ISM': 'Gaz, poussière et le milieu interstellaire',
    'Gravitational waves': 'Ondes gravitationnelles',
    'High Energy Astrophysics': 'Astrophysique des hautes énergies',
    'Indigenous Engagement': 'Engagement avec les Premiers Peuples',
    'Instrumentation': 'Instrumentation',
    'Local Group': 'Groupe local',
    'Night-Sky Protection': 'Protection du ciel nocturne',
    'Night-Sky Protection / Solar System': 'Protection du ciel nocturne / Système solaire',
    'Next generation observatories': 'Observatoires de nouvelle génération',
    'Solar System': 'Système solaire',
    'Stars and Stellar cluster formation': "Étoiles et formation d'amas stellaires",
    'Supermassive black hole': 'Trou noir supermassif',
    'Supernova remnant': 'Rémanent de supernova',
    'Transients': 'Phénomènes transitoires',
}

DAY_FR   = {'Tuesday': 'Mardi',    'Wednesday': 'Mercredi', 'Thursday': 'Jeudi'}
DAY_SLUG = {'Tuesday': 'mardi',    'Wednesday': 'mercredi', 'Thursday': 'jeudi'}

NAME_PREFIXES = frozenset({
    'da', 'de', 'den', 'der', 'van', 'von', 'le', 'la', 'du',
    'des', 'di', 'del', 'dos', 'el', 'al', 'bin', 'binti',
})

# ─── Greek / math symbol tables ───────────────────────────────────────────────
GREEK = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε',
    'varepsilon': 'ε', 'zeta': 'ζ', 'eta': 'η', 'theta': 'θ', 'vartheta': 'θ',
    'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν',
    'xi': 'ξ', 'pi': 'π', 'varpi': 'π', 'rho': 'ρ', 'varrho': 'ρ',
    'sigma': 'σ', 'varsigma': 'ς', 'tau': 'τ', 'upsilon': 'υ',
    'phi': 'φ', 'varphi': 'φ', 'chi': 'χ', 'psi': 'ψ', 'omega': 'ω',
    'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ',
    'Pi': 'Π', 'Sigma': 'Σ', 'Upsilon': 'Υ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω',
}

MATH_SYM = {
    'cdot': '·', 'cdots': '···', 'ldots': '...', 'times': '×', 'div': '÷',
    'pm': '±', 'mp': '∓', 'sim': '~', 'approx': '≈', 'simeq': '≃',
    'cong': '≅', 'leq': '≤', 'geq': '≥', 'neq': '≠', 'll': '≪', 'gg': '≫',
    'lesssim': '≲', 'gtrsim': '≳', 'infty': '∞',
    'rightarrow': '→', 'leftarrow': '←', 'Rightarrow': '⇒', 'Leftarrow': '⇐',
    'leftrightarrow': '↔', 'to': '→', 'gets': '←',
    'nabla': '∇', 'partial': '∂', 'propto': '∝',
    'in': '∈', 'notin': '∉', 'subset': '⊂', 'supset': '⊃',
    'cup': '∪', 'cap': '∩', 'circ': '∘',
    'prime': '′', 'odot': '⊙', 'otimes': '⊗', 'oplus': '⊕',
    'perp': '⊥', 'parallel': '∥', 'angle': '∠',
    'langle': '⟨', 'rangle': '⟩',
    'sum': 'Σ', 'prod': 'Π', 'int': '∫',
    'sqrt': '√',
}

# ─── LaTeX cleaner ────────────────────────────────────────────────────────────

def clean_latex(text: str) -> str:
    """Convert common LaTeX markup to plain Unicode text."""
    if not text:
        return ''

    # Remove % comments (lines starting with %)
    text = re.sub(r'(?m)^%[^\n]*\n?', '', text)
    text = re.sub(r'(?<!\\)%[^\n]*', '', text)

    # Accented characters — brace form first: \'{e} \`{a} etc.
    def _accent(letter, style):
        maps = {
            "'":  {'a':'á','e':'é','i':'í','o':'ó','u':'ú','y':'ý',
                   'A':'Á','E':'É','I':'Í','O':'Ó','U':'Ú','Y':'Ý'},
            '`':  {'a':'à','e':'è','i':'ì','o':'ò','u':'ù',
                   'A':'À','E':'È','I':'Ì','O':'Ò','U':'Ù'},
            '"':  {'a':'ä','e':'ë','i':'ï','o':'ö','u':'ü','y':'ÿ',
                   'A':'Ä','E':'Ë','I':'Ï','O':'Ö','U':'Ü'},
            '^':  {'a':'â','e':'ê','i':'î','o':'ô','u':'û',
                   'A':'Â','E':'Ê','I':'Î','O':'Ô','U':'Û'},
            '~':  {'n':'ñ','N':'Ñ','a':'ã','A':'Ã','o':'õ','O':'Õ'},
            'v':  {'c':'č','C':'Č','s':'š','S':'Š','z':'ž','Z':'Ž'},
        }
        return maps.get(style, {}).get(letter, letter)

    for style in ("'", '`', '"', r'\^', r'\~', r'v'):
        esc = re.escape(style)
        text = re.sub(r'\\' + esc + r'\{([a-zA-Z])\}',
                      lambda m, s=style: _accent(m.group(1), s.lstrip('\\')), text)
        text = re.sub(r'\\' + esc + r'([a-zA-Z])',
                      lambda m, s=style: _accent(m.group(1), s.lstrip('\\')), text)

    # Cedilla
    text = re.sub(r'\\c\{([cCsStT])\}', lambda m: {'c':'ç','C':'Ç','s':'ş','S':'Ş','t':'ţ','T':'Ţ'}.get(m.group(1), m.group(1)), text)
    text = re.sub(r'\\c ([cC])', lambda m: 'ç' if m.group(1)=='c' else 'Ç', text)

    # Ligatures
    text = text.replace('\\oe{}', 'œ').replace('\\OE{}', 'Œ')
    text = text.replace('\\ae{}', 'æ').replace('\\AE{}', 'Æ')
    text = text.replace('\\aa{}', 'å').replace('\\AA{}', 'Å')
    text = text.replace('\\o{}', 'ø').replace('\\O{}', 'Ø')
    text = text.replace('\\ss{}', 'ß')
    text = text.replace('\\oe', 'œ').replace('\\OE', 'Œ')
    text = text.replace('\\ae', 'æ').replace('\\AE', 'Æ')
    text = text.replace('\\aa', 'å').replace('\\AA', 'Å')

    # emdash / endash
    text = text.replace('\\textemdash', '—').replace('\\textendash', '–')
    text = text.replace('---', '—').replace('--', '–')

    # Greek letters in math: $\alpha$ → α  (also bare \alpha)
    for name, sym in GREEK.items():
        text = re.sub(r'\$\\' + name + r'(?![a-zA-Z])\$', sym, text)
        text = re.sub(r'(?<!\w)\\' + name + r'(?![a-zA-Z])', sym, text)

    # Math symbols: $\cdot$ → ·  etc.
    for name, sym in MATH_SYM.items():
        text = re.sub(r'\$\\' + name + r'(?![a-zA-Z])\$', sym, text)
        text = re.sub(r'(?<!\w)\\' + name + r'(?![a-zA-Z])', sym, text)

    # Subscript / superscript in math — strip $ and _ ^ markers
    text = re.sub(r'\$([^$]*)\$', r'\1', text)   # remaining inline math
    text = re.sub(r'_\{([^}]+)\}', r'\1', text)
    text = re.sub(r'_([a-zA-Z0-9])', r'\1', text)
    text = re.sub(r'\^\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\^([a-zA-Z0-9])', r'\1', text)

    # Text formatting — keep content, strip command
    for cmd in ('textbf', 'textit', 'textrm', 'texttt', 'textsc', 'textsf',
                'textsl', 'textup', 'textnormal', 'emph',
                'footnotesize', 'small', 'large', 'Large', 'huge', 'Huge',
                'normalsize', 'scriptsize', 'tiny'):
        # \cmd{...} with possibly nested braces one level deep
        text = re.sub(r'\\' + cmd + r'\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'\1', text)
        text = re.sub(r'\{\\' + cmd + r'\s+([^{}]*)\}', r'\1', text)

    # Group font switches like {\bfseries ...} {\sffamily ...}
    for sw in ('bfseries', 'itshape', 'sffamily', 'rmfamily', 'ttfamily',
               'scshape', 'normalfont', 'upshape', 'slshape'):
        text = re.sub(r'\{\\' + sw + r'\s+([^{}]*)\}', r'\1', text)
        text = re.sub(r'\\' + sw + r'(?![a-zA-Z])\s*', '', text)

    # Color commands
    text = re.sub(r'\\color\{[^}]+\}', '', text)
    text = re.sub(r'\\textcolor\{[^}]+\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', r'\1', text)
    text = re.sub(r'\{\\color\{[^}]+\}([^{}]*)\}', r'\1', text)

    # Hyperlink / ref commands — keep display text
    text = re.sub(r'\\hyperlink\{[^}]+\}\{([^{}]+)\}', r'\1', text)
    text = re.sub(r'\\hyperref\[[^\]]+\]\{([^{}]+)\}', r'\1', text)
    text = re.sub(r'\\href\{[^}]+\}\{([^{}]+)\}', r'\1', text)
    text = re.sub(r'\\ref\{[^}]+\}', '', text)
    text = re.sub(r'\\label\{[^}]+\}', '', text)
    text = re.sub(r'\\hypertarget\{[^}]+\}\{[^}]*\}', '', text)
    text = re.sub(r'\\addcontentsline\{[^}]+\}\{[^}]+\}\{[^}]+\}', '', text)

    # Footnotes
    text = re.sub(r'\\footnote\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', '', text)

    # Special characters
    for old, new in [('\\%', '%'), ('\\&', '&'), ('\\$', '$'), ('\\_', '_'),
                     ('\\#', '#'), ('\\{', '{'), ('\\}', '}'), ('\\~{}', '~'),
                     ('\\,', ' '), ('\\;', ' '), ('\\:', ' '), ('\\!', ''),
                     ('\\/', ''), ('\\.', ''), ('\\-', '')]:
        text = text.replace(old, new)

    # Quotes
    text = text.replace('``', '"').replace("''", '"').replace('`', "'")

    # Non-breaking tilde (not already a math ~)
    text = re.sub(r'(?<![\\])~', ' ', text)

    # Line breaks
    text = re.sub(r'\\\\', '\n', text)
    text = text.replace('\\newline', '\n').replace('\\par', '\n\n')

    # Remove remaining known LaTeX commands (no content to keep)
    for cmd in ('programdayheader', 'daypalettebanner', 'programchapter',
                'toprule', 'midrule', 'bottomrule', 'endfirsthead', 'endhead',
                'hbadness', 'sloppy', 'RaggedRight', 'arraybackslash',
                'TableRaggedRight', 'hspace', 'vspace', 'noindent',
                'raggedright', 'centering', 'setlength', 'setstretch'):
        text = re.sub(r'\\' + cmd + r'(?:\[[^\]]*\])?(?:\{[^{}]*\})?', '', text)

    # \cmd{arg} generically — removes anything left
    text = re.sub(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{[^{}]*\}', '', text)
    # Bare \cmd
    text = re.sub(r'\\[a-zA-Z]+\*?\s*', '', text)

    # Remove stray braces
    text = re.sub(r'[{}]', '', text)

    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


# ─── Field formatting ─────────────────────────────────────────────────────────

def format_fields(raw: str) -> str:
    """Convert LaTeX field string to bilingual ';'-separated JSON format."""
    # split on $\cdot$ or · (already cleaned)
    parts = re.split(r'\$\\cdot\$|\$·\$|·|;', raw)
    result = []
    for part in parts:
        en = clean_latex(part).strip()
        # Normalize spaces around /
        en = re.sub(r'\s*/\s*', ' / ', en)
        if not en:
            continue
        fr = FIELD_FR.get(en)
        if fr is None:
            # case-insensitive fallback
            for key, val in FIELD_FR.items():
                if key.lower() == en.lower():
                    en, fr = key, val
                    break
        if fr:
            result.append(f'{en} - {fr}')
        else:
            result.append(en)
    return ';'.join(result)


# ─── Name helpers ─────────────────────────────────────────────────────────────

def load_name_lookup(participants_path: Path) -> dict:
    """Parse participants.tex → {normalized_full: (first, last)}."""
    lookup = {}
    try:
        text = participants_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return lookup
    for m in re.finditer(r'\\textbf\{([^,}]+),\s*([^}]+)\}', text):
        last  = clean_latex(m.group(1)).strip()
        first = clean_latex(m.group(2)).strip()
        key = f'{first} {last}'.lower()
        lookup[key] = (first, last)
    return lookup


def split_name(full_name: str, lookup: dict | None = None) -> tuple[str, str]:
    """Split 'First [Middle] Last' into (first, last)."""
    full_name = full_name.strip()
    if lookup:
        key = full_name.lower()
        if key in lookup:
            return lookup[key]
    parts = full_name.split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return '', parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    # If penultimate token is a nobiliary particle, include it in last name
    if parts[-2].lower() in NAME_PREFIXES:
        return ' '.join(parts[:-2]), ' '.join(parts[-2:])
    # Default: first word = first name, rest = last name
    return parts[0], ' '.join(parts[1:])


# ─── Schedule parser ──────────────────────────────────────────────────────────

def parse_schedule(path: Path, lookup: dict | None = None) -> list[dict]:
    """
    Parse generated_schedule.tex.
    Returns list of session dicts with skeleton talk entries (id + speaker + title).
    Abstracts / fields are merged in later via build_schedule_json().
    """
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()

    sessions: list[dict] = []
    current_day: str | None   = None
    current_period: str | None = None
    session_rooms: list[dict] = []

    # Current room state
    room_name:             str | None  = None
    room_theme:            str | None  = None
    room_invited_speaker:  str | None  = None
    room_invited_minutes:  int | None  = None
    room_talks:            list[dict]  = []
    in_longtable: bool = False

    def save_room():
        nonlocal room_name, room_theme, room_invited_speaker, room_invited_minutes
        nonlocal room_talks, in_longtable
        if room_name is not None:
            session_rooms.append({
                'room':             room_name,
                'theme':            room_theme or '',
                'invited_speaker':  room_invited_speaker,
                'invited_title':    None,
                'invited_minutes':  room_invited_minutes,
                'talks':            list(room_talks),
            })
        room_name = None; room_theme = None
        room_invited_speaker = None; room_invited_minutes = None
        room_talks.clear(); in_longtable = False

    def save_session():
        if current_day and current_period and session_rooms:
            sessions.append({
                'day':     DAY_SLUG.get(current_day, current_day.lower()),
                'day_en':  current_day,
                'day_fr':  DAY_FR.get(current_day, current_day),
                'period':  current_period,
                'rooms':   list(session_rooms),
            })
        session_rooms.clear()

    for line in lines:
        s = line.strip()

        # Skip LaTeX comment lines
        if s.startswith('%'):
            continue

        # ── Day header (two possible forms) ────────────────────────────────
        # \programdayheader{Tuesday}  OR  \hypertarget{schedule-day-tuesday}{}
        m = re.match(r'\\programdayheader\{(\w+)\}', s)
        if not m:
            m2 = re.match(r'\\hypertarget\{schedule-day-(\w+)\}\{\}', s)
            if m2:
                # map slug back to title-case day name
                slug = m2.group(1).lower()
                DAY_FROM_SLUG = {v: k for k, v in DAY_SLUG.items()}
                day_name = DAY_FROM_SLUG.get(slug, slug.capitalize())
                save_room(); save_session()
                current_day = day_name; current_period = None
                continue
        if m:
            save_room(); save_session()
            current_day = m.group(1); current_period = None
            continue

        # ── Period ──────────────────────────────────────────────────────────
        m = re.match(r'\\section\*\{(Morning|Afternoon)\}', s)
        if m:
            save_room(); save_session()
            current_period = 'AM' if m.group(1) == 'Morning' else 'PM'
            continue

        # ── Room ────────────────────────────────────────────────────────────
        m = re.match(r'\\subsection\*\{([^}]+)\}', s)
        if m:
            save_room()
            room_name = m.group(1).strip()
            continue

        # ── Theme ───────────────────────────────────────────────────────────
        m = re.match(r'\\textbf\{Theme:\}', s)
        if m:
            raw = re.sub(r'^\\textbf\{Theme:\}\s*', '', s).rstrip('\\').strip()
            room_theme = clean_latex(raw)
            continue

        # ── Longtable boundaries ─────────────────────────────────────────────
        if r'\begin{longtable}' in s:
            in_longtable = True; continue
        if r'\end{longtable}' in s:
            in_longtable = False; continue
        if not in_longtable:
            continue

        # ── Skip table structural lines ──────────────────────────────────────
        if any(kw in s for kw in (r'\toprule', r'\midrule', r'\bottomrule',
                                   r'\endfirsthead', r'\endhead',
                                   'Speaker & Title', r'\addlinespace')):
            continue

        # ── Invited speaker line (ends with -sched}) ─────────────────────────
        if r'\hypertarget{invited-' in s and '-sched}' in s:
            # Name is in {\bfseries\color{cascagold}NAME}
            nm = re.search(r'\\color\{cascagold\}([^}]+)\}', s)
            if nm:
                room_invited_speaker = clean_latex(nm.group(1)).strip()
            mm = re.search(r'\(Invited,\s*(\d+)~?min\)', s)
            if mm:
                room_invited_minutes = int(mm.group(1))
            continue

        # ── Regular talk line ────────────────────────────────────────────────
        if r'\hypertarget{schedule-talk-' in s:
            id_m = re.search(r'\\hypertarget\{schedule-talk-([^}]+)\}', s)
            if not id_m:
                continue
            raw_id = id_m.group(1)

            # Strip all \hypertarget{}{} and \label{} constructs → leaves speaker & title
            clean_s = re.sub(r'\\hypertarget\{[^}]+\}\{[^}]*\}', '', s)
            clean_s = re.sub(r'\\label\{[^}]+\}', '', clean_s)

            parts = clean_s.split('&', 1)
            speaker_raw = clean_latex(parts[0]).strip() if parts else ''

            title_m = re.search(r'\\hyperlink\{[^}]+\}\{([^}]+)\}', s)
            title = clean_latex(title_m.group(1)).strip() if title_m else ''

            try:
                talk_id: int | str = int(raw_id)
            except ValueError:
                talk_id = raw_id   # keep as string (e.g. 'xx')

            room_talks.append({
                '_id':      talk_id,
                '_speaker': speaker_raw,
                '_title':   title,
            })

    # Final flush
    save_room(); save_session()
    return sessions


# ─── Abstracts parser ─────────────────────────────────────────────────────────

def parse_abstracts(path: Path, lookup: dict | None = None) -> dict:
    """
    Parse generated_abstracts.tex.
    Returns {talk_id: {title, first, last, field, abstract}}.
    talk_id is int when numeric, else str.
    """
    text = path.read_text(encoding='utf-8')

    # Split at each abstract entry boundary
    chunks = re.split(r'(?=\\hypertarget\{abstract-talk-)', text)
    abstracts: dict = {}

    for chunk in chunks:
        if '\\hypertarget{abstract-talk-' not in chunk:
            continue

        # ID
        id_m = re.match(r'\\hypertarget\{abstract-talk-([^}]+)\}', chunk)
        if not id_m:
            continue
        raw_id = id_m.group(1)

        # Title — \subsubsection*{...}
        title_m = re.search(r'\\subsubsection\*\{([^}]+)\}', chunk)
        title = clean_latex(title_m.group(1)).strip() if title_m else ''

        # Speaker — \textbf{Speaker:} NAME\\
        spk_m = re.search(r'\\textbf\{Speaker:\}\s*(.*?)(?:\\\\|$)', chunk)
        speaker_raw = clean_latex(spk_m.group(1)).strip() if spk_m else ''

        # Fields — \textbf{Field[s]:} ...  (may end at \\ or blank line)
        fld_m = re.search(r'\\textbf\{Fields?:\}\s*(.*?)(?=\n\n|\n\\[a-zA-Z]|\\\\|\Z)',
                          chunk, re.DOTALL)
        field_str = ''
        if fld_m:
            raw_fld = fld_m.group(1).rstrip('\\').strip()
            field_str = format_fields(raw_fld)

        # Abstract body — everything after the last header field up to end of chunk
        # Heuristic: find the last \textbf{...} header line, then take the rest
        body = _extract_abstract_body(chunk)

        try:
            tid: int | str = int(raw_id)
        except ValueError:
            tid = raw_id

        first, last = split_name(speaker_raw, lookup)

        abstracts[tid] = {
            'title':    title,
            'first':    first,
            'last':     last,
            'field':    field_str,
            'abstract': body,
        }

    return abstracts


def _extract_abstract_body(chunk: str) -> str:
    """Extract the abstract body text from an abstract chunk."""
    # Only match lines that are part of the abstract *entry header*,
    # not day-boundary markers (programdayheader etc.) that may appear at
    # the end of a chunk when a day boundary falls inside it.
    HEADER_PAT = re.compile(
        r'\\hypertarget\{|\\label\{|\\subsubsection\*\{|\\addcontentsline\{|'
        r'\\textbf\{Speaker:|\\textbf\{Fields?:|\\textbf\{Presenter:|'
        r'\\textbf\{Poster number:|\\section\*|\\subsection\*'
    )

    lines = chunk.splitlines()
    body_lines = []
    past_headers = False

    # Find the end of header section (last line containing a known header keyword)
    last_header_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('%'):
            continue
        if HEADER_PAT.search(stripped):
            last_header_idx = i

    # Body starts after the last header line (skip blank separator)
    start = last_header_idx + 1
    while start < len(lines) and not lines[start].strip():
        start += 1

    body_lines = [l for l in lines[start:] if not l.strip().startswith('%')]
    raw_body = '\n'.join(body_lines).strip()
    body = clean_latex(raw_body)

    # Collapse to a single paragraph (as the existing JSON does)
    body = re.sub(r'\s+', ' ', body).strip()
    return body


# ─── Poster abstracts parser ──────────────────────────────────────────────────

def parse_poster_abstracts(path: Path, lookup: dict | None = None) -> list[dict]:
    """
    Parse generated_posters_abstracts.tex.
    Returns list of poster dicts sorted by poster number.
    """
    text = path.read_text(encoding='utf-8')

    # Split at each poster entry boundary
    chunks = re.split(r'(?=\\hypertarget\{poster-abstract-talk-)', text)
    posters: list[dict] = []

    for chunk in chunks:
        if '\\hypertarget{poster-abstract-talk-' not in chunk:
            continue

        # ID
        id_m = re.match(r'\\hypertarget\{poster-abstract-talk-([^}]+)\}', chunk)
        if not id_m:
            continue
        raw_id = id_m.group(1)

        # Title — \subsection*{Poster N. TITLE}
        title_m = re.search(r'\\subsection\*\{Poster\s+\d+\.\s*(.*?)\}', chunk)
        if not title_m:
            title_m = re.search(r'\\subsection\*\{([^}]+)\}', chunk)
        title = clean_latex(title_m.group(1)).strip() if title_m else ''

        # Poster number
        num_m = re.search(r'\\textbf\{Poster number:\}\s*(\d+)', chunk)
        poster_num = int(num_m.group(1)) if num_m else None

        # Presenter
        pres_m = re.search(r'\\textbf\{Presenter:\}\s*(.*?)(?:\\\\|$)', chunk)
        presenter_raw = clean_latex(pres_m.group(1)).strip() if pres_m else ''

        # Fields
        fld_m = re.search(r'\\textbf\{Fields?:\}\s*(.*?)(?=\n\n|\n\\[a-zA-Z]|\\\\|\Z)',
                          chunk, re.DOTALL)
        field_str = ''
        if fld_m:
            field_str = format_fields(fld_m.group(1).rstrip('\\').strip())

        # Abstract body
        body = _extract_abstract_body(chunk)

        try:
            pid: int | str = int(raw_id)
        except ValueError:
            pid = raw_id

        first, last = split_name(presenter_raw, lookup)

        posters.append({
            '_id':         pid,
            '_poster_num': poster_num if poster_num is not None else (pid if isinstance(pid, int) else 9999),
            'id':          pid,
            'first':       first,
            'last':        last,
            'title':       title,
            'abstract':    body,
            'field':       field_str,
            'total_grade': None,
            'n_gradings':  0,
        })

    # Sort by poster number
    posters.sort(key=lambda p: p['_poster_num'])

    # Strip internal keys
    for p in posters:
        del p['_id']
        del p['_poster_num']

    return posters


# ─── JSON builder ─────────────────────────────────────────────────────────────

def build_schedule_json(sessions: list[dict], abstracts: dict,
                        lookup: dict | None = None) -> list[dict]:
    """Merge skeleton sessions with abstract data → final schedule.json format."""
    result = []
    for session in sessions:
        rooms_out = []
        for room in session['rooms']:
            talks_out = []
            for t in room['talks']:
                tid = t['_id']
                info = abstracts.get(tid, {})
                speaker = t['_speaker']
                first, last = split_name(speaker, lookup)
                # Prefer name from abstract file (more authoritative)
                if info.get('first'):
                    first = info['first']
                if info.get('last'):
                    last = info['last']
                talks_out.append({
                    'id':       tid,
                    'first':    first,
                    'last':     last,
                    'title':    info.get('title') or t['_title'],
                    'abstract': info.get('abstract', ''),
                    'field':    info.get('field', ''),
                })
            rooms_out.append({
                'room':            room['room'],
                'theme':           room['theme'],
                'invited_speaker': room['invited_speaker'],
                'invited_title':   room['invited_title'],
                'invited_minutes': room['invited_minutes'],
                'talks':           talks_out,
            })
        result.append({
            'day':    session['day'],
            'day_en': session['day_en'],
            'day_fr': session['day_fr'],
            'period': session['period'],
            'rooms':  rooms_out,
        })
    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print('Loading name lookup from participants file…')
    lookup = load_name_lookup(SECTIONS / 'generated_participants.tex')
    print(f'  {len(lookup)} names loaded.')

    print('Parsing oral schedule…')
    sessions = parse_schedule(SECTIONS / 'generated_schedule.tex', lookup)
    total_talks = sum(len(r['talks']) for s in sessions for r in s['rooms'])
    invited_rooms = sum(1 for s in sessions for r in s['rooms'] if r['invited_speaker'])
    print(f'  {len(sessions)} sessions, {total_talks} talks, {invited_rooms} invited-speaker rooms.')

    print('Parsing oral abstracts…')
    abstracts = parse_abstracts(SECTIONS / 'generated_abstracts.tex', lookup)
    print(f'  {len(abstracts)} abstracts loaded.')

    print('Building schedule.json…')
    schedule_data = build_schedule_json(sessions, abstracts, lookup)
    schedule_path = OUT / 'schedule.json'
    schedule_path.write_text(
        json.dumps(schedule_data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'  → {schedule_path}')

    print('Parsing poster abstracts…')
    posters = parse_poster_abstracts(SECTIONS / 'generated_posters_abstracts.tex', lookup)
    print(f'  {len(posters)} posters loaded.')

    posters_path = OUT / 'posters.json'
    posters_path.write_text(
        json.dumps(posters, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(f'  → {posters_path}')

    print('Done.')


if __name__ == '__main__':
    main()

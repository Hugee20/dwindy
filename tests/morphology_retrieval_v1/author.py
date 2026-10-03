"""One-time synthetic fixture authoring; refuses to overwrite a frozen evaluation.

No retrieval, ranking, scoring, model or network call is made by this script.
Cases were authored after reading M6-M8 failure reports. Holdout fixtures are
authored here, but their arm outputs must remain ungenerated until approval.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent

# Each tuple is (question, permitted source statement, answer span). Development
# and holdout use different topics/word families; this is not a paraphrase split.
POSITIVE = {
    'inflection': {
        'dev': [
            ('When are pumps inspected?', 'Pump inspection occurs every Tuesday.', 'every Tuesday'),
            ('Where are filters replaced?', 'Filter replacement happens at the violet depot.', 'the violet depot'),
            ('Who calibrates sensors?', 'Sensor calibration belongs to technician Mara.', 'technician Mara'),
            ('When are valves tested?', 'Valve testing begins at noon.', 'at noon'),
            ('Where are crates returned?', 'Crate return uses the east counter.', 'the east counter'),
            ('When are badges renewed?', 'Badge renewal takes place every April.', 'every April'),
        ],
        'holdout': [
            ('Where are drums cleaned?', 'Drum cleaning uses bay seventeen.', 'bay seventeen'),
            ('When are shutters closed?', 'Shutter closure occurs at sunset.', 'at sunset'),
            ('Who repairs motors?', 'Motor repair belongs to engineer Lio.', 'engineer Lio'),
            ('Where are cables connected?', 'Cable connection uses terminal violet.', 'terminal violet'),
            ('When are batteries charged?', 'Battery charging begins at dawn.', 'at dawn'),
            ('Where are invoices printed?', 'Invoice printing uses the north kiosk.', 'the north kiosk'),
        ],
    },
    'derivation': {
        'dev': [
            ('What is needed to approve documents?', 'Document approval requires a copper seal.', 'a copper seal'),
            ('What is needed to activate lockers?', 'Locker activation requires a green card.', 'a green card'),
            ('What is needed to adjust mirrors?', 'Mirror adjustment requires a brass key.', 'a brass key'),
            ('What is needed to attach panels?', 'Panel attachment requires a nylon clip.', 'a nylon clip'),
            ('What is needed to allocate parcels?', 'Parcel allocation requires a red ticket.', 'a red ticket'),
            ('What is needed to revise ledgers?', 'Ledger revision requires a signed note.', 'a signed note'),
        ],
        'holdout': [
            ('What is needed to organize seminars?', 'Seminar organization requires a purple permit.', 'a purple permit'),
            ('What is needed to coordinate ferries?', 'Ferry coordination requires a blue flag.', 'a blue flag'),
            ('What is needed to collect samples?', 'Sample collection requires a sterile jar.', 'a sterile jar'),
            ('What is needed to select fabrics?', 'Fabric selection requires a woven swatch.', 'a woven swatch'),
            ('What is needed to develop films?', 'Film development requires an amber tray.', 'an amber tray'),
            ('What is needed to rotate wheels?', 'Wheel rotation requires a torque wrench.', 'a torque wrench'),
        ],
    },
    'exact_identifier': {
        'dev': [
            ('Where is the pebble register?', 'The pebble register is in cabinet nine.', 'cabinet nine'),
            ('Who owns QUARTZ_BATCH?', 'QUARTZ_BATCH is owned by curator Una.', 'curator Una'),
            ('Where is src/pollen.py?', 'src/pollen.py is stored in the amber checkout.', 'the amber checkout'),
            ('When does the jade ferry leave?', 'The jade ferry leaves at 14:20.', '14:20'),
            ('What is spool_limit?', 'spool_limit is set to 37.', '37'),
            ('Which color marks the opal tag?', 'The opal tag is marked orange.', 'orange'),
        ],
        'holdout': [
            ('Where is the saffron ledger?', 'The saffron ledger is in drawer eleven.', 'drawer eleven'),
            ('Who owns BASALT_QUEUE?', 'BASALT_QUEUE is owned by archivist Teo.', 'archivist Teo'),
            ('Where is lib/coral.ts?', 'lib/coral.ts is stored in the bronze checkout.', 'the bronze checkout'),
            ('When does the silver shuttle leave?', 'The silver shuttle leaves at 08:35.', '08:35'),
            ('What is reed_timeout?', 'reed_timeout is set to 46.', '46'),
            ('Which color marks the mica token?', 'The mica token is marked indigo.', 'indigo'),
        ],
    },
    'synonym': {
        'dev': [
            ('Who can permit entry?', 'Access authorization belongs to steward Neri.', 'steward Neri'),
            ('Where can I purchase refreshments?', 'Beverage sales occur beside the copper fountain.', 'the copper fountain'),
            ('When does instruction commence?', 'Teaching begins at ten.', 'at ten'),
            ('Who mends footwear?', 'Shoe restoration belongs to artisan Bela.', 'artisan Bela'),
            ('Where are automobiles kept?', 'Cars occupy the underground garage.', 'the underground garage'),
            ('How long is the journey?', 'The trip lasts seventy minutes.', 'seventy minutes'),
        ],
        'holdout': [
            ('Who can forbid admittance?', 'Entrance prohibition belongs to marshal Omi.', 'marshal Omi'),
            ('Where can I obtain apparel?', 'Clothing distribution occurs beside the silver gate.', 'the silver gate'),
            ('When does labor cease?', 'Work ends at five.', 'at five'),
            ('Who constructs dwellings?', 'Home building belongs to mason Vela.', 'mason Vela'),
            ('Where are bicycles kept?', 'Cycles occupy the courtyard shelter.', 'the courtyard shelter'),
            ('How much does the remedy cost?', 'The medicine price is thirty credits.', 'thirty credits'),
        ],
    },
    'filipino_taglish': {
        'dev': [
            ('Saan kinukuha ang gamit?', 'Equipment pickup uses room cobalt.', 'room cobalt'),
            ('Kailan nagsasara ang imbakan?', 'Storage closes at six.', 'at six'),
            ('Sino ang tagapag-ingat ng susi?', 'Key custody belongs to porter Dani.', 'porter Dani'),
            ('Kailan ang turbine inspection?', 'Turbine inspection occurs every Thursday.', 'every Thursday'),
            ('Saan ang marble inventory?', 'Marble inventory is stored in annex red.', 'annex red'),
            ('Sino ang lantern coordinator?', 'The lantern coordinator is keeper Sia.', 'keeper Sia'),
        ],
        'holdout': [
            ('Saan ibinabalik ang kagamitan?', 'Equipment handback uses room topaz.', 'room topaz'),
            ('Kailan nagbubukas ang tanggapan?', 'The office opens at eight.', 'at eight'),
            ('Sino ang nangangasiwa sa talaan?', 'Register oversight belongs to clerk Romi.', 'clerk Romi'),
            ('Kailan ang nozzle maintenance?', 'Nozzle maintenance occurs every Friday.', 'every Friday'),
            ('Saan ang linen archive?', 'Linen archive is stored in annex blue.', 'annex blue'),
            ('Sino ang beacon supervisor?', 'The beacon supervisor is keeper Emi.', 'keeper Emi'),
        ],
    },
}

# Collision annotations name token pairs, not semantic classifications performed
# by the runtime. Meanings/absence of relevance are human-authored fixture gold.
NEGATIVE = {
    'collision': {
        'dev': [
            ('When are university tuition deadlines?', 'Universe expansion is recorded in astronomy logs.', ('university', 'universe')),
            ('How are general election ballots counted?', 'Electricity generation uses a turbine.', ('general', 'generation')),
            ('What are customs passport rules?', 'Custom dashboard palettes use cyan.', ('customs', 'custom')),
            ('How do arms export treaties work?', 'The arm of the display mount folds inward.', ('arms', 'arm')),
            ('How does organic farming protect soil?', 'The concert organ has ivory keys.', ('organic', 'organ')),
            ('Why are console gaming controllers wireless?', 'Consolation prizes are awarded after the raffle.', ('console', 'consolation')),
        ],
        'holdout': [
            ('How do news editorial standards work?', 'New shelving arrives next month.', ('news', 'new')),
            ('How does intelligence agency oversight work?', 'Intelligent thermostat presets save energy.', ('intelligence', 'intelligent')),
            ('Why is experimental jazz rhythm irregular?', 'Experiment records use a numbered lab book.', ('experimental', 'experiment')),
            ('How does operating theater sterilization work?', 'Operator accounts use a violet badge.', ('operating', 'operator')),
            ('Why do business ethics matter?', 'Busy signal lamps flash amber.', ('business', 'busy')),
            ('How do provisional constitutional governments work?', 'Provision bins store dry rice.', ('provisional', 'provision')),
        ],
    },
    'accidental_overlap': {
        'dev': [
            ('How does musical pitch change?', 'Pitch coating seals the workshop roof.', None),
            ('Why do tectonic plates move?', 'Lunch plates are kept in cabinet A.', None),
            ('What causes geological faults?', 'Printer faults require a service ticket.', None),
            ('How do biological cells divide?', 'Battery cells are counted weekly.', None),
            ('Why does atmospheric pressure fall?', 'Pressure washers use bay cobalt.', None),
            ('How are legal appeals filed?', 'Fundraising appeals use a green envelope.', None),
        ],
        'holdout': [
            ('How does photographic exposure work?', 'Chemical exposure reports go to the safety desk.', None),
            ('Why do ocean currents circulate?', 'Circuit currents are measured in the electronics room.', None),
            ('What causes stellar fusion?', 'Fusion menu lunches are served upstairs.', None),
            ('How do literary plots develop?', 'Garden plots are assigned on Wednesday.', None),
            ('Why does economic inflation rise?', 'Balloon inflation uses a foot pump.', None),
            ('How are theatrical acts rehearsed?', 'Acts of repair are logged in binder pink.', None),
        ],
    },
    'ordinary_control': {
        'dev': [
            ('Write a poem about rusting valves.', 'Valve testing begins at noon.', None),
            ('Rewrite: The filter was replaced.', 'Filter replacement uses a service voucher.', None),
            ('Thanks, that helps.', 'Thanks cards are stored beside the gift shelf.', None),
            ('What did I tell you in our conversation?', 'Conversation records use a filing tray.', None),
            ('Why is the sky blue?', 'Blue receipt books are issued monthly.', None),
            ('Tell me a story about parcel allocation.', 'Parcel allocation requires a red ticket.', None),
        ],
        'holdout': [
            ('Compose a haiku about turning wheels.', 'Wheel rotation uses a torque wrench.', None),
            ('Rephrase: We collected the sample.', 'Sample collection needs a sterile jar.', None),
            ('Good morning!', 'Morning rounds start at seven.', None),
            ('What was your previous answer?', 'Answer sheets are held in drawer C.', None),
            ('Why do rainbows appear?', 'Rainbow labels identify visitor passes.', None),
            ('Tell me a joke about seminar organization.', 'Seminar organization needs a purple permit.', None),
        ],
    },
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    if (ROOT/'FREEZE.json').exists():
        raise SystemExit('Frozen: authoring is disabled. A revision needs a new version.')
    corpus = ROOT/'corpus'
    corpus.mkdir(exist_ok=True)
    documents, cases = [], []
    categories = tuple(POSITIVE) + tuple(NEGATIVE)
    for category in categories:
        group = POSITIVE.get(category, NEGATIVE.get(category))
        for split in ('dev', 'holdout'):
            for n, (query, statement, label) in enumerate(group[split], 1):
                key = f'{category}_{split}_{n}'
                doc_id = f'd{len(documents):03d}'
                extension = '.md' if n % 2 else '.txt'
                name = f'Note {doc_id}'
                intro = (' '.join(statement.split()[:2]) + ' has a local procedure note.') if category in ('inflection','derivation') else None
                text = (f'# {name}\n\n' if extension == '.md' else '') + ((intro+'\n\n') if intro else '') + statement + '\n'
                relative = f'corpus/{doc_id}{extension}'
                (ROOT/relative).write_text(text, encoding='utf-8', newline='\n')
                documents.append(dict(id=doc_id, path=relative, name=name, split=split,
                                      source_type='project_document' if n % 2 else 'local_text'))
                positive = category in POSITIVE
                relevant = [dict(document_id=doc_id, start=text.index(statement), end=text.index(statement)+len(statement), text=statement)] if positive else []
                answer = [dict(document_id=doc_id, start=text.index(label), end=text.index(label)+len(label), text=label)] if positive else []
                diagnostic = category in ('synonym', 'filipino_taglish')
                cases.append(dict(id=key, category=category, split=split, query=query,
                                  history=[dict(role='user', content='I prefer short answers.'), dict(role='assistant', content='Understood.')] if category=='ordinary_control' and n==4 else [],
                                  relevance_gold=relevant, answer_gold=answer,
                                  context_expected=positive, diagnostic_only=diagnostic,
                                  collision_pair=list(label) if category=='collision' else None,
                                  relevance_only_text=intro,
                                  note='Human-authored related/answer-bearing gold, not a ranking label.' if positive else 'Local bait is unrelated to the requested task; no local context should be supplied.'))
    # Identical statements in control bait are valid alternative sources for a
    # positive fact. Never credit only the arbitrarily chosen original file.
    for case in cases:
        if not case['relevance_gold']:
            continue
        statement = case['relevance_gold'][0]['text']
        answer = case['answer_gold'][0]['text']
        case['relevance_gold'], case['answer_gold'] = [], []
        for d in documents:
            if d['split'] != case['split']:
                continue
            text = (ROOT/d['path']).read_text(encoding='utf-8')
            if statement in text:
                start = text.index(statement)
                case['relevance_gold'].append(dict(document_id=d['id'], start=start, end=start+len(statement), text=statement))
                offset = start + statement.index(answer)
                case['answer_gold'].append(dict(document_id=d['id'], start=offset, end=offset+len(answer), text=answer))
            intro = case['relevance_only_text']
            if intro and intro in text:
                offset = text.index(intro)
                case['relevance_gold'].append(dict(document_id=d['id'], start=offset, end=offset+len(intro), text=intro))
    dump(ROOT/'documents.json', documents)
    (ROOT/'cases.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False)+'\n' for c in cases), encoding='utf-8', newline='\n')
    dump(ROOT/'split.json', {s:[c['id'] for c in cases if c['split']==s] for s in ('dev','holdout')})
    manifest = ''.join(f'[[documents]]\nid = "{d["id"]}"\npath = "{d["path"]}"\nname = "{d["name"]}"\n\n' for d in documents)
    (ROOT/'collection.toml').write_text(manifest.rstrip()+'\n', encoding='utf-8', newline='\n')
    for split in ('dev', 'holdout'):
        selected = [d for d in documents if d['split']==split]
        manifest = ''.join(f'[[documents]]\nid = "{d["id"]}"\npath = "{d["path"]}"\nname = "{d["name"]}"\n\n' for d in selected)
        (ROOT/f'collection_{split}.toml').write_text(manifest.rstrip()+'\n', encoding='utf-8', newline='\n')
    print(f'Authored {len(cases)} cases and {len(documents)} source files; no arm evaluated.')


if __name__ == '__main__':
    main()

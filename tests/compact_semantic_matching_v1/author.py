"""One-time, output-blind fixture construction. No retrieval or encoder imports.

Language labels are provisional until fluent human review. Do not rerun once
FREEZE.json exists. The initial holdout is authored here, never scored here.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
CATEGORIES = dict(english_semantic=12, filipino=12, taglish=12, lexical=8,
                  identifier=8, morphology=8, short_local=4, no_supply=16)

# query | relevant source text | answer-bearing exact text | plausible distractor
# Related source text is not automatically answer-bearing. All labels are authored
# before encoder acquisition or retrieval outputs. Each row has an independent topic.
DATA = {
    'dev': {
        'english_semantic': '''
How does Alder stop duplicate deliveries?|Alder ignores a message after its identifier has been recorded in the receipt ledger.|receipt ledger|Birch suppresses duplicate delivery by checking a memory cache.
Where can Briar users recover an erased note?|Briar retains discarded notes in the recycle drawer for seven days.|recycle drawer|Briar permanently purges notes when the recycle drawer retention period expires.
Who decides whether Cedar requests may proceed?|Cedar requires sign-off from the intake steward before a request advances.|intake steward|Cedar assigns storage maintenance to the archive steward.
How does Drift keep failed jobs from running forever?|Drift ends unsuccessful attempts after the fourth retry.|fourth retry|Drift rechecks successful job receipts every four hours.
Where does Elm place work that is waiting for a person?|Elm parks tasks needing human intervention in the review tray.|review tray|Elm sends completed tasks to the delivery tray.
When may Flint clients ask again after a denial?|Flint permits another submission once the cooling interval reaches thirty seconds.|thirty seconds|Flint retains denied submission logs for thirty days.
What protects Grove records from two simultaneous writers?|Grove serializes updates with a per-record mutex.|per-record mutex|Grove checks record integrity with a checksum after an update.
How does Harbor restore the last good configuration?|Harbor rolls settings back by loading the previous approved snapshot.|previous approved snapshot|Harbor exports the current configuration for audit without restoring it.
What determines which Ivy task is served next?|Ivy dispatches pending tasks according to arrival sequence.|arrival sequence|Ivy orders the completed-task report by task name.
Where does Juniper keep material that cannot be read?|Juniper moves undecodable uploads into the quarantine vault.|quarantine vault|Juniper stores approved readable uploads in the public vault.
How does Kestrel limit a user's active work?|Kestrel allows each account at most three simultaneous jobs.|three simultaneous jobs|Kestrel permits three administrators for each account.
When does Larch discard idle connections?|Larch closes an inactive session after ninety seconds of silence.|ninety seconds|Larch records an active session heartbeat every nine seconds.
''',
        'filipino': '''
Saan makikita ang mga resibong nakansela sa Amihan?|Sa Amihan, inililipat ang mga kinanselang resibo sa hiwalay na talaan.|hiwalay na talaan|Sa Amihan, ang mga bayad nang resibo ay nasa pangunahing talaan.
Sino ang dapat mag-apruba ng bakasyon sa Balangay?|Balangay leave applications require approval from the team supervisor.|team supervisor|Balangay expense applications require approval from the finance officer.
Gaano katagal puwedeng baguhin ang naipadalang ulat sa Dalisay?|Maaaring itama ang naipadalang ulat sa Dalisay sa loob ng dalawang araw.|dalawang araw|Ang naipadalang invoice sa Dalisay ay maaaring baguhin sa loob ng limang araw.
Ano ang gagawin kapag nawala ang kard sa Hiraya?|Hiraya replaces a missing access card after the owner submits a loss declaration.|loss declaration|Hiraya renews expired access cards after payment of the renewal fee.
Saan dinadala ang mga sirang kagamitan sa Ilaw?|Dinadala ang sirang kagamitan ng Ilaw sa silid ng pagkukumpuni.|silid ng pagkukumpuni|Dinadala ang bagong kagamitan ng Ilaw sa silid ng imbakan.
Kailan puwedeng kunin ang sertipiko sa Lakbay?|Lakbay releases certificates on the next working day after verification.|next working day|Lakbay releases travel advances on the day before departure.
Paano malalaman kung sino ang kumuha ng susi sa Luntian?|Itinatala sa logbook ng Luntian ang pangalan ng bawat humihiram ng susi.|logbook|Itinatala sa attendance sheet ng Luntian ang oras ng pagpasok ng kawani.
Ano ang kailangan para maibalik ang deposito sa Mayumi?|Mayumi refunds a deposit upon presentation of the original acknowledgment slip.|original acknowledgment slip|Mayumi collects a new deposit when a lease is extended.
Ilang bisita ang puwedeng isama sa Narra?|Sa Narra, maaaring magsama ang isang residente ng hanggang apat na bisita.|apat na bisita|Sa Narra, maaaring magrehistro ang residente ng dalawang sasakyan.
Sino ang tatawagan kapag tumagas ang tubo sa Pahina?|Pahina directs plumbing leak reports to the facilities desk.|facilities desk|Pahina directs account password problems to the support desk.
Paano itinatama ang maling pangalan sa talaan ng Salin?|Sa Salin, kailangang magpakita ng wastong ID bago itama ang pangalan sa talaan.|wastong ID|Sa Salin, kailangang magpakita ng resibo bago itama ang halaga ng bayad.
Saan ilalagay ang kahilingan para sa dagdag na upuan sa Tala?|Tala accepts extra-seat requests through the room-booking form.|room-booking form|Tala accepts equipment-repair requests through the maintenance form.
''',
        'taglish': '''
Paano mag-reschedule ng appointment sa Aster?|Aster lets a client move a visit by contacting the booking desk before noon.|booking desk|Aster lets a client cancel an invoice by contacting the billing desk.
Saan ang backup copies ng files sa Beacon?|Beacon stores recovery copies on the isolated archive disk.|isolated archive disk|Beacon stores working copies in the shared workspace.
May waiting period ba bago ma-activate ang Coral account?|Coral activates a newly verified account after six hours.|six hours|Coral expires an unverified invitation after six days.
Who can mag-unlock ng cabinet sa Dawn?|Sa Dawn, ang opisyal na tagapag-ingat lamang ang may susi sa kabinet.|opisyal na tagapag-ingat|Sa Dawn, ang guwardiya lamang ang may susi sa tarangkahan.
Ano ang limit ng file uploads sa Echo?|Echo accepts attachments no larger than twenty megabytes each.|twenty megabytes|Echo retains attachments for twenty days after closure.
Paano i-check kung delivered na ang parcel sa Fern?|Fern marks an item as received only after the recipient signs the handover sheet.|handover sheet|Fern marks an item as packed after the warehouse checklist is signed.
Kailan available ang lunch vouchers sa Glade?|Glade distributes meal coupons every Monday morning.|Monday morning|Glade distributes parking permits every Friday afternoon.
Saan mag-report ng missing payment sa Haven?|Haven routes absent remittance reports to the reconciliation queue.|reconciliation queue|Haven routes duplicate customer profiles to the identity queue.
Ano ang process para i-close ang Indigo ticket?|Sa Indigo, isinasara ang ticket matapos kumpirmahin ng humiling na nalutas ang problema.|kumpirmahin ng humiling|Sa Indigo, ina-archive ang ticket matapos ang taunang pagsusuri.
Can I borrow overnight ang Jade laptop?|Jade permits overnight equipment loans with written permission from the custodian.|written permission|Jade permits daytime equipment loans with an entry in the register.
Paano mag-opt out ng Kiwi reminders?|Kiwi disables notifications when the subscriber clears the reminder preference.|reminder preference|Kiwi removes an account when the owner completes the deletion form.
Sino ang contact for late shipment sa Lotus?|Lotus assigns delayed dispatch inquiries to the logistics coordinator.|logistics coordinator|Lotus assigns damaged-product inquiries to the quality coordinator.
''',
        'lexical': '''
What is Mica's receipt retention period?|Mica's receipt retention period is twelve months.|twelve months|Mica's draft retention period is two weeks.
Where is Nacre's incident register stored?|Nacre's incident register is stored in the safety cabinet.|safety cabinet|Nacre's visitor register is stored at reception.
Who approves Opal's purchase orders?|Opal purchase orders are approved by the procurement lead.|procurement lead|Opal maintenance orders are approved by the facilities lead.
What is Pearl's nightly export time?|Pearl runs its nightly export at 02:15 UTC.|02:15 UTC|Pearl runs its weekly cleanup at 03:30 UTC.
How many copies does Quartz's print job make?|Quartz's print job makes two copies by default.|two copies|Quartz's scan job captures four pages by default.
Which port does Reed's status service use?|Reed's status service uses port 7342.|7342|Reed's metrics service uses port 7343.
What is Sable's maximum booking duration?|Sable's maximum booking duration is three hours.|three hours|Sable's minimum cancellation notice is three days.
Where is Thistle's returns counter?|Thistle's returns counter is beside the north entrance.|north entrance|Thistle's sales counter is beside the south entrance.
''',
        'identifier': '''
What does CACHE_TTL_MINUTES control in Umber?|In Umber, CACHE_TTL_MINUTES sets cached response lifetime to eight minutes.|eight minutes|In Umber, CACHE_TTL_SECONDS configures a separate test cache.
Where does Vale write exports/summary.json?|Vale writes exports/summary.json beneath the session directory.|session directory|Vale writes exports/summary.csv beneath the reporting directory.
What uses Violet's /v1/archive endpoint?|Violet's /v1/archive endpoint accepts closed-record archive requests.|closed-record archive requests|Violet's /v1/archives endpoint lists existing archives.
What is Willow's queue_retry_limit value?|Willow sets queue_retry_limit to 5.|5|Willow sets queue_retry_delay to 15 seconds.
What happens in Wren's rotate_keys() function?|Wren's rotate_keys() function retires the previous signing key.|retires the previous signing key|Wren's rotate_key() function rotates a display legend in the UI.
Where is Xenon's configs/release.toml read?|Xenon reads configs/release.toml during release preparation.|release preparation|Xenon reads configs/releases.toml during dashboard rendering.
What does Yarrow's AB-17 status mean?|Yarrow uses AB-17 to mean an address check is pending.|address check is pending|Yarrow uses AB-71 to mean a payment check is pending.
Which Zinc job uses build_manifest_v2?|Zinc's packaging job uses build_manifest_v2.|packaging job|Zinc's preview job uses build_manifest_v1.
''',
        'morphology': '''
How does Amber approve requests?|Amber records approvals in the authorization log.|authorization log|Amber records removals in the disposal log.
Where are Brook cancellations recorded?|Brook records each canceled reservation in the booking journal.|booking journal|Brook records confirmed arrivals in the attendance journal.
How does Crest retry failed calls?|Crest retries unsuccessful calls three times.|three times|Crest repeats successful health checks every minute.
When does Delta archive records?|Delta's archiving task runs every Sunday.|every Sunday|Delta's validation task runs every Wednesday.
Who handles Ember validations?|Ember validates submissions through the review officer.|review officer|Ember prints submissions through the office assistant.
Where does Fjord store assignments?|Fjord assigns cases using the workload board.|workload board|Fjord tracks expenses using the finance board.
What is Garnet's reporting destination?|Garnet reports incidents to the duty manager.|duty manager|Garnet sends marketing reports to the sales manager.
How does Hazel authenticate users?|Hazel's authentication requires a one-time code.|one-time code|Hazel's authorization requires a role assignment.
''',
        'short_local': '''
Acorn opening time?|Acorn's service desk opens at 08:30.|08:30|Acorn's loading dock opens at 06:00.
Brume refund contact?|Brume sends refund inquiries to Mara.|Mara|Brume sends delivery inquiries to Noel.
Cairn locker fee?|Cairn charges forty pesos for a locker rental.|forty pesos|Cairn charges twenty pesos for towel rental.
Dune pickup point?|Dune's parcel pickup point is Gate C.|Gate C|Dune's parcel drop-off point is Gate A.
''',
        'no_supply': '''
What is Auric's refund deadline?|Only Boreal's refund deadline is described here: ten days after purchase.|wrong_entity|A different named service is not authority for Auric.
How do I repair an Auric payment terminal?|Auric terminal installation involves attaching the power cable and registering the device.|wrong_procedure|Installation instructions do not describe repair.
What is Auric's production log limit?|Auric's sandbox logs are capped at six megabytes.|wrong_scope|Sandbox settings do not establish production limits.
What does Auric's PAYMENT_READY_2 mean?|Auric uses PAYMENT_READY_1 to mark a completed payment review.|identifier_near_miss|Different exact status IDs are not interchangeable.
Thanks, that helped.|The Help desk processes requests for Auric account activation.|conversation|An acknowledgment does not authorize local context.
Hi there.|Auric's greeting service sends welcome messages to new users.|conversation|Greeting terminology is accidental overlap.
I'm feeling a bit overwhelmed today.|Auric's overload monitor pauses background jobs at peak load.|conversation|Human feelings are not a monitoring query.
That sounds good to me.|Auric's sound-testing procedure uses the calibration rack.|conversation|Conversational assent is not an equipment question.
Rewrite this politely: Send the receipt now.|Auric receipt dispatch requires approval from the cashier.|transformation|Rewrite only supplied text; don't import process facts.
Translate this to English: Pakisara ang pinto.|Auric door access requires a security card.|transformation|Translation of quoted text needs no project evidence.
Shorten this: Our meeting will begin at nine tomorrow morning.|Auric meetings begin at ten on weekdays.|transformation|External schedule must not alter a text transformation.
Turn this into a bullet: Back up the notes and label the folder.|Auric backups are stored in the cellar every night.|transformation|Formatting a supplied sentence needs no local facts.
Write a short poem about keys and rain.|Auric keeps spare keys in a waterproof cabinet.|writing|Creative output must not import an unrelated local policy.
Give me a name for a fictional archive.|Auric's archive directory is called copper-vault.|writing|Fictional naming is not a request for local settings.
Why is the sky blue?|Auric's status dashboard uses blue for queued work.|general_knowledge|Shared color terminology is not relevance.
What is seven times eight?|Auric invoice 7 has eight pending attachments.|general_reasoning|Arithmetic does not require matching invoice evidence.
''',
    },
    'holdout': {
        'english_semantic': '''
How does Marigold prevent incomplete files becoming visible?|Marigold publishes an upload only after an atomic rename of the finished staging file.|atomic rename|Marigold previews unfinished uploads in the staff staging browser.
Where can Nebula clients find a lost invoice number?|Nebula locates purchase identifiers in the mailed billing acknowledgment.|mailed billing acknowledgment|Nebula locates customer identifiers in the membership card.
Who can overturn Oak's rejected enrollment?|Oak allows a second decision only from the appeals chair.|appeals chair|Oak lets the admissions clerk correct typographical errors.
How does Palisade make room when its inbox fills?|Palisade evicts the oldest unpinned entry when the inbox reaches capacity.|oldest unpinned entry|Palisade retains pinned entries until the owner removes them.
When is Quill ready to accept new work after a restart?|Quill begins intake after its journal replay completes.|journal replay completes|Quill begins metrics collection immediately during restart.
Where does Rill record a user's permission withdrawal?|Rill writes consent revocations in the privacy register.|privacy register|Rill writes permission grants in the onboarding register.
What keeps Saffron requests from starving?|Saffron promotes a waiting request one tier after ten minutes.|one tier|Saffron demotes a failing worker after ten errors.
How does Tundra detect a changed attachment?|Tundra compares a newly computed digest with the recorded fingerprint.|recorded fingerprint|Tundra checks attachment names against the permitted extension list.
What tells Upland a long task is still alive?|Upland expects a periodic lease renewal from the active worker.|lease renewal|Upland expects a final completion receipt from the finished worker.
Where does Vesper direct information requested under privacy law?|Vesper assembles disclosure material in the requester-only download area.|requester-only download area|Vesper publishes generic privacy notices in the public download area.
How does Weir prevent a partial payment from closing a bill?|Weir leaves an invoice open until the remaining balance reaches zero.|remaining balance reaches zero|Weir closes expired payment links after fourteen days.
When does Xylem allow a held consignment to leave?|Xylem releases a shipment after customs clearance is recorded.|customs clearance|Xylem accepts a shipment when the warehouse intake scan is recorded.
''',
        'filipino': '''
Paano makakakuha ng kopya ng kontrata sa Bukal?|Sa Bukal, maaaring humingi ng kopya ng kontrata sa tanggapan ng mga talaan.|tanggapan ng mga talaan|Sa Bukal, maaaring humingi ng kopya ng mapa sa tanggapan ng pagpaplano.
Ano ang kailangan bago magamit ang serbisyo sa Dagat?|Dagat requires a completed orientation session before service access.|completed orientation session|Dagat requires a medical clearance before field deployment.
Saan puwedeng mag-charge ng de-kuryenteng bisikleta sa Gabay?|May puwesto para sa pag-charge ng de-kuryenteng bisikleta sa likod ng gusali ng Gabay.|likod ng gusali|May paradahan ng motorsiklo sa harap ng gusali ng Gabay.
Kailan sinusukat ang kalidad ng tubig sa Habagat?|Habagat tests water quality on the first Tuesday of each month.|first Tuesday|Habagat inspects fire extinguishers on the last Thursday of each month.
Sino ang responsable sa mga halaman sa Isla?|Ang tagapangasiwa ng hardin ang responsable sa mga halaman ng Isla.|tagapangasiwa ng hardin|Ang tagapangasiwa ng pasilidad ang responsable sa ilaw ng Isla.
Ilang oras puwedeng gamitin ang silid sa Katipunan?|Katipunan permits a study-room session of up to two hours.|two hours|Katipunan permits a hall reservation of up to eight hours.
Paano ibinabalik ang aklat kapag sarado ang Liwayway?|Kapag sarado ang Liwayway, maaaring ihulog ang aklat sa kahon ng pagsasauli.|kahon ng pagsasauli|Kapag bukas ang Liwayway, dinadala ang bagong donasyon sa mesa ng pagtanggap.
Ano ang singil para sa nawawalang badge sa Mulawin?|Mulawin charges seventy pesos to replace a missing badge.|seventy pesos|Mulawin charges thirty pesos to replace a damaged lanyard.
Saan dapat isumite ang tala ng oras sa Pag-asa?|Sa Pag-asa, isinusumite ang tala ng oras sa portal ng kawani.|portal ng kawani|Sa Pag-asa, isinusumite ang reklamo sa portal ng mamamayan.
Kailan puwedeng sumali ang bisita sa ensayo ng Sampaguita?|Sampaguita permits guests at the final rehearsal on Saturday.|final rehearsal on Saturday|Sampaguita permits members at every weekday rehearsal.
Paano kinukumpirma ang donasyon sa Silangan?|Nagpapadala ang Silangan ng sulat ng pagkilala sa bawat natanggap na donasyon.|sulat ng pagkilala|Nagpapadala ang Silangan ng paalala para sa mga ipinangakong donasyon.
Sino ang magpapasya sa paglipat ng silid sa Ugnay?|Ugnay room-transfer decisions belong to the housing panel.|housing panel|Ugnay bed repairs belong to the maintenance team.
''',
        'taglish': '''
How to request a gate pass sa Zephyr?|Zephyr issues an exit permit when the shift coordinator signs the departure slip.|shift coordinator|Zephyr issues a visitor permit when the receptionist records an arrival.
Kailan mag-e-expire ang Azure quote?|Azure's price offer remains valid for fourteen calendar days.|fourteen calendar days|Azure's delivery estimate remains valid for seven calendar days.
Where ang drop box for Comet survey forms?|Comet collects questionnaires in the sealed box beside reception.|sealed box beside reception|Comet collects applications at the appointment counter.
Paano malaman kung cleared na ang Dusk balance?|Dusk shows a cleared account when the settlement receipt has been posted.|settlement receipt|Dusk shows a reviewed account when the assessment checklist has been posted.
Ano ang dress code for Equinox lab visits?|Equinox visitors must wear closed shoes during a laboratory tour.|closed shoes|Equinox staff must wear an identification badge during an office visit.
Who handles overtime pay sa Fable?|Ang opisyal ng payroll ng Fable ang nagpoproseso ng bayad sa sobrang oras.|opisyal ng payroll|Ang tagapag-iskedyul ng Fable ang nag-aayos ng oras ng trabaho.
Saan makuha ang guest Wi-Fi password sa Halo?|Halo supplies the visitor network key at the front desk.|front desk|Halo supplies the staff network key through the IT portal.
How much ang reservation bond sa Irides?|Irides collects a three-hundred-peso security bond for a hall reservation.|three-hundred-peso|Irides collects a fifty-peso printing fee for a program booklet.
Paano i-renew ang Jolt membership?|Jolt extends membership after the annual subscription is paid.|annual subscription|Jolt transfers membership after the reassignment form is signed.
Ano ang pickup window ng Lumina supplies?|Lumina supplies may be collected between one and four in the afternoon.|one and four in the afternoon|Lumina returns may be deposited between eight and ten in the morning.
Kailan nag-u-update ang Meridian inventory?|Meridian refreshes stock totals at the end of each shift.|end of each shift|Meridian refreshes price labels at the start of each month.
Sino ang lead for Nimbus evacuation drill?|Nimbus assigns the practice evacuation to the safety marshal.|safety marshal|Nimbus assigns the alarm-system repair to the electrical technician.
''',
        'lexical': '''
What is Oasis's inspection interval?|Oasis's inspection interval is sixty days.|sixty days|Oasis's billing interval is thirty days.
Where is Prism's sign-in book?|Prism's sign-in book is on the eastern reception table.|eastern reception table|Prism's parcel book is on the western dispatch table.
Who authorizes Ripple's fee waivers?|Ripple's fee waivers are authorized by the accounts director.|accounts director|Ripple's deadline extensions are authorized by the course director.
What is Solace's delivery cutoff?|Solace's delivery cutoff is 16:45.|16:45|Solace's collection cutoff is 11:15.
How many seats are in Tempest's small room?|Tempest's small room contains six seats.|six seats|Tempest's large room contains twelve seats.
Which channel carries Verve alerts?|Verve alerts are broadcast on channel 19.|19|Verve music is broadcast on channel 21.
What is Wander's equipment deposit?|Wander's equipment deposit is five hundred pesos.|five hundred pesos|Wander's meal deposit is one hundred pesos.
Where is Zenith's emergency exit?|Zenith's emergency exit is behind the western stairwell.|western stairwell|Zenith's delivery entrance is beside the eastern stairwell.
''',
        'identifier': '''
What does ATLAS_BATCH_SIZE set?|ATLAS_BATCH_SIZE sets the nightly batch size to 64 records.|64 records|ATLAS_BATCH_BYTES sets a separate byte limit for diagnostics.
Where is Lyric's logs/audit.ndjson written?|Lyric writes logs/audit.ndjson beneath the protected runtime folder.|protected runtime folder|Lyric writes logs/audits.json beneath the shared report folder.
What does Muse's /v2/lease endpoint return?|Muse's /v2/lease endpoint returns the current worker lease.|current worker lease|Muse's /v2/leases endpoint returns a list of historical leases.
What is Nectar's reconnect_delay_ms?|Nectar sets reconnect_delay_ms to 750.|750|Nectar sets reconnect_deadline_ms to 9000.
What does Orbit's seal_record() do?|Orbit's seal_record() marks a record immutable.|marks a record immutable|Orbit's seal_records() prepares a printable bundle.
Where is Pike's assets/policy.yaml used?|Pike uses assets/policy.yaml for local rule loading.|local rule loading|Pike uses assets/policies.yaml for website navigation.
What does Rook's ZX_204 code mean?|Rook uses ZX_204 for an expired lease.|expired lease|Rook uses ZX_240 for a missing receipt.
Which Sylvan task calls refresh_catalog_v3?|Sylvan's catalog update task calls refresh_catalog_v3.|catalog update task|Sylvan's price update task calls refresh_catalog_v2.
''',
        'morphology': '''
How are Finch subscriptions extended?|Finch extends a subscription after receiving the renewal payment.|renewal payment|Finch terminates a subscription after receiving a closure request.
Who handles Iris reimbursements?|Iris reimburses approved expenses through the treasury clerk.|treasury clerk|Iris approves travel through the program clerk.
Where does Lynx encrypt data?|Lynx's encryption happens in the protected staging area.|protected staging area|Lynx's compression happens in the export area.
When is Moss certification performed?|Moss certifies equipment at the annual safety review.|annual safety review|Moss calibrates equipment during the monthly measurement review.
What does Otter notify users about?|Otter's notifications announce reservation changes.|reservation changes|Otter's announcements describe community events.
Where are Plover evaluations recorded?|Plover evaluates submissions in the assessment ledger.|assessment ledger|Plover tracks attendance in the presence ledger.
How does Robin inspect parcels?|Robin's inspection uses the screening station.|screening station|Robin's weighing uses the dispatch scale.
Who schedules Swift pickups?|Swift's scheduling is handled by the route planner.|route planner|Swift's packaging is handled by the warehouse operator.
''',
        'short_local': '''
Agate complaint address?|Agate accepts complaints at review@agate.invalid.|review@agate.invalid|Agate accepts job applications at careers@agate.invalid.
Beryl closing hour?|Beryl's reception closes at 17:20.|17:20|Beryl's kitchen closes at 15:10.
Cobalt access age?|Cobalt admits members aged sixteen and above.|sixteen|Cobalt admits volunteers aged eighteen and above.
Dolomite collection day?|Dolomite collects recyclables on Thursdays.|Thursdays|Dolomite collects refuse on Tuesdays.
''',
        'no_supply': '''
How long is Argent's equipment warranty?|Bronze's equipment warranty lasts eighteen months.|wrong_entity|Warranty terms of a different named provider are not relevant authority.
How do I appeal an Argent loan rejection?|Argent loan applications are submitted through the finance portal.|wrong_procedure|Application instructions do not establish appeals procedure.
Who can view Argent's employee medical records?|Argent's visitor health declarations can be viewed by reception.|wrong_scope|Visitor declarations do not establish employee medical-record access.
What does Argent's LOCK_330 indicate?|Argent's LOCK_303 means a door sensor requires inspection.|identifier_near_miss|A similar error code is a different identifier.
Good morning!|Argent's morning inspection checks the ventilation controller.|conversation|Greeting is not a request for ventilation evidence.
Okay, understood.|Argent's understanding survey measures training completion.|conversation|Acknowledgment does not request a training survey.
I could use some encouragement.|Argent's incentive register lists annual staff awards.|conversation|Personal encouragement is not a query about staff awards.
That made me laugh.|Argent's laughter workshop runs at the community center.|conversation|Conversational feedback is not a workshop query.
Make this less formal: Please attend the briefing.|Argent briefing attendance is mandatory for security staff.|transformation|Rewrite the quoted sentence without importing attendance obligations.
Translate to Filipino: The window is open.|Argent open-window alarms notify the overnight guard.|transformation|Translation does not require an alarm policy.
Correct the spelling: The calender is on the wall.|Argent's wall calendar lists quarterly maintenance dates.|transformation|Spelling correction must not add calendar facts.
Put this in title case: monthly safety review.|Argent safety reviews are held in Room 12.|transformation|Title case is a text operation.
Write a bedtime story about a paper boat.|Argent boat storage requires a moisture-resistant cover.|writing|A story is not a storage-policy request.
Suggest a slogan for an imaginary help desk.|Argent's official help-desk slogan is Always On Call.|writing|Imaginary copywriting does not request the actual slogan.
Explain the difference between a noun and a verb.|Argent's database stores noun labels and verb event codes.|general_knowledge|Grammar explanation is not a database question.
If I have ten apples and give away three, how many remain?|Argent inventory batch ten has three spoiled apples.|general_reasoning|Simple arithmetic does not authorize local inventory context.
''',
    },
}


def save(name, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    (ROOT/name).write_bytes(raw.encode('utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def construct():
    if (ROOT/'FREEZE.json').exists():
        raise RuntimeError('Frozen evaluation cannot be reauthored')
    documents, split_ids, reviews = [], {}, []
    for split, categories in DATA.items():
        cases, manifest = [], []
        serial = 0
        folder = ROOT/'corpus'/split
        folder.mkdir(parents=True, exist_ok=True)

        def document(body):
            nonlocal serial
            serial += 1
            identity = f'{split}-entry-{serial:03}'
            path = f'corpus/{split}/{serial:03}.txt'
            # Source names carry no case/category, relevance or answer labels.
            text = body + '\n'
            (ROOT/path).write_bytes(text.encode('utf-8'))
            item = dict(id=identity, source_id=identity, split=split, path=path,
                        name=f'Local record {serial:03}', source_type='project_document' if serial%2 else 'local_text',
                        content_hash=hashlib.sha256(text.encode('utf-8')).hexdigest())
            documents.append(item)
            manifest.append(f'[[documents]]\nid = "{identity}"\npath = "{path}"\nname = "{item["name"]}"\n')
            return item, text

        for category, expected in CATEGORIES.items():
            rows = [r.strip().split('|') for r in categories[category].strip().splitlines()]
            assert len(rows)==expected, (split,category,len(rows))
            for n, parts in enumerate(rows, 1):
                identity = f'{split}_{category}_{n:02}'
                query, body, answer, distractor = parts
                case = dict(id=identity, split=split, category=category, query=query,
                            context_expected=category!='no_supply', mode='auto', history=[],
                            relevance_gold=[], answer_gold=[], distractors=[])
                if category=='no_supply':
                    d, _ = document(body)
                    case.update(negative_kind=answer, rationale=distractor, distractors=[d['id']])
                else:
                    d, text = document(body)
                    start = text.index(answer)
                    base = dict(document_id=d['id'], source_id=d['source_id'])
                    case['relevance_gold'] = [dict(base, start=0, end=len(body), text=body)]
                    case['answer_gold'] = [dict(base, start=start, end=start+len(answer), text=answer)]
                    other, _ = document(distractor)
                    case['distractors'] = [other['id']]
                    case['rationale'] = 'The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.'
                case['fluent_review_required'] = category in ('filipino','taglish') or (split=='dev' and category=='no_supply' and n==10)
                if case['fluent_review_required']:
                    reviews.append(dict(id=identity, case_sha256=digest(case), status='pending',
                                        reviewer=None, reviewed_at=None, comments=None))
                cases.append(case)
        split_ids[split] = [c['id'] for c in cases]
        save(f'cases_{split}.json', cases)
        (ROOT/f'collection_{split}.toml').write_bytes(('\n'.join(manifest)+'\n').encode('utf-8'))
    save('documents.json', documents)
    save('split.json', split_ids)
    save('language_review.json', dict(requirement='Fluent human review before freeze; no automatic sign-off.', entries=reviews))
    by_doc = {d['id']:d for d in documents}
    packet = ['# Fluent language review — 48 language positives and one quoted-text control', '',
              'Review naturalness, intended meaning, code-switching, relevance labels, answer spans and distractor exclusions. These are authored fixtures, not retrieval outputs.', '',
              'Construction-time review includes both initial splits. This does not spend a retrieval holdout. Once reviewed and frozen, no holdout retrieval/output inspection is permitted.', '',
              'Approve each ID or report corrections. Do not approve labels simply because they were generated. Review may correct fixtures before freeze; gates cannot be loosened.', '']
    for split in ('dev','holdout'):
        for c in json.loads((ROOT/f'cases_{split}.json').read_text(encoding='utf-8')):
            if not c['fluent_review_required']:
                continue
            bait = (ROOT/by_doc[c['distractors'][0]]['path']).read_text(encoding='utf-8').strip()
            packet += [f'## {c["id"]}', '', f'Query: {c["query"]}', '']
            if c['relevance_gold']:
                g,a = c['relevance_gold'][0],c['answer_gold'][0]
                packet += [f'Relevant source ({g["source_id"]}): {g["text"]}', '',
                           f'Answer span [{a["start"]}, {a["end"]}): **{a["text"]}**', '']
            else:
                packet += ['Gold: no local supply. Check the Filipino quotation and its translation-request meaning; no generated translation is evaluated.', '']
            packet += [f'Distractor (excluded): {bait}', '', f'Label rationale: {c["rationale"]}', '',
                       f'Case SHA-256: `{digest(c)}`', '', 'Review: pending', '']
    (ROOT/'LANGUAGE_REVIEW.md').write_bytes(('\n'.join(packet)+'\n').encode('utf-8'))
    return dict(cases=160, documents=len(documents), language_reviews=len(reviews))


if __name__=='__main__':
    print(json.dumps(construct()))

# Fluent language review — 48 language positives and one quoted-text control

Review naturalness, intended meaning, code-switching, relevance labels, answer spans and distractor exclusions. These are authored fixtures, not retrieval outputs.

Construction-time review includes both initial splits. This does not spend a retrieval holdout. Once reviewed and frozen, no holdout retrieval/output inspection is permitted.

User language review completed on 2026-10-03. All 45 unchanged review items approved. Four requested corrections applied below and finalization approved by the user completion directive on 2026-10-03. All 49 review items are approved. Gates are unchanged.

## dev_filipino_01

Query: Saan makikita ang mga resibong nakansela sa Amihan?

Relevant source (dev-entry-025): Sa Amihan, inililipat ang mga kinanselang resibo sa hiwalay na talaan.

Answer span [52, 69): **hiwalay na talaan**

Distractor (excluded): Sa Amihan, ang mga bayad nang resibo ay nasa pangunahing talaan.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `a0aaf6b1e31aacab0268b95c91f985ff22f787bca3ccd88e453534451e8d3f2a`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_02

Query: Sino ang dapat mag-apruba ng bakasyon sa Balangay?

Relevant source (dev-entry-027): Balangay leave applications require approval from the team supervisor.

Answer span [54, 69): **team supervisor**

Distractor (excluded): Balangay expense applications require approval from the finance officer.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `d7c24a981a1b580269b20ed2422c54f6a40e509a4f37891ec11d56a25f6a8b66`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_03

Query: Gaano katagal puwedeng baguhin ang naipadalang ulat sa Dalisay?

Relevant source (dev-entry-029): Maaaring itama ang naipadalang ulat sa Dalisay sa loob ng dalawang araw.

Answer span [58, 71): **dalawang araw**

Distractor (excluded): Ang naipadalang invoice sa Dalisay ay maaaring baguhin sa loob ng limang araw.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `a174bd980fc6140fd8e054312bd183e59fe5bf1398ddbce105dce90c2a66179c`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_04

Query: Ano ang gagawin kapag nawala ang kard sa Hiraya?

Relevant source (dev-entry-031): Hiraya replaces a missing access card after the owner submits a loss declaration.

Answer span [64, 80): **loss declaration**

Distractor (excluded): Hiraya renews expired access cards after payment of the renewal fee.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `4f53b17230a6f487809b9c3f50fc770101a38fbc37728c01b6b8f83f83b0b0eb`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_05

Query: Saan dinadala ang mga sirang kagamitan sa Ilaw?

Relevant source (dev-entry-033): Dinadala ang sirang kagamitan ng Ilaw sa silid ng pagkukumpuni.

Answer span [41, 62): **silid ng pagkukumpuni**

Distractor (excluded): Dinadala ang bagong kagamitan ng Ilaw sa silid ng imbakan.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `08d5ec4d37798764b8f74297d633ed640bda221ba1530f6d7b6ef928423abee3`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_06

Query: Kailan puwedeng kunin ang sertipiko sa Lakbay?

Relevant source (dev-entry-035): Lakbay releases certificates on the next working day after verification.

Answer span [36, 52): **next working day**

Distractor (excluded): Lakbay releases travel advances on the day before departure.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `8a30f53ef1065631a7cc72ecbd9a3e77f855e814d07d221eefdc884621f16b0a`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_07

Query: Paano malalaman kung sino ang kumuha ng susi sa Luntian?

Relevant source (dev-entry-037): Itinatala sa logbook ng Luntian ang pangalan ng bawat humihiram ng susi.

Answer span [13, 20): **logbook**

Distractor (excluded): Itinatala sa attendance sheet ng Luntian ang oras ng pagpasok ng kawani.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `fc5efd934cca9a9366c16937815a537f19fcefcc855915a06b15b8449454aac6`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_08

Query: Ano ang kailangan para maibalik ang deposito sa Mayumi?

Relevant source (dev-entry-039): Mayumi refunds a deposit upon presentation of the original acknowledgment slip.

Answer span [50, 78): **original acknowledgment slip**

Distractor (excluded): Mayumi collects a new deposit when a lease is extended.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `10f6f1b3f7fe3c92cccfb7334788f52b88a48db0188574208df96397b7fc3fdf`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_09

Query: Ilang bisita ang puwedeng isama sa Narra?

Relevant source (dev-entry-041): Sa Narra, maaaring magsama ang isang residente ng hanggang apat na bisita.

Answer span [59, 73): **apat na bisita**

Distractor (excluded): Sa Narra, maaaring magrehistro ang residente ng dalawang sasakyan.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `1b08011029eb41eb114884e7f226af71712ce158e1fbc16c6b0cfbe7f2b76da4`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_10

Query: Sino ang tatawagan kapag tumagas ang tubo sa Pahina?

Relevant source (dev-entry-043): Pahina directs plumbing leak reports to the facilities desk.

Answer span [44, 59): **facilities desk**

Distractor (excluded): Pahina directs account password problems to the support desk.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `0c0da5158f0da501acd1b5e5ae14402a3ff6c512b2c5ec755e6c242107199f7e`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_11

Query: Paano itinatama ang maling pangalan sa talaan ng Salin?

Relevant source (dev-entry-045): Sa Salin, kailangang magpakita ng wastong ID bago itama ang pangalan sa talaan.

Answer span [34, 44): **wastong ID**

Distractor (excluded): Sa Salin, kailangang magpakita ng resibo bago itama ang halaga ng bayad.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `30792be9bc5db58196d38da67d89d40d4c94e09a7ad0a91d60f4cabf8a99d446`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_filipino_12

Query: Saan ilalagay ang kahilingan para sa dagdag na upuan sa Tala?

Relevant source (dev-entry-047): Tala accepts extra-seat requests through the room-booking form.

Answer span [45, 62): **room-booking form**

Distractor (excluded): Tala accepts equipment-repair requests through the maintenance form.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `d59a97d420706bf0787be2954fb9cdb8318c6c01a4116c3ec9ec0f2facd380b1`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_01

Query: Paano mag-reschedule ng appointment sa Aster?

Relevant source (dev-entry-049): Aster lets a client move a visit by contacting the booking desk before noon.

Answer span [51, 63): **booking desk**

Distractor (excluded): Aster lets a client cancel an invoice by contacting the billing desk.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `bd9228c53c7348ab0985e2f582ad4bdfa092aa7edb9048d1753f7371c2cf4e18`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_02

Query: Saan ang backup copies ng files sa Beacon?

Relevant source (dev-entry-051): Beacon stores recovery copies on the isolated archive disk.

Answer span [37, 58): **isolated archive disk**

Distractor (excluded): Beacon stores working copies in the shared workspace.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `b004d23d4a424bff0c72d31f387a3609e025f2b5b2fc0b8be1c7f78ce04c6c58`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_03

Query: May waiting period ba bago ma-activate ang Coral account?

Relevant source (dev-entry-053): Coral activates a newly verified account after six hours.

Answer span [47, 56): **six hours**

Distractor (excluded): Coral expires an unverified invitation after six days.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `64540189c99ac71046c8a6005d0fc590b591926aee1d5cf65c26e44706209c12`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_04

Query: Who can mag-unlock ng cabinet sa Dawn?

Relevant source (dev-entry-055): Sa Dawn, ang opisyal na tagapag-ingat lamang ang may susi sa kabinet.

Answer span [13, 37): **opisyal na tagapag-ingat**

Distractor (excluded): Sa Dawn, ang guwardiya lamang ang may susi sa tarangkahan.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `c8d364444f62bc6e8dc0f950a6b30c326413de8b54b3a4c6decfea1ab4ab96fa`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_05

Query: Ano ang limit ng file uploads sa Echo?

Relevant source (dev-entry-057): Echo accepts attachments no larger than twenty megabytes each.

Answer span [40, 56): **twenty megabytes**

Distractor (excluded): Echo retains attachments for twenty days after closure.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `f61f7a813239104b2f214ed57775929bffe891af3344ed7f272eae1aabe5005b`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_06

Query: Paano i-check kung delivered na ang parcel sa Fern?

Relevant source (dev-entry-059): Fern marks an item as received only after the recipient signs the handover sheet.

Answer span [66, 80): **handover sheet**

Distractor (excluded): Fern marks an item as packed after the warehouse checklist is signed.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `74ed9c93b1b876059ff0b4d319c2ad58d5550cc78ab6e01250d3baefa01a4a6f`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_07

Query: Kailan available ang lunch vouchers sa Glade?

Relevant source (dev-entry-061): Glade distributes meal coupons every Monday morning.

Answer span [37, 51): **Monday morning**

Distractor (excluded): Glade distributes parking permits every Friday afternoon.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `a651f1767f01be1196a129d06ab3005d2ba1af45a330160e22508000e5df9df4`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_08

Query: Saan mag-report ng missing payment sa Haven?

Relevant source (dev-entry-063): Haven routes absent remittance reports to the reconciliation queue.

Answer span [46, 66): **reconciliation queue**

Distractor (excluded): Haven routes duplicate customer profiles to the identity queue.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `d4e91d0779e28b90f1ce407efcccece7e438e1df9aab5861378333bf4f725345`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_09

Query: Ano ang process para i-close ang Indigo ticket?

Relevant source (dev-entry-065): Sa Indigo, isinasara ang ticket matapos kumpirmahin ng humiling na nalutas ang problema.

Answer span [40, 63): **kumpirmahin ng humiling**

Distractor (excluded): Sa Indigo, ina-archive ang ticket matapos ang taunang pagsusuri.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `85c2e65e2fd7a2bc09e321b6542c0ab7f51456b3ff2a93b0f5876f1de5a6cf29`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_10

Query: Can I borrow overnight ang Jade laptop?

Relevant source (dev-entry-067): Jade permits overnight equipment loans with written permission from the custodian.

Answer span [44, 62): **written permission**

Distractor (excluded): Jade permits daytime equipment loans with an entry in the register.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `a784cc33dc6caaa71e52618e4e769d625b514df2131014beccc1a7f2f48ad245`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_11

Query: Paano mag-opt out ng Kiwi reminders?

Relevant source (dev-entry-069): Kiwi disables notifications when the subscriber clears the reminder preference.

Answer span [59, 78): **reminder preference**

Distractor (excluded): Kiwi removes an account when the owner completes the deletion form.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `40983b179a7244bef6a7058aeb72d8cfb4678e9dbd15b382af8a6f3430eebbef`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_taglish_12

Query: Sino ang contact for late shipment sa Lotus?

Relevant source (dev-entry-071): Lotus assigns delayed dispatch inquiries to the logistics coordinator.

Answer span [48, 69): **logistics coordinator**

Distractor (excluded): Lotus assigns damaged-product inquiries to the quality coordinator.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `c4d7412b2c12f1265ba744192d06777580a090846f9dca218832e9a9d9f2ebb9`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## dev_no_supply_10

Query: Translate this to English: Pakisara ang pinto.

Gold: no local supply. Check the Filipino quotation and its translation-request meaning; no generated translation is evaluated.

Distractor (excluded): Auric door access requires a security card.

Label rationale: Translation of quoted text needs no project evidence.

Case SHA-256: `0028eff10ae599de77fe444b16c1713c67b98e6fa240740e7d82f27edecc2f02`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_01

Query: Paano makakakuha ng kopya ng kontrata sa Bukal?

Relevant source (holdout-entry-025): Sa Bukal, maaaring humingi ng kopya ng kontrata sa tanggapan ng mga talaan.

Answer span [51, 74): **tanggapan ng mga talaan**

Distractor (excluded): Sa Bukal, maaaring humingi ng kopya ng mapa sa tanggapan ng pagpaplano.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `596445e7a63955a0c43361e4d98049c3a37c564d0f9982e3ff5e144a3cf8098c`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_02

Query: Ano ang kailangan bago magamit ang serbisyo sa Dagat?

Relevant source (holdout-entry-027): Dagat requires a completed orientation session before service access.

Answer span [17, 46): **completed orientation session**

Distractor (excluded): Dagat requires a medical clearance before field deployment.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `bb52fb52be42b0aceee6d059aa11518fad8b0d14fd4b5df0c52c75d3d91fade6`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_03

Query: Saan puwedeng mag-charge ng de-kuryenteng bisikleta sa Gabay?

Relevant source (holdout-entry-029): May puwesto para sa pag-charge ng de-kuryenteng bisikleta sa likod ng gusali ng Gabay.

Answer span [61, 76): **likod ng gusali**

Distractor (excluded): May paradahan ng motorsiklo sa harap ng gusali ng Gabay.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `514d73b9c40212c21e5e243564f0ca900a1be148d9ad32b510b60ca01f4a7f56`

Review: approved - Eugene (user), 2026-10-03. Specified correction applied; finalization approved by user completion directive.

## holdout_filipino_04

Query: Kailan sinusukat ang kalidad ng tubig sa Habagat?

Relevant source (holdout-entry-031): Habagat tests water quality on the first Tuesday of each month.

Answer span [35, 48): **first Tuesday**

Distractor (excluded): Habagat inspects fire extinguishers on the last Thursday of each month.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `5b9c10f6dd520481c5d7ff25e5581ae3804f20acf52a6933b041d7c3c1a379ee`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_05

Query: Sino ang responsable sa mga halaman sa Isla?

Relevant source (holdout-entry-033): Ang tagapangasiwa ng hardin ang responsable sa mga halaman ng Isla.

Answer span [4, 27): **tagapangasiwa ng hardin**

Distractor (excluded): Ang tagapangasiwa ng pasilidad ang responsable sa ilaw ng Isla.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `bdcc0703269a9427b842647523aafed25db2d9c5bbfd88beb5a889c2c945bc4d`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_06

Query: Ilang oras puwedeng gamitin ang silid sa Katipunan?

Relevant source (holdout-entry-035): Katipunan permits a study-room session of up to two hours.

Answer span [48, 57): **two hours**

Distractor (excluded): Katipunan permits a hall reservation of up to eight hours.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `a6f10388f36a63815d14f129b2b4149df4f985f58f276048ca7b07c6ccabd805`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_07

Query: Paano ibinabalik ang aklat kapag sarado ang Liwayway?

Relevant source (holdout-entry-037): Kapag sarado ang Liwayway, maaaring ihulog ang aklat sa kahon ng pagsasauli.

Answer span [56, 75): **kahon ng pagsasauli**

Distractor (excluded): Kapag bukas ang Liwayway, dinadala ang bagong donasyon sa mesa ng pagtanggap.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `7ba8bff70e35a1c6868a0ac79715203b8f385e0826680e5ec551163fbc3d8137`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_08

Query: Ano ang singil para sa nawawalang badge sa Mulawin?

Relevant source (holdout-entry-039): Mulawin charges seventy pesos to replace a missing badge.

Answer span [16, 29): **seventy pesos**

Distractor (excluded): Mulawin charges thirty pesos to replace a damaged lanyard.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `55a2b9f717816147eebffcd7de7e2d9f7784f458e3647543c2da474398d55b3b`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_09

Query: Saan dapat isumite ang tala ng oras sa Pag-asa?

Relevant source (holdout-entry-041): Sa Pag-asa, isinusumite ang tala ng oras sa portal ng kawani.

Answer span [44, 60): **portal ng kawani**

Distractor (excluded): Sa Pag-asa, isinusumite ang reklamo sa portal ng mamamayan.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `ff4d28e3c34f1791f1f76877e6275b30e4aad5333bcb513eb2d83cefec8fc01d`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_10

Query: Kailan puwedeng sumali ang bisita sa ensayo ng Sampaguita?

Relevant source (holdout-entry-043): Sampaguita permits guests at the final rehearsal on Saturday.

Answer span [33, 60): **final rehearsal on Saturday**

Distractor (excluded): Sampaguita permits members at every weekday rehearsal.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `dbbc2e4524edf2122fdff1ad6ecad5297652e109c7bd09cc16f9ec8816585f60`

Review: approved - Eugene (user), 2026-10-03. Specified correction applied; finalization approved by user completion directive.

## holdout_filipino_11

Query: Paano kinukumpirma ang donasyon sa Silangan?

Relevant source (holdout-entry-045): Nagpapadala ang Silangan ng sulat ng pagkilala sa bawat natanggap na donasyon.

Answer span [28, 46): **sulat ng pagkilala**

Distractor (excluded): Nagpapadala ang Silangan ng paalala para sa mga ipinangakong donasyon.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `70cbc6743fab59583d88d1247a01cec5e26ab1b83ceedb48670e076266cb1e0a`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_filipino_12

Query: Sino ang magpapasya sa paglipat ng silid sa Ugnay?

Relevant source (holdout-entry-047): Ugnay room-transfer decisions belong to the housing panel.

Answer span [44, 57): **housing panel**

Distractor (excluded): Ugnay bed repairs belong to the maintenance team.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `6f6c489e842b6aea5c8b8647a10b4cb6b7f1e5d541cb683ff3d3c7e21aa7f842`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_01

Query: How to request a gate pass sa Zephyr?

Relevant source (holdout-entry-049): Zephyr issues an exit permit when the shift coordinator signs the departure slip.

Answer span [38, 55): **shift coordinator**

Distractor (excluded): Zephyr issues a visitor permit when the receptionist records an arrival.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `9c8b1ae99067c70f9d91ab306cfc76c4d644dc03316fe392b14e560b583fb2a9`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_02

Query: Kailan mag-e-expire ang Azure quote?

Relevant source (holdout-entry-051): Azure's price offer remains valid for fourteen calendar days.

Answer span [38, 60): **fourteen calendar days**

Distractor (excluded): Azure's delivery estimate remains valid for seven calendar days.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `987f4c3fa7c20c9d8beaf2e48e27b31da9f9e56e8a2121720f408e631d73d973`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_03

Query: Where ang drop box for Comet survey forms?

Relevant source (holdout-entry-053): Comet collects questionnaires in the sealed box beside reception.

Answer span [37, 64): **sealed box beside reception**

Distractor (excluded): Comet collects applications at the appointment counter.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `2deb616b4482e1b1386b3d83d7078eab1027a9581f1e696ccf1bd21b2d5a62ae`

Review: approved - Eugene (user), 2026-10-03. Specified correction applied; finalization approved by user completion directive.

## holdout_taglish_04

Query: Paano malaman kung cleared na ang Dusk balance?

Relevant source (holdout-entry-055): Dusk shows a cleared account when the settlement receipt has been posted.

Answer span [38, 56): **settlement receipt**

Distractor (excluded): Dusk shows a reviewed account when the assessment checklist has been posted.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `352645688d5f0d3b4784f8444e1bdcf132f0e38817e01e7d2b4ddf1a0bf9ca93`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_05

Query: Ano ang dress code for Equinox lab visits?

Relevant source (holdout-entry-057): Equinox visitors must wear closed shoes during a laboratory tour.

Answer span [27, 39): **closed shoes**

Distractor (excluded): Equinox staff must wear an identification badge during an office visit.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `2060751d4ad45415a490dc5a5f0a30b1210935904a275d0e2dc78904e27f7c76`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_06

Query: Who handles overtime pay sa Fable?

Relevant source (holdout-entry-059): Ang opisyal ng payroll ng Fable ang nagpoproseso ng bayad sa sobrang oras.

Answer span [4, 22): **opisyal ng payroll**

Distractor (excluded): Ang tagapag-iskedyul ng Fable ang nag-aayos ng oras ng trabaho.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `7a790f50c0653b20195e191c8fda31a4eff71d1a0476030b1cf3b377c74819fb`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_07

Query: Saan makuha ang guest Wi-Fi password sa Halo?

Relevant source (holdout-entry-061): Halo supplies the visitor network key at the front desk.

Answer span [45, 55): **front desk**

Distractor (excluded): Halo supplies the staff network key through the IT portal.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `9e5af5608dbf76d7d4e334cc35b1e931bcc5455405691c9b257ff269bab4e06c`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_08

Query: How much ang reservation bond sa Irides?

Relevant source (holdout-entry-063): Irides collects a three-hundred-peso security bond for a hall reservation.

Answer span [18, 36): **three-hundred-peso**

Distractor (excluded): Irides collects a fifty-peso printing fee for a program booklet.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `6e54c990e516ca9f26f556b4fc152945a470cb6f5066a0fef0698ed366ff3883`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_09

Query: Paano i-renew ang Jolt membership?

Relevant source (holdout-entry-065): Jolt extends membership after the annual subscription is paid.

Answer span [34, 53): **annual subscription**

Distractor (excluded): Jolt transfers membership after the reassignment form is signed.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `5a0308e93fc94786a3c6c2e20d2aa02efc447ae96bed54efd3a72ad4788ef694`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_10

Query: Ano ang pickup window ng Lumina supplies?

Relevant source (holdout-entry-067): Lumina supplies may be collected between one and four in the afternoon.

Answer span [41, 70): **one and four in the afternoon**

Distractor (excluded): Lumina returns may be deposited between eight and ten in the morning.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `97ae0b1de5d28427eb53b7c8866cd2571674e39e67c560b44a5412da7cbbaadb`

Review: approved - Eugene (user), 2026-10-03. Specified correction applied; finalization approved by user completion directive.

## holdout_taglish_11

Query: Kailan nag-u-update ang Meridian inventory?

Relevant source (holdout-entry-069): Meridian refreshes stock totals at the end of each shift.

Answer span [39, 56): **end of each shift**

Distractor (excluded): Meridian refreshes price labels at the start of each month.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `10ad16e894a0a23ea9c92891f26e2f9f2dedbfad920e3f453cc9f9f442515c9a`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.

## holdout_taglish_12

Query: Sino ang lead for Nimbus evacuation drill?

Relevant source (holdout-entry-071): Nimbus assigns the practice evacuation to the safety marshal.

Answer span [46, 60): **safety marshal**

Distractor (excluded): Nimbus assigns the alarm-system repair to the electrical technician.

Label rationale: The named entity, requested procedure and scope must match; the paired entry is related but does not answer this request.

Case SHA-256: `cb3a2f36fb78e4b5c40dfc695801aa69116b0355da22adde7276ee70aa1a465c`

Review: approved - Eugene (user), 2026-10-03. Approved by user language review; preserve wording, including colloquial code-switching.


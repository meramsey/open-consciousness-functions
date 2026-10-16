"""Curated review notes, separate from active catalog data and earlier drafts.

Each row records the complete phrase reviewed in the source-English body and
closer, the relevant procedure/target, and scope that a naming decision must keep.
Line evidence and text fingerprints are generated from the actual resources.
"""

# function: (complete taught phrase, contextual editorial finding)
TEACHING = {
    "OCF-AUT-001": (
        "Plus Automate",
        "Correctly learn the selected ordered action, rehearse correct completion, then inhale/hold/cue/exhale. Automatic performance remains consciously observable, adjustable and stoppable; not future-condition manifestation.",
    ),
    "OCF-BOD-001": (
        "Plus Flow Better",
        "Brain/neck circulation maintenance and mental sharpness; select area, close eyes, inhale/hold/cue/slow mouth exhale. Automatic baseline plus optional local reinforcement; Brain Flow must not mean merely cognitive flow.",
    ),
    "OCF-BOD-002": (
        "Plus Flow Smooth",
        "Whole-body circulation and vessel maintenance, distinct from brain/neck emphasis. Select area, close eyes, inhale/hold/cue/slow mouth exhale; automatic baseline plus reinforcement.",
    ),
    "OCF-BOD-003": (
        "Plus Five Five Five One Five",
        "Locate physical discomfort, close eyes, inhale/hold/numeric cue/candle-like exhale. Reduces signal salience while retaining bodily awareness; COMFORT is a new association, not speech already taught. Distinct from temporary numbing.",
    ),
    "OCF-BOD-004": (
        "Plus Clean Clear",
        "Coordinated whole-body cleansing systems retain useful material and process unneeded material. Close eyes, attend to systems, inhale/hold/cue/exhale. Body Clarity would misleadingly suggest psychological clarity.",
    ),
    "OCF-BOD-005": (
        "Plus Satisfied Supplied",
        "One complete cue releases unnecessary craving while preserving genuine nutritional need and chosen eating. Pause, attend to craving, inhale/hold/cue/exhale. No independent appetite-increase mode is taught; do not split the two words into directions.",
    ),
    "OCF-BOD-006": (
        "Plus Heart Better Better",
        "Automatic heart muscle, vessel, rhythm and renewal maintenance plus reinforcement. Close eyes, heart attention, inhale/hold/complete repeated cue/exhale. Preserve the second Better; not merely heart-rate steadiness.",
    ),
    "OCF-BOD-007": (
        "Plus Balance Blood Pressure",
        "Appropriate cardiovascular regulation for rest/activity, not indiscriminate lowering. Close eyes, attend to heart/vessels, comfortable inhale/hold/cue/exhale. Keep Blood explicit; do not invent up/down modes.",
    ),
    "OCF-BOD-008": (
        "Plus Alert Destroy",
        "Immune-specific surveillance, coordinated response, memory, healthy-tissue protection and return to balance. Inhale/hold/cue/exhale; no eye-closing step is taught. Readiness must retain response scope, not generic alertness.",
    ),
    "OCF-BOD-009": (
        "Plus Breathe Better",
        "Respiratory-system maintenance, airway clearance, gas exchange and adaptive breathing. Inhale/hold/cue/exhale, without an added eye-closing step. Breathe is a verb/pronunciation correction, not formatting of Breath.",
    ),
    "OCF-BOD-010": (
        "Plus Food More",
        "MORE selects useful food-energy extraction/conversion/distribution/use; LESS selects sufficient nourishment with reduced unnecessary retention/storage. Close eyes, inhale/hold/select complete cue/exhale/open eyes. Neither mode is permanently active; automatic baseline differs. Not appetite control.",
    ),
    "OCF-BOD-011": (
        "Plus Equalize Harmonize",
        "Hormonal adaptation through premenstrual/perimenopausal/menopausal/postmenopausal transitions, not generic life change. Inhale/hold/cue/exhale; gratitude is optional, not a cue. Adaptive balance is not fixed hormone levels.",
    ),
    "OCF-BOD-012": (
        "Plus Sex More",
        "MORE/LESS select personal arousal directions and chosen redirection of attention/energy. Inhale/hold/chosen cue/exhale. Permanent learned availability does not leave either mode continuously active; GREATER/LESSER aliases are not current teaching.",
    ),
    "OCF-BOD-013": (
        "Plus Balance Heal",
        "Whole-body automatic maintenance and selected-area inward perception/repair. Close eyes, select area, inhale/hold/complete cue/exhale/open eyes. Balance and Heal are one cue, not separate modes; inner perception is not verified diagnosis.",
    ),
    "OCF-BOD-014": (
        "Plus Build Live",
        "Automatic repair/reconstruction and selected damaged/impaired/missing physical structure intent. Select area, picture complete form/function, close eyes, inhale/hold/cue/exhale. Regenerate is not yet taught; retain reconstruction provenance and scope.",
    ),
    "OCF-BOD-015": (
        "Plus Go Numb Go Numb",
        "Temporary localized numbing of selected new discomfort: close eyes, focus area, inhale/hold/complete cue/exhale. Selected-area Plus Release restores sensitivity; learning remains. Clarify restriction/release metadata separately; do not equate this with Comfort.",
    ),
    "OCF-COG-001": (
        "Plus Retrieve",
        "Requests knowledge/experience from the personal library. Cue then target in instruction/closer; practice selects target first. No breath instruction. Different from detailed event Recall; no external knowledge or accuracy verification is established.",
    ),
    "OCF-COG-002": (
        "Plus Calculate",
        "Automatic mathematical understanding, numerical memory and symbolic reasoning, optionally intensified with inhale/hold/cue/candle-like exhale. Mental Calculation must not narrow scope to arithmetic.",
    ),
    "OCF-COG-003": (
        "Plus Open",
        "Close eyes, inhale/hold/Open/exhale, then natural breathing opens total/greater-self communication. Plus Closed ends current contemplation, not learned access or a shared numbered Focus-state return. Review the reciprocal operation together.",
    ),
    "OCF-COG-004": (
        "Plus Imprint Imprint",
        "Selected information/experience encoding: inhale/hold/complete repeated cue/focus target/exhale. Plus Recall retrieves imprinted material. Registry suggestion/intention rehearsal understates actual memory encoding/consolidation; the shorter Imprint is not independently taught.",
    ),
    "OCF-COG-005": (
        "Plus Options Choices",
        "Close eyes, inhale/hold, select situation, complete cue, exhale with eyes remaining closed. Explore greater-self possibilities/probabilities and consequences while preserving choice. Plus Options is nested only, not independently taught or verified prediction.",
    ),
    "OCF-COG-006": (
        "Plus Recall",
        "Select memory/information, inhale/hold/cue/candle-like exhale for detailed retrieval. Shared Imprint retrieval is related but uses its own context/procedure; no global dispatcher precedence is implied.",
    ),
    "OCF-COG-007": (
        "Plus Think",
        "Automatic reasoning, working memory, clarity and flexible processing with optional inhale/hold/cue/candle-like reinforcement. Speed is not rushing. Preserve protected THINK; no invented MORE/LESS.",
    ),
    "OCF-COM-001": (
        "Plus Speak Up",
        "Automatic articulation, organization, vocal coordination, reading and everyday fluency; optional inhale/hold/cue/candle-like reinforcement. Speak Up is not volume-only or assertiveness-only.",
    ),
    "OCF-EMG-001": (
        "Plus Control Balance Restore",
        "Conscious inhale/hold/complete ordered cue/exhale reinforces injury response. Narrated automatic injury-triggered operation even asleep/unconscious is absent from manual/empty-trigger registry metadata. Resolve that scope separately; three verbs are not three modes.",
    ),
    "OCF-EMG-002": (
        "Plus Clear Remove",
        "Conscious inhale/hold/complete cue/exhale reinforces harmful-exposure response. Narrated automatic operation and chemical/venom/bite/sting scope exceed manual/empty-trigger registry metadata. Not emotional clearing; source-unavailable reconstruction is not authenticated history.",
    ),
    "OCF-EMO-001": (
        "Plus Let Go",
        "Recognize selected interfering emotion, inhale/hold/cue/candle-like exhale. Retain useful understanding, emotional responsiveness and choice; not temporary function release or indiscriminate removal of emotion.",
    ),
    "OCF-EMO-002": (
        "Plus Fade Fade",
        "Select recurring thought/emotional pattern, inhale/hold/cue/exhale then breathe naturally. Selected interference stays inactive until consciously desired otherwise; useful memories remain. Neither registry CLEAR nor proposed OFFLOAD is currently taught.",
    ),
    "OCF-EMO-003": (
        "Plus Profile Profile",
        "Select another being, quiet expectations and receive impressions with inhale/hold/complete cue/exhale. Retain total-self, wordless/nonphysical communion scope without treating impressions as verified knowledge/control of another being.",
    ),
    "OCF-EXP-001": (
        "Plus Change Change",
        "Select desired FUTURE CONDITION and COMPLETION TIME, inhale/hold/cue/slow mouth exhale. Total-self manifestation with non-destructive outcome condition; not merely breaking loops or generic goal rehearsal. Manifest is more specific than Create.",
    ),
    "OCF-EXP-002": (
        "Plus Insulate Insulate",
        "Represent head-to-toe insulating zone, inhale/hold/cue/exhale for temperature comfort. Plus Cancel ends current adjustment; selected Zoning plus Plus Release puts whole application on hold. Preserve distinct controls; not generic unwanted influence.",
    ),
    "OCF-FND-001": (
        "Plus Energize",
        "Cue, picture result, direct M energy to selected purpose; no breath requirement. Healing/protection/total-self direction exceeds simple energy restoration. Separate Plus Release Eleven Access closes access channel; it is not generic Release.",
    ),
    "OCF-FND-002": (
        "Plus Focus",
        "Select activity/thought/experience, inhale/hold/cue/candle-like exhale. Sustained attention permits conscious shifts; not entry to a numbered Focus state. Preserve protected FOCUS.",
    ),
    "OCF-FND-003": (
        "Plus Recharge",
        "Settle for brief natural sleep/rest, inhale/hold/cue/candle-like exhale; awakening within minutes. No programmable timer or wake/abort cue is supplied; distinguish energy access and overnight restoration.",
    ),
    "OCF-FND-004": (
        "Plus Relax Relax",
        "Inhale/hold/complete repeated cue/candle-like exhale releases physical/mental tension while allowing relaxed alert activity. Shorter RELAX is not independently taught; frozen editorial checkpoint remains pending.",
    ),
    "OCF-FND-005": (
        "Plus Reset Reset",
        "When tired/weary/emotionally low: inhale, close eyes/hold, complete repeated cue, exhale/open eyes into energized clear confident waking state. Not neutral global reset, ending other functions, or Recharge sleep.",
    ),
    "OCF-FND-006": (
        "Plus Release",
        "Consciously select temporary application or clearly selected group, inhale/hold/cue/exhale to END that application. Preserve learning, lasting baselines and other functions. Distinct Cancel/access-close roles are not overridden; Suspend may misleadingly imply ability disablement.",
    ),
    "OCF-LIF-001": (
        "Plus No More No More",
        "Recognize selected unwanted physical/mental habit as it arises, inhale/hold/complete cue/candle-like exhale for progressive lasting elimination. Preserve wanted memories/skills. This is habit change, not ending a temporary OCF application.",
    ),
    "OCF-PRF-001": (
        "Plus Do This Now",
        "Select activity and next action, inhale/hold/cue/candle-like exhale. Beginning, continuing and completing belong to one activity-directed operation, not three modes.",
    ),
    "OCF-PRF-002": (
        "Plus Eight Great",
        "Ongoing total-self greatness/power, conscious/subconscious/higher-self unity, wisdom and expression throughout life. OPTIONAL inhale/hold/cue/candle-like reinforcement. Inner Power retains this scope better than task competence or momentary physical force.",
    ),
    "OCF-PRF-003": (
        "Plus Smooth Fast",
        "Increasing mind/nervous-system/muscle coordination, balance, precision and timing; optional inhale/hold/cue/candle-like reinforcement. Smooth and Fast are one cue; steady precision, not indiscriminate speed.",
    ),
    "OCF-PRF-004": (
        "Plus Lighter Lighter",
        "Lasting efficient gait, clean foot lift, controlled placement and reduced impact; optional inhale/hold/cue/slow mouth exhale. Preserve automatic baseline rather than imply command-only walking/jogging/running scope.",
    ),
    "OCF-PRF-005": (
        "Plus This Day",
        "Each morning before activities, picture/express chosen internal states AND experiences/conditions/outcomes, inhale/hold/cue/exhale. Same-day manifestation, not merely setting mood; renewed daily rather than indefinite future programming.",
    ),
    "OCF-PRF-006": (
        "Plus Strong Quick",
        "Select essential immediate action, inhale/hold/cue/exhale. Exceptional strength/quickness application is temporary; focus Strong-Quick and use Plus Release with inhale/hold/exhale when need passes. Not lasting total-self Inner Power.",
    ),
    "OCF-SEN-001": (
        "Plus Hear More",
        "Close eyes, inhale/hold/chosen MORE or LESS cue/exhale/open eyes for external hearing; intention also selects imagined sound. Temporary adjustments differ from lasting imagery development. No normal/reset cue; frozen pilot untouched.",
    ),
    "OCF-SEN-002": (
        "Plus See Better",
        "Inhale/hold/cue/exhale reinforces physical sight, inner visualization or both by intention. Preserve protected SEE BETTER and physical/inner scope; superseded MORE/LESS must not return as artificial modes.",
    ),
    "OCF-SEN-003": (
        "Plus Smell More",
        "Close eyes, inhale/hold/chosen MORE or LESS cue/exhale/open eyes; external aromas or intended inner scent. GREATER/LESSER aliases are not current teaching; no third normal/reset cue.",
    ),
    "OCF-SEN-004": (
        "Plus Taste More",
        "Close eyes, inhale/hold/chosen MORE or LESS cue/exhale/open eyes for actual or imagined flavor. LESS can soften enjoyable flavor too; distinct from appetite. GREATER/LESSER aliases are not current teaching.",
    ),
    "OCF-SEN-005": (
        "Plus Touch More",
        "Close eyes, inhale/hold/chosen MORE or LESS cue/exhale/open eyes for physical sensation or intended tactile imagination. Not numbing/injury protection; body slow-mouth and closer candle-like exhale differ. GREATER/LESSER aliases are not current teaching.",
    ),
    "OCF-SLP-001": (
        "Plus Heal Heal",
        "Select restoration intention, deep inhale/gentle hold/cue/slow mouth candle-like exhale. Total-self healing/restoration/regeneration during natural sleep; lasting availability is not perpetual active application.",
    ),
    "OCF-SLP-002": (
        "Plus Twenty Twenty",
        "Choose sleep, breathe slowly/deeply/easily and cue DURING EXHALATION, repeating with successive breaths. Retain chosen waking time. Do not insert inhale/hold or candle procedure; registry SLEEP is not taught.",
    ),
    "OCF-SLP-003": (
        "Plus Theme Dream Sleep",
        "Select/represent dream theme, inhale/hold/complete cue/exhale, then slow deep breathing. Preserve selected dream experience AND clear joyful waking recall; do not add lucid-control or cancellation modes.",
    ),
    "OCF-SLP-004": (
        "Plus Sleep Help",
        "Select question/problem and intention, inhale/hold/cue/exhale then slow deep breathing; recognize answer through varied experiential forms on waking. Sleep problem incubation, not wake-time selection.",
    ),
    "OCF-SLP-005": (
        "Plus Quiet Sleep",
        "Unfamiliar/noisy/changing/distracting conditions and settling after interruptions distinguish this from Sleep. Comfortable, CLOSE EYES, deep INHALE/HOLD/cue/SLOW MOUTH EXHALE then easy natural breathing. No added candle step, alarm guarantee or procedure change; frozen review remains.",
    ),
    "OCF-SLP-006": (
        "Plus One Awake Alert One One",
        "Select essential immediate need, inhale/hold/complete cue/slow mouth exhale. Temporary purposeful alertness yields when need passes; lasting availability is not continuous stimulation. No separate release cue taught.",
    ),
}

# Override only this task's proposal, never canonical or previously edited reports.
# title, preferred cue, alternatives (paired), reason for the title/cue relationship.
PAIR_OVERRIDES = {
    "OCF-BOD-004": (
        "Body Cleansing",
        "PLUS-CLEAN CLEAR",
        [],
        "Names the retained bodily cleansing intent; avoids Body Clarity's psychological ambiguity. Cue already matches complete taught words.",
    ),
    "OCF-BOD-006": (
        "Heart Renewal",
        "PLUS-HEART, BETTER, BETTER",
        [],
        "Short descriptive title with the complete repeated reinforcement; shortening would change an established association without a clear usability need.",
    ),
    "OCF-BOD-007": (
        "Blood Pressure Balance",
        "PLUS-BALANCE BLOOD PRESSURE",
        [],
        "Noun title and natural verb cue retain the explicit blood-pressure target and complete spoken word order.",
    ),
    "OCF-BOD-010": (
        "Food Energy Use",
        "PLUS-USE FOOD ENERGY",
        [{"title": "Food Energy", "cue": "PLUS-FOOD MORE", "secondary": "PLUS-FOOD LESS"}],
        "Useful energy utilization and reduced unnecessary retention are asymmetric operations. Avoid Nourish Less, which can imply inadequate nourishment; decide both modes together.",
    ),
    "OCF-COG-003": (
        "Contemplation",
        "PLUS-OPEN",
        [{"title": "Contemplation", "cue": "PLUS-CONTEMPLATE", "secondary": "PLUS-CLOSED"}],
        "Opening and closing total-self communication form an explicitly taught reciprocal operation; semantic reinforcement justifies not copying the full title.",
    ),
    "OCF-EMO-003": (
        "Empathize",
        "PLUS-EMPATHIZE",
        [{"title": "Empathy", "cue": "PLUS-EMPATHIZE"}],
        "Natural action title and cue align directly while retaining total-self communion scope.",
    ),
    "OCF-FND-006": (
        "Release",
        "PLUS-RELEASE",
        [{"title": "End Application", "cue": "PLUS-END APPLICATION"}],
        "Release naturally ends a consciously selected temporary application; retain the contextual shared cue instead of implying erasure of learning or permanent-baseline disablement.",
    ),
    "OCF-LIF-001": (
        "Habit Freedom",
        "PLUS-FREE THIS HABIT",
        [{"title": "End This Habit", "cue": "PLUS-END THIS HABIT"}],
        "Targeted lasting habit change stays distinct from temporary application Release; cue explicitly selects this habit rather than ending every pattern.",
    ),
    "OCF-PRF-002": (
        "Inner Power",
        "PLUS-INNER POWER",
        [{"title": "Inner Capability", "cue": "PLUS-CAPABLE"}],
        "Names total-self power, unity and expression throughout life; distinguishes ongoing development from Strong-Quick's exceptional temporary physical response.",
    ),
}

UNRESOLVED = {"OCF-BOD-005", "OCF-BOD-010", "OCF-BOD-015", "OCF-EMG-001", "OCF-EMG-002"}

SECONDARY_PROPOSALS = {
    "OCF-CMD-BOD-010-FOOD-LESS": (
        "PLUS-RETAIN LESS EXCESS",
        "Reduce unnecessary energy retention while preserving sufficient useful nourishment. Review alongside USE FOOD ENERGY; not appetite suppression or less nourishment.",
    ),
}
